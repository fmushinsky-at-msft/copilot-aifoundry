# Custom Feedback Setup Guide (Copilot Studio)

How to collect 👍 / 👎 feedback — plus a free-text comment on negative ratings — using your
own Azure Function instead of the built-in Copilot Studio feedback store.

**Why do this:** the built-in conversational feedback is not reliably available or queryable
in every cloud (notably **GCC / GCC High / DoD**). This approach works everywhere, stores the
data in **your** Application Insights, and — critically — can be **joined to the
`AgentInteraction` telemetry** so you can see exactly which question was rated poorly.

**Time required:** about 30 minutes.

---

## Table of contents
- [How it works](#how-it-works)
- [Before you begin](#before-you-begin)
- [Part 1 — Create the "Submit Feedback" flow](#part-1--create-the-submit-feedback-flow)
- [Part 2 — Add the feedback prompt to your topic](#part-2--add-the-feedback-prompt-to-your-topic)
- [Part 3 — Publish and test](#part-3--publish-and-test)
- [Part 4 — Query the results](#part-4--query-the-results)
- [Part 5 — Troubleshooting](#part-5--troubleshooting)
- [Design notes and tradeoffs](#design-notes-and-tradeoffs)

---

## How it works

```
User asks a question
	  |
	  v
Agent answers  ──►  AgentInteraction event   (conversationId, canAnswer, tokens)
	  |
	  v
Topic asks: "Was this helpful?"  [Yes] [No]
	  |                                |
   [Yes]                             [No]
	  |                                |
	  |                       Ask: "What went wrong?"
	  |                                |
	  v                                v
		Call "Submit Feedback" flow  ──►  submit_feedback Function
											  |
											  v
								   UserFeedback event
								   (rating, comment, question, conversationId)
```

The **`conversationId`** is the join key. Passing the agent action's `threadId` into the
feedback call is what lets you correlate a thumbs-down with the exact question, the
`canAnswer` flag, and the token cost of that turn.

---

## Before you begin

- ☐ The Function is deployed and exposes the **`submit_feedback`** route.
- ☐ `APPLICATIONINSIGHTS_CONNECTION_STRING` is set on the Function App.
- ☐ You have the **function key** for `submit_feedback`:
  Azure Portal → Function App → **Functions** → `submit_feedback` → **Function Keys** → copy `default`.
- ☐ You know your Function App name, e.g. `func-hrbenefit-dev003`.
- ☐ You are a **maker** in the same Power Platform environment as the agent.
- ☐ **Power Automate Premium** licence (the HTTP action is a premium connector).

> **GCC note:** use the government portals —
> Copilot Studio: `https://gcc.copilotstudio.microsoft.us`
> Power Automate: `https://make.gov.powerautomate.us`
> (Exact hostnames vary by cloud; use whichever your tenant already uses.)

---

## Part 1 — Create the "Submit Feedback" flow

### Step 1.1 — Start the flow from Copilot Studio
1. Open **Copilot Studio** → select your agent.
2. Left navigation → **Tools** (older label: **Actions** / **Plugins**).
3. Click **+ Add a tool** → **New tool** → **Flow**.
4. Power Automate opens in a new tab with a starter flow.

✅ **Checkpoint:** you see **"When an agent calls the flow"** and **"Respond to the agent"**.

### Step 1.2 — Add the inputs
Click the trigger box, then **+ Add an input** → **Text** for each, named exactly:

| # | Input name | Purpose |
|---|---|---|
| 1 | `rating` | `up` or `down` |
| 2 | `comment` | free text (negative feedback only) |
| 3 | `question` | the question that was rated |
| 4 | `conversation_id` | join key to `AgentInteraction` |
| 5 | `user_id` | who rated |
| 6 | `user_full_name` | who rated |

> Names are case-sensitive and must match exactly.

✅ **Checkpoint:** six text inputs, in the order above.

### Step 1.3 — Add the HTTP action
1. Click the **+** below the trigger → **Add an action**.
2. Search `HTTP` → choose the plain **HTTP** action under **Built-in**.
   - ❌ Do **not** pick *HTTP with Microsoft Entra ID* — it restricts calls to a
	 pre-configured `BaseResourceUri` and will fail with a 400.
3. Configure:
   - **URI:** `https://<FUNCTION_APP>.azurewebsites.net/api/submit_feedback?code=<FUNCTION_KEY>`
   - **Method:** `POST`
   - **Headers:** `Content-Type` = `application/json`
   - **Body:**

```json
{
  "rating": "@{triggerBody()?['text']}",
  "comment": "@{triggerBody()?['text_1']}",
  "question": "@{triggerBody()?['text_2']}",
  "conversation_id": "@{triggerBody()?['text_3']}",
  "user_id": "@{triggerBody()?['text_4']}",
  "user_full_name": "@{triggerBody()?['text_5']}"
}
```

> **Verify the token names.** Power Automate names trigger inputs `text`, `text_1`, … in
> creation order. Click into the Body, open **Dynamic content**, and hover each input to
> confirm. Adjust the JSON if your order differs.

✅ **Checkpoint:** method `POST`, one header, and the JSON body above.

### Step 1.4 — Return a confirmation (optional)
1. Click the **Respond to the agent** box.
2. **+ Add an output** → **Text** → name it `result`.
3. Set its value from **HTTP → Body** (or add a **Parse JSON** step first using the sample
   `{ "recorded": true, "rating": "negative", "message": "Thanks for your feedback." }`).

### Step 1.5 — Name, save, and test
1. Top-left → rename the flow to **Submit Feedback**.
2. Click **Save**.
3. Click **Test** → **Manually** → supply sample values:
   - `rating` → `down`
   - `comment` → `Test comment`
   - `question` → `Test question`
   - `conversation_id` → `test-conv-001`
   - `user_id` → `TEST01`
   - `user_full_name` → `Test User`
4. Run it. The **HTTP** step should return **200** with
   `{"recorded": true, "rating": "negative", ...}`.

✅ **Checkpoint:** the flow runs green end-to-end.

### Step 1.6 — Make it visible to the agent
1. Return to the Copilot Studio tab.
2. Press **Ctrl + F5** to refresh.
3. **Tools** → confirm **Submit Feedback** is listed.

---

## Part 2 — Add the feedback prompt to your topic

### Step 2.1 — Open the topic
Copilot Studio → your agent → **Topics** → open the topic that answers questions
(the one calling your agent Function).

### Step 2.2 — Make sure the question is stored
You need the original question for the feedback record.
- If you already created `Topic.UserQuestion` (used for the email feature), reuse it.
- Otherwise add a **Set a variable value** node before the agent action:
  - **Set variable:** new variable `UserQuestion`
  - **To value:** **System** → **Activity.Text**

### Step 2.3 — Ask for the rating
Place this **after** the node that shows the agent's answer.

1. Click **+** → **Ask a question**.
2. **Enter a message:** `Was this helpful?`
3. **Identify:** → **Multiple choice options**.
4. **Options for user:** add two:
   - `Yes` (you may label it `👍 Yes`)
   - `No` (you may label it `👎 No`)
5. **Save response as** → rename the variable to `Helpful` (becomes `Topic.Helpful`).

✅ **Checkpoint:** the node shows two options and creates a branch for each.

### Step 2.4 — Positive branch (Yes)
1. Click **+** inside the **Yes** branch → **Add a tool** → **Submit Feedback**.
2. Set the inputs:

| Input | Value |
|---|---|
| `rating` | type the literal text `up` |
| `comment` | leave blank |
| `question` | `Topic.UserQuestion` |
| `conversation_id` | the agent action's **threadId** output |
| `user_id` | your user-id variable |
| `user_full_name` | **System → User.DisplayName** (or your variable) |

3. Add a **Send a message**: `Great — thanks for letting me know!`

### Step 2.5 — Negative branch (No)
1. Click **+** inside the **No** branch → **Ask a question**.
2. **Enter a message:** `Sorry about that. What went wrong?`
3. **Identify:** → **User's entire response** (free text).
4. **Save response as** → rename to `FeedbackComment` (becomes `Topic.FeedbackComment`).
5. Click **+** below it → **Add a tool** → **Submit Feedback**.
6. Set the inputs:

| Input | Value |
|---|---|
| `rating` | type the literal text `down` |
| `comment` | `Topic.FeedbackComment` |
| `question` | `Topic.UserQuestion` |
| `conversation_id` | the agent action's **threadId** output |
| `user_id` | your user-id variable |
| `user_full_name` | **System → User.DisplayName** (or your variable) |

7. Add a **Send a message**:
   `Thank you — I've passed that along so we can improve.`

> **Tip:** to let users skip the comment, add a **Condition** allowing an empty response,
> or offer a `Skip` quick reply. The Function accepts an empty `comment`.

### Step 2.6 — Save
Click **Save** and clear any red error markers.

✅ **Checkpoint:** Yes → records `up`; No → asks for a comment, then records `down`.

---

## Part 3 — Publish and test

### Step 3.1 — Publish
Copilot Studio → **Publish** → confirm. Changes do not reach Teams until published.

### Step 3.2 — Test in the Test panel
1. Ask a question and let the agent answer.
2. The **Was this helpful?** prompt should appear with Yes / No.
3. Click **No** → provide a comment → confirm the thank-you message.

### Step 3.3 — Test in Teams
Repeat in Teams to confirm behaviour on the real channel.

### Step 3.4 — Verify in the Function logs
Azure Portal → Function App → **Log stream**:
```
submit_feedback trigger invoked.
Feedback recorded: rating=negative hasComment=True conversationId=conv_...
```

### Step 3.5 — Verify the telemetry
Application Insights → **Logs** (allow 2–5 minutes):
```kql
customEvents
| where name == "UserFeedback"
| where timestamp > ago(30m)
| project timestamp, customDimensions
| order by timestamp desc
```

---

## Part 4 — Query the results

Full query set: **[ANALYTICS_KQL_QUERIES.md](./ANALYTICS_KQL_QUERIES.md)** → *User feedback*.

Most useful day to day — the review queue:
```kql
customEvents
| where name == "UserFeedback"
| where timestamp > ago(30d)
| where tostring(customDimensions.rating) == "negative"
| project timestamp,
		  question = tostring(customDimensions.question),
		  comment  = tostring(customDimensions.comment),
		  user     = tostring(customDimensions.userName)
| order by timestamp desc
```

---

## Part 5 — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Feedback prompt never appears | Topic not published, or generative orchestration bypassed it | Publish; consider classic orchestration |
| `400 Missing required parameter 'rating'` | Body field name wrong, or input order shifted | Check the HTTP body JSON against the real `text_N` tokens |
| `400 Parameter 'rating' must indicate up/down` | Passing `Yes`/`No` from the choice variable | Pass the **literal** `up` / `down`, not the choice value |
| `401` / `403` from the Function | Wrong or missing function key | Re-copy the key into the URI or `x-functions-key` header |
| Flow shows Premium warning | No Power Automate Premium licence | Request the licence |
| Events missing in `customEvents` | Exporter not installed / connection string unset | See the Setup section of ANALYTICS_KQL_QUERIES.md |
| `conversationId` is empty | `threadId` not mapped | Map the agent action's `threadId` output into `conversation_id` |
| Comment always empty | Question node not set to free text | Set **Identify** = *User's entire response* |

### Where to inspect
- **Power Automate** → **My flows** → **Submit Feedback** → **28-day run history** → open a
  run → check the trigger and HTTP step **Inputs**/**Outputs**.
- **Copilot Studio** → Test panel with **Track between topics** enabled.
- **Azure** → Function App → **Log stream**.

---

## Design notes and tradeoffs

**Why pass `rating` as a literal instead of the choice variable**
The choice variable holds `Yes`/`No`, which are ambiguous. Passing `up`/`down` explicitly on
each branch keeps the Function contract clear. (The Function does also accept `yes`/`no`,
`1`/`0`, `true`/`false`, and 👍/👎 — but explicit is better.)

**Question text is captured only on negative feedback**
Positive feedback records no question text, consistent with the wider telemetry
minimisation policy. Negative feedback stores the question because reviewing it is the whole
point. Comments are stored for both, though in practice only negative ones have them.

**Privacy**
`UserFeedback` records `userId`, `userName`, `userEmail`, the comment, and (for negative
ratings) the question text. Comments are free text and may contain personal information.
- ☐ Confirm this is acceptable with your privacy/compliance team.
- ☐ Review the Application Insights retention period (default 90 days).
- ☐ Restrict read access to the Application Insights resource.

**Tradeoff vs. the built-in feedback**
You lose the polished inline thumbs UI and gain an extra conversational turn. In exchange
you get data that is queryable in your own environment, works in GCC, and joins directly to
the interaction telemetry.

**Optional: only ask sometimes**
Prompting on every turn gets tiring. Consider asking only when `canAnswer` is `false`, or
using a random condition to sample (e.g. roughly 1 in 5 turns).
