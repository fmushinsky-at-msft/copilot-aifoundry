# Copilot Studio & Power Automate — Detailed Implementation Guide

Companion to **EMAIL_HR_DEPLOYMENT_CHECKLIST.md**, expanding Sections **7, 8, and 9** into
click-by-click instructions.

**Goal:** When the Benefit agent cannot answer a question, Teams offers to email the question
to HR; on *Yes*, the Azure Function sends the email.

**Assumed already done** (from the main checklist):
- Function code deployed, exposing `agent_httptrigger` (returns `canAnswer`) and `send_hr_email`.
- Function App settings, managed identity, Graph `Mail.Send`, Exchange policy configured.
- Foundry agent instructed to emit `NO_ANSWER` when it cannot answer.

---

## Table of contents
- [Part 0 — Orientation: where things live](#part-0--orientation-where-things-live)
- [Part 1 — Create the `send_hr_email` flow (Section 9)](#part-1--create-the-send_hr_email-flow-section-9)
- [Part 2 — Fix JSON escaping with `addProperty` (Section 7)](#part-2--fix-json-escaping-with-addproperty-section-7)
- [Part 3 — Topic logic: offer & send (Section 8)](#part-3--topic-logic-offer--send-section-8)
- [Part 4 — Publish and test](#part-4--publish-and-test)
- [Part 5 — Troubleshooting](#part-5--troubleshooting)

---

## Part 0 — Orientation: where things live

Two different web apps are involved. Keep both open in separate browser tabs.

| Tool | URL | What you do there |
|---|---|---|
| **Copilot Studio** | https://copilotstudio.microsoft.com | Topics (conversation logic), publishing the agent |
| **Power Automate** | https://make.powerautomate.com | Flows that call your Azure Function (HTTP actions) |

### Confirm you are in the right environment
1. Open **Copilot Studio**.
2. Top-right, next to your profile picture, find the **environment picker** (shows an
   environment name such as *Contoso (default)*).
3. Note the environment name.
4. Open **Power Automate** and use its environment picker (also top-right) to select the
   **same environment**.

> If the environments differ, the flow you build will not be visible to your agent.

### Terminology used below
- **Topic** — a conversation script in Copilot Studio (nodes arranged top to bottom).
- **Node** — one step in a topic (Send a message, Question, Condition, Call an action).
- **Action** — a call out to something external; for us, a Power Automate flow that calls
  the Azure Function.
- **Variable** — a value stored during the conversation, e.g. `Topic.EmailHR`.

---

## Part 1 — Create the `send_hr_email` flow (Section 9)

This flow is what the topic calls when the user says *Yes*. It POSTs to the Azure Function.

### 1.1 Gather what you need first
- Function App name, e.g. `pa-benefits-func`.
- The **function key** for `send_hr_email`:
  - Azure Portal → **Function App** → **Functions** → click **send_hr_email** →
	left menu **Function Keys** → copy the **default** key value.
- Resulting URL shape:
  `https://<FUNCTION_APP>.azurewebsites.net/api/send_hr_email`

### 1.2 Create the flow from Copilot Studio (recommended path)
Creating it from inside Copilot Studio automatically wires it as an available action.

1. Open **Copilot Studio** → select your agent (**PA-Health-Benefit-Agent** experience).
2. Left navigation → **Actions** (in some tenants this is under **Tools** or **Plugins**).
3. Click **+ Add an action** (or **New action**).
4. Choose **New flow** (this opens the Power Automate designer in a new tab, pre-wired with
   a Copilot Studio trigger).
5. You will see a trigger named **"When an agent calls the flow"** (older label:
   *"When Power Virtual Agents calls a flow"*).

### 1.3 Define the flow inputs
1. Click the trigger node **When an agent calls the flow**.
2. Click **+ Add an input**.
3. Choose **Text**. Name it exactly: `question`
4. Click **+ Add an input** → **Text** → name it: `user_full_name`
5. Click **+ Add an input** → **Text** → name it: `user_id`
6. Click **+ Add an input** → **Text** → name it: `conversation_id`

> Names are case-sensitive when you reference them later. Keep them exactly as above.

### 1.4 Add the Compose action that builds the JSON body
This is the escaping fix (Section 7) applied to this flow.

1. Below the trigger, click **+** → **Add an action**.
2. Search **Compose** → select **Compose** (under **Data Operation**).
3. Rename it for clarity: click the node title → type **Compose request body**.
4. Click inside the **Inputs** field.
5. Open the **expression editor**:
   - Newer designer: click the box, then the **fx** icon in the pop-up panel.
   - Classic designer: choose the **Expression** tab in the right-hand flyout.
6. Paste this **single-line** expression:

```
addProperty(addProperty(addProperty(addProperty(json('{}'), 'question', triggerBody()?['text']), 'user_full_name', triggerBody()?['text_1']), 'user_id', triggerBody()?['text_2']), 'conversation_id', triggerBody()?['text_3'])
```

7. Click **OK** / **Add** to commit.

> **Important — verify the token names.** Power Automate names trigger inputs
> `text`, `text_1`, `text_2`, `text_3` in the order you created them. To be certain:
> click in the Inputs box, open the **Dynamic content** tab, and hover each input to see
> its underlying token. If your order differs, adjust the expression accordingly so that:
> `question` ← the question input, `user_full_name` ← the name input, etc.

### 1.5 Add the HTTP action
1. Below Compose, click **+** → **Add an action**.
2. Search **HTTP** → select **HTTP** (the plain "HTTP" action, premium connector).
3. Configure:
   - **Method:** `POST`
   - **URI:** `https://<FUNCTION_APP>.azurewebsites.net/api/send_hr_email?code=<FUNCTION_KEY>`
   - **Headers:** add one row → Key `Content-Type`, Value `application/json`
   - **Body:** click the field → **Dynamic content** → under **Compose request body**
	 select **Outputs**. The field should show `@{outputs('Compose_request_body')}`
	 and contain nothing else.

> Alternative to putting the key in the URL: leave the URI without `?code=` and add a second
> header — Key `x-functions-key`, Value `<FUNCTION_KEY>`. Slightly cleaner (key not in URL logs).

### 1.6 Parse the function response (optional but recommended)
Lets the topic show the function's confirmation text.

1. Click **+** → **Add an action** → search **Parse JSON** → select it.
2. **Content:** Dynamic content → **HTTP** → **Body**.
3. **Schema:** click **Generate from sample** and paste:
```json
{ "sent": true, "message": "Your question has been emailed to HR." }
```
4. Click **Done**.

### 1.7 Return a value to Copilot Studio
1. Click **+** → **Add an action** → search **Respond to the agent** (older label:
   *"Respond to Power Virtual Agents"*) → select it.
2. Click **+ Add an output** → **Text** → name it `result`.
3. Set its value: Dynamic content → from **Parse JSON**, choose **message**
   (or, if you skipped Parse JSON, use **HTTP → Body**).

### 1.8 Name and save
1. Click the flow name at the top-left → rename to **Send HR Email**.
2. Click **Save** (top-right).
3. Wait for "Your flow is ready to go" / the save confirmation.

---

## Part 2 — Fix JSON escaping with `addProperty` (Section 7)

Part 1 already applied this to the new flow. Now apply the same fix to the **existing flow
that calls the agent** (`agent_httptrigger`) — this is what fixes the double-quote bug.

### 2.1 Open the existing agent flow
1. Go to **https://make.powerautomate.com** (correct environment).
2. Left navigation → **My flows**.
   - If the flow lives in a solution: left navigation → **Solutions** → open your agent's
	 solution → **Cloud flows**.
3. Find the flow that calls `agent_httptrigger` (name likely references the agent or the
   Copilot Studio action).
4. Click it → click **Edit** (pencil icon, top toolbar).

### 2.2 Inspect the current HTTP action
1. Scroll to the **HTTP** action whose URI contains `agent_httptrigger`.
2. Click it to expand.
3. Look at **Body**. Today it likely reads:
```json
{
  "message": "@{triggerBody()?['text']}",
  "agent_name": "PA-Health-Benefit-Agent",
  "parameters": {
	"user_id": "@{triggerBody()?['text_2']}",
	"user_full_name": "@{triggerBody()?['text_3']}"
  },
  "threadid": "@{triggerBody()?['text_1']}"
}
```
4. **Copy this text into a scratch file** before changing it — you need the exact token names
   (`text`, `text_1`, `text_2`, `text_3`).

### 2.3 Add the Compose action
1. Hover over the connector arrow just **above** the HTTP action.
2. Click the **+** circle → **Add an action**.
3. Search **Compose** → select **Compose**.
4. Rename it to **Compose agent body**.
5. Click **Inputs** → open the **fx / Expression** editor.
6. Paste this **single-line** expression (it reproduces the body above, including the nested
   `parameters` object):

```
addProperty(addProperty(addProperty(addProperty(json('{}'), 'message', triggerBody()?['text']), 'agent_name', 'PA-Health-Benefit-Agent'), 'parameters', addProperty(addProperty(json('{}'), 'user_id', triggerBody()?['text_2']), 'user_full_name', triggerBody()?['text_3'])), 'threadid', triggerBody()?['text_1'])
```

7. Click **OK**.

**How to read it (inside-out):**
| Step | Adds |
|---|---|
| `json('{}')` | empty object |
| + `message` | the user's question (auto-escaped) |
| + `agent_name` | constant `PA-Health-Benefit-Agent` |
| + `parameters` | nested object with `user_id`, `user_full_name` |
| + `threadid` | conversation id |

### 2.4 Point the HTTP Body at Compose
1. Click the **HTTP** action.
2. **Delete everything** in the **Body** field.
3. With the cursor in **Body**, open **Dynamic content** → under **Compose agent body**
   select **Outputs**.
4. Confirm Body now contains only `@{outputs('Compose_agent_body')}`.
5. Confirm **Headers** still has `Content-Type: application/json`.

### 2.5 Save and verify escaping
1. Click **Save**.
2. Click **Test** (top-right) → **Manually** → **Test**.
3. Trigger it with a question containing a quote, e.g.
   `Can I enroll in the "Choice Plus" plan?`
4. Open the run → click **Compose agent body** → inspect **Outputs**. You should see:
```json
{
  "message": "Can I enroll in the \"Choice Plus\" plan?",
  "agent_name": "PA-Health-Benefit-Agent",
  "parameters": { "user_id": "SCHOY", "user_full_name": "Steven Choy" },
  "threadid": ""
}
```
The `\"` confirms correct escaping.
5. Click the **HTTP** step → confirm **Status 200**.

---

## Part 3 — Topic logic: offer & send (Section 8)

### 3.1 Open the topic
1. Go to **Copilot Studio** → select your agent.
2. Left navigation → **Topics**.
3. Open the topic that calls the agent action. If your agent uses a single main topic, it may
   be named **Conversational boosting**, **Fallback**, or a custom name such as
   *Ask Benefits*.
4. The authoring canvas opens showing nodes top to bottom.

### 3.2 Confirm the agent action returns `canAnswer`
1. Locate the **Call an action** node that invokes the agent flow (`agent_httptrigger`).
2. Click it and look at the **Outputs** section — you should see `message`, `threadId`,
   and `canAnswer`.
3. **If `canAnswer` is missing:**
   - The flow's response schema is stale. Open the agent flow in Power Automate,
	 run it once (**Test → Manually**), then in the flow's **Respond to the agent** action
	 add an output named `canAnswer` (type **Boolean**) bound to the function's `canAnswer`
	 field (via **Parse JSON** on the HTTP body).
   - Save the flow, return to Copilot Studio, remove and re-add the action node so the schema
	 refreshes.

> The function returns JSON like:
> `{ "message": "...", "threadId": "conv_...", "canAnswer": false }`
> The flow must surface `canAnswer` as an output for the topic to branch on it.

### 3.3 Save the question into a variable (if not already)
You need the original user question later for the email.
1. Find where the user's question is captured (often `Activity.Text` or a topic variable).
2. If it is not already stored, add a **Set a variable value** node just before the action:
   - **Set variable:** create `Topic.UserQuestion`
   - **To value:** select **System.Activity.Text** (or the existing question variable).

### 3.4 Add the condition on `canAnswer`
1. Click the **+** below the **Call an action** node.
2. Select **Add a condition**.
3. In the condition node:
   - Left side: click the variable selector → choose the action's **canAnswer** output.
   - Operator: **is equal to**
   - Right side: click the value box → switch the type selector to **Boolean** → choose
	 **false**.
4. The node now shows two branches: the condition's **true** path and **All other conditions**
   (else).

> Result: **true** branch = the agent could NOT answer. **Else** branch = normal answer.

### 3.5 Build the "could not answer" branch
Work inside the **true** branch (`canAnswer = false`).

**a) Show the agent's apology message**
1. Click **+** inside the true branch → **Send a message**.
2. In the message box, click the **{x}** (insert variable) icon → select the action's
   **message** output.

**b) Ask the Yes/No question**
1. Click **+** below it → **Ask a question**.
2. **Enter a message:**
   `I couldn't find that in the benefits materials. Would you like me to email your question to HR?`
3. **Identify:** open the dropdown → select **Multiple choice options**.
4. Under **Options for user**, click **+ New option** → type `Yes`.
5. Click **+ New option** again → type `No`.
6. On the right, find **Save response as** → click the variable name → rename it to
   `EmailHR` (it becomes `Topic.EmailHR`).

**c) Branch on the answer**
Copilot Studio automatically creates a branch per option when you use multiple choice.
1. You should now see two paths: **Yes** and **No**.
2. If you instead see a single path, add a **Condition** node:
   `Topic.EmailHR` **is equal to** `Yes`.

**d) On the Yes path — call the email flow**
1. Click **+** in the **Yes** branch → **Call an action**.
2. Select **Send HR Email** (the flow from Part 1).
3. Fill the inputs that appear:
   | Input | Set to |
   |---|---|
   | `question` | `Topic.UserQuestion` (or `System.Activity.Text`) |
   | `user_full_name` | your user-name variable (same source as `text_3`) |
   | `user_id` | your user-id variable (same source as `text_2`) |
   | `conversation_id` | the agent action's **threadId** output |
   - For each, click the field → **{x}** → pick the variable.
4. Click **+** below the action → **Send a message**.
5. Insert the flow's **result** output (the confirmation text), or type a static message:
   `Thanks — I've emailed your question to HR. They'll follow up with you directly.`

**e) On the No path**
1. Click **+** in the **No** branch → **Send a message**.
2. Type: `No problem. Let me know if there's anything else I can help with.`

### 3.6 Build the normal branch
1. In the **All other conditions** (else) branch — meaning `canAnswer = true`:
2. Click **+** → **Send a message**.
3. Insert the action's **message** output so the user sees the normal answer.

### 3.7 Save
1. Click **Save** (top-right of the topic canvas).
2. Resolve any red error markers on nodes (usually an unset variable or empty message).

---

## Part 4 — Publish and test

### 4.1 Publish the agent
1. In Copilot Studio, click **Publish** (top-right).
2. Confirm **Publish** in the dialog.
3. Wait for "Publish succeeded".

> Changes are **not** visible in Teams until you publish.

### 4.2 Test in the Copilot Studio test pane first
1. Open the **Test your agent** panel (right side; toggle at top-right if hidden).
2. Ask a question the agent **can** answer (e.g. *What medical plans are available?*).
   - Expect: a normal answer, no email prompt.
3. Ask a question it **cannot** answer (e.g. *What is the company pet policy?*).
   - Expect: the apology, then *"Would you like me to email your question to HR?"* with
	 **Yes** / **No** buttons.
4. Click **Yes**.
   - Expect: the confirmation message.
5. Check the HR mailbox for the forwarded question.

### 4.3 Test in Teams
1. Open the agent in **Teams**.
2. Repeat the "cannot answer" question.
3. Click **Yes** and confirm the email arrives.
4. Also ask a question containing a double quote to confirm the Part 2 escaping fix.

### 4.4 Verify on the Azure side
- Function App → **Log stream** should show:
  - `canAnswer=False` for the unanswerable question.
  - `send_hr_email trigger invoked.` then `HR email sent (status 202) ...`

---

## Part 5 — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `canAnswer` not listed in action outputs | Flow response schema missing/stale | Add `canAnswer` output in **Respond to the agent**; re-add the action node in the topic |
| Condition never takes the "false" path | Comparing a string to a boolean | Ensure the value selector is set to **Boolean** `false`, not the text `"false"` |
| Agent never says it cannot answer | `NO_ANSWER` instruction missing | Add the instruction in Foundry (main checklist Section 6) and save the agent |
| Yes/No buttons do not appear | Question node not set to multiple choice | Set **Identify** = *Multiple choice options* and add **Yes**/**No** |
| Email flow fails with 401/403 | Function key missing or wrong | Re-copy the key; verify `?code=` or `x-functions-key` header |
| Email flow returns 502 `Authorization_RequestDenied` | Graph `Mail.Send` not granted | Complete main checklist Section 3 |
| Email flow returns 502 `ErrorAccessDenied` | Exchange policy excludes the mailbox | Complete/await main checklist Section 4 |
| `400 Missing required parameter 'question'` | Input name mismatch | Flow input must produce JSON key `question` (check the `addProperty` expression) |
| Function logs `Request JSON parse failed` | Body still hand-templated | Re-do Part 2 (Compose + `addProperty`) |
| Quote in question still breaks the call | HTTP Body not pointing at Compose | Confirm Body contains only `@{outputs('Compose_agent_body')}` |
| Changes not visible in Teams | Agent not published | Click **Publish** in Copilot Studio |

### Where to look at run details
- **Power Automate:** left nav → **My flows** → open the flow → **28-day run history** →
  click a run → expand each step to see **Inputs**/**Outputs**.
- **Copilot Studio:** open the topic → **Test your agent** panel → enable
  **Track between topics** to watch node-by-node execution.
- **Azure:** Function App → **Log stream**, or Application Insights →
  **Logs** with:
```kql
traces
| where timestamp > ago(30m)
| where message has "canAnswer" or message has "send_hr_email" or message has "Graph sendMail"
| project timestamp, message
| order by timestamp desc
```

---

## Appendix — expression quick reference

**Email flow body (Part 1.4):**
```
addProperty(addProperty(addProperty(addProperty(json('{}'), 'question', triggerBody()?['text']), 'user_full_name', triggerBody()?['text_1']), 'user_id', triggerBody()?['text_2']), 'conversation_id', triggerBody()?['text_3'])
```

**Agent flow body (Part 2.3):**
```
addProperty(addProperty(addProperty(addProperty(json('{}'), 'message', triggerBody()?['text']), 'agent_name', 'PA-Health-Benefit-Agent'), 'parameters', addProperty(addProperty(json('{}'), 'user_id', triggerBody()?['text_2']), 'user_full_name', triggerBody()?['text_3'])), 'threadid', triggerBody()?['text_1'])
```

**Why `addProperty` instead of typing JSON:** values are passed as *arguments*, so the runtime
JSON-escapes quotes, backslashes, and newlines automatically. Hand-typed JSON with
`"@{variable}"` breaks as soon as the user types a `"`.
