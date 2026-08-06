# Copilot Studio & Power Automate — Step-by-Step Guide (Email to HR)

Companion to **EMAIL_HR_DEPLOYMENT_CHECKLIST.md**, expanding Sections **8 and 9** into
click-by-click instructions.

**What you will build:** When the Benefits agent cannot answer a question, it asks the user
*"Would you like me to email your question to HR?"*. If the user chooses **Yes**, a
Power Automate flow calls your Azure Function, which emails the question to HR.

**Who this is for:** Someone who has never used Copilot Studio or Power Automate before.
Every step says where to click and what you should see afterwards.

**Time required:** About 45–60 minutes.

---

## Table of contents
- [Before you begin](#before-you-begin)
- [Part 0 — Orientation for first-time users](#part-0--orientation-for-first-time-users)
- [Part 1 — Create the "Send HR Email" flow (Section 9)](#part-1--create-the-send-hr-email-flow-section-9)
- [Part 2 — Add the conversation logic (Section 8)](#part-2--add-the-conversation-logic-section-8)
- [Part 3 — Publish and test](#part-3--publish-and-test)
- [Part 4 — Troubleshooting](#part-4--troubleshooting)
- [Glossary](#glossary)

---

## Before you begin

### Already completed (from the main checklist)
- Function code deployed, exposing `agent_httptrigger` (returns `canAnswer`) and `send_hr_email`.
- Function App settings, managed identity, Graph `Mail.Send`, Exchange policy configured.
- Foundry agent instructed to emit `NO_ANSWER` when it cannot answer.

### Permissions you need
- You must be a **maker** in the Power Platform environment (able to edit the agent and
  create flows). If Copilot Studio opens read-only, or you cannot create a flow, ask your
  Power Platform admin to grant you the **Environment Maker** role.
- You need access to the **Azure Portal** to copy the function key.

### Licensing — read this first
The **HTTP** action used in Part 1 is a **premium connector**. You need a
**Power Automate Premium** licence (or an equivalent Power Apps / Dynamics licence) on the
account that will run the flow.

- Without premium, the HTTP action shows a **Premium** badge and the flow fails at run time.
- **Workaround:** ask your admin for the licence, or route the call through a connector
  already approved in your tenant.

### Browser tip
Power Automate opens in **new browser tabs** from Copilot Studio. If nothing happens when
you click, check that your browser is not blocking pop-ups for these sites.

### Values to collect now
Write these down before starting; you will paste them later.

| What | Where to find it | Example |
|---|---|---|
| Function App name | Azure Portal → your Function App → **Overview** | `pa-benefits-func` |
| Function key for `send_hr_email` | Azure Portal → Function App → **Functions** → click `send_hr_email` → **Function Keys** → copy `default` | `abc123...==` |
| Environment name | Copilot Studio, top-right environment picker | `Contoso (default)` |

---

## Part 0 — Orientation for first-time users

### How the pieces fit together (read this once)
There are **two separate flows**. Knowing which is which prevents most confusion later.

```
Teams user
    |
    v
Copilot Studio agent  ──►  TOPIC (conversation script)
    |                          |
    |   1) already exists      +--► FLOW A: "call the agent"
    |                          |      calls  agent_httptrigger
    |                          |      returns message, threadId, canAnswer
    |                          |
    |   2) you build this      +--► FLOW B: "Send HR Email"
    |                                 calls  send_hr_email
    |                                 sends the email via Azure
    v
Azure Function App
```

| | Flow A | Flow B |
|---|---|---|
| Name | whatever your agent already uses | **Send HR Email** |
| Azure route | `agent_httptrigger` | `send_hr_email` |
| Status | **already exists** | **you create it in Part 1** |
| You touch it in | Part 2, Step 2.2 (only if `canAnswer` is missing) | Part 1 (build it) |

**In plain terms:** Flow A asks the agent a question. If the agent could not answer
(`canAnswer = false`), the topic offers to email HR. If the user says Yes, the topic calls
Flow B, which sends the email.

### The two websites you will use
Keep both open in separate browser tabs.

| Website | URL | What it is for |
|---|---|---|
| **Copilot Studio** | https://copilotstudio.microsoft.com | Building the agent's conversation logic |
| **Power Automate** | https://make.powerautomate.com | Building the flow that calls your Azure Function |

### Step 0.0 — Open your agent
1. Go to https://copilotstudio.microsoft.com and sign in with your work account.
2. In the left navigation, click **Agents** (older label: **Chatbots** or **Copilots**).
3. Click your Benefits agent in the list to open it.
4. You now see the agent's own left navigation: **Overview**, **Knowledge**, **Tools**,
   **Topics**, **Analytics**, **Channels**, **Settings**.

✅ **Checkpoint:** the agent's name is shown at the top and you can see the menu items above.

### Step 0.1 — Make sure both are in the SAME environment
An *environment* is a container that holds your agent and your flows. If they differ, your
agent will not be able to see the flow.

1. Open **Copilot Studio**.
2. Look at the **top-right corner**, left of your profile picture — you will see an
   environment name (for example *Contoso (default)*).
3. Click it to see the environments you can access. Note the one your agent is in.
4. Open **Power Automate** in another tab.
5. Top-right, click its environment picker and select **the same environment**.

✅ **Checkpoint:** both tabs show the same environment name in the top-right.

### Step 0.2 — Check how your agent decides what to do (IMPORTANT)
Modern Copilot Studio agents run in one of two modes. This determines whether the topic you
build in Part 2 will actually run.

1. In Copilot Studio, open your agent.
2. Click **Settings** (top-right) → **Generative AI** (some tenants label this
   **Orchestration**).
3. Check the orchestration setting:

| Setting | Meaning | Effect on this guide |
|---|---|---|
| **Generative orchestration = ON** | The AI decides which tools/topics to use | Your custom topic may be skipped — see note below |
| **Classic orchestration** (generative OFF) | The agent follows topics and trigger phrases | Part 2 works exactly as written |

> **If generative orchestration is ON**, choose one:
> - **Option A (recommended while building):** switch to **classic orchestration** so your
>   topic runs predictably after the agent action. This guide assumes Option A.
> - **Option B:** keep generative orchestration, add the flow as a **tool**, and describe in
>   the agent's instructions when to use it — e.g. *"If you cannot answer, ask the user
>   whether to email HR; if they agree, call the Send HR Email tool."* More flexible, less
>   predictable.

### Step 0.3 — Words you will see (plain English)
- **Agent** — your chatbot (older name: *copilot*).
- **Topic** — one conversation script, built as boxes (nodes) connected top to bottom.
- **Node** — a single step inside a topic, e.g. *Send a message*, *Ask a question*.
- **Tool / Action** — something the agent calls out to. Microsoft renamed **Actions** to
  **Tools**; you may see either word depending on your tenant.
- **Flow** — an automation in Power Automate. Yours sends an HTTP request to Azure.
- **Variable** — a value remembered during a conversation, e.g. `Topic.EmailHR`.
- **Dynamic content** — the picker that inserts a variable or an earlier step's output.
- **Publish** — pushes changes live; without it, Teams keeps using the old version.

---

## Part 1 — Create the "Send HR Email" flow (Section 9)

This flow receives the question from the agent and POSTs it to your Azure Function.

### Step 1.1 — Start a new flow from inside Copilot Studio
Creating it from Copilot Studio automatically makes it available to your agent.

1. Open **Copilot Studio** and select your agent.
2. In the left navigation, click **Tools**.
   - *No "Tools"? Look for **Actions** or **Plugins** — same feature, older name.*
3. Click **+ Add a tool** (older label: **+ Add an action**).
4. Choose **New tool** → **Flow**.
   - *Older tenants: **New action** → **New flow**.*
5. Power Automate opens in a **new browser tab** with a flow already started.

✅ **Checkpoint:** you see a first box titled **"When an agent calls the flow"**
(older label: *"When Power Virtual Agents calls a flow"*) and a second box
**"Respond to the agent"**.

### Step 1.2 — Add the six inputs
These are the values the agent passes in.

1. Click the first box, **When an agent calls the flow**.
2. In the panel that opens, click **+ Add an input**.
3. Choose the type **Text**.
4. A field appears with a placeholder name. Replace it by typing exactly: `question`
5. Repeat five more times, always choosing **Text**:
   - `user_full_name`
   - `user_id`
   - `conversation_id`
   - `user_email`
   - `to_address`

> Type the names **exactly** as shown (lower case, underscores). They must match what the
> Azure Function expects.

✅ **Checkpoint:** the trigger box lists six text inputs in this order:
`question`, `user_full_name`, `user_id`, `conversation_id`, `user_email`, `to_address`.

### Step 1.3 — Add the HTTP action that calls Azure
1. Hover over the **arrow** below the trigger box; a **+** circle appears. Click it.
2. Click **Add an action**.
3. Search for `HTTP`.
4. Choose the action named simply **HTTP** (globe icon, marked **Premium**).
5. Fill in the panel:
   - **URI:** `https://<FUNCTION_APP>.azurewebsites.net/api/send_hr_email?code=<FUNCTION_KEY>`
     (replace both placeholders with the values you collected)
   - **Method:** open the dropdown → **POST**
   - **Headers:** Key = `Content-Type`, Value = `application/json`
     *(if headers are not visible, click **Add new parameter** and tick **Headers**)*
   - **Body:** paste the JSON below

```json
{
  "question": "@{triggerBody()?['text']}",
  "user_full_name": "@{triggerBody()?['text_1']}",
  "user_id": "@{triggerBody()?['text_2']}",
  "conversation_id": "@{triggerBody()?['text_3']}",
  "user_email": "@{triggerBody()?['text_4']}",
  "to_address": "@{triggerBody()?['text_5']}"
}
```

> **Why `text`, `text_1`, …?** Power Automate names trigger inputs internally in the order
> you created them. `question` was first so it is `text`; `user_full_name` is `text_1`, etc.
>
> **To confirm:** click inside the Body box, open **Dynamic content** (lightning-bolt icon)
> and hover each input — a tooltip shows its internal name. If your order differs, adjust the
> JSON so each Azure field receives the correct input.

> **Safer alternative for the key:** remove `?code=<FUNCTION_KEY>` from the URI and add a
> second header instead: Key = `x-functions-key`, Value = `<FUNCTION_KEY>`. This keeps the
> secret out of URL logs.

✅ **Checkpoint:** the HTTP box shows Method `POST`, your URI, one header, and the JSON body.

### Step 1.4 — Read the function's reply (recommended)
This lets the agent display the confirmation text the function returns.

1. Click **+** below the HTTP box → **Add an action**.
2. Search `Parse JSON` → select **Parse JSON** (under *Data Operation*).
3. **Content:** click the field → **Dynamic content** → under **HTTP** choose **Body**.
4. **Schema:** click **Use sample payload to generate schema** (older label:
   *Generate from sample*), paste the text below, then click **Done**:

```json
{ "sent": true, "message": "Your question has been emailed to HR." }
```

✅ **Checkpoint:** the Parse JSON box shows a schema containing `sent` and `message`.

### Step 1.5 — Send a result back to the agent
1. Click the **Respond to the agent** box created in Step 1.1.
   - *Missing?* Click **+** → **Add an action** → search **Respond to the agent**
     (older label: *Respond to Power Virtual Agents*).
2. Click **+ Add an output** → choose **Text**.
3. Name it exactly: `result`
4. Click its value box → **Dynamic content** → under **Parse JSON** choose **message**.
   - *If you skipped Step 1.4:* choose **HTTP → Body**.

✅ **Checkpoint:** the respond box has one text output named `result` with a dynamic value.

### Step 1.6 — Name and save the flow
1. At the **top-left**, click the flow name (may say *Untitled*).
2. Type: `Send HR Email`
3. Click **Save** (top-right).
4. Wait for the confirmation banner.

✅ **Checkpoint:** the flow is named **Send HR Email** and saved without errors.

### Step 1.7 — Test the flow on its own (strongly recommended)
Testing now means that if something breaks later, you know it is *not* the flow.

1. In the Power Automate designer, click **Test** (top-right).
2. Choose **Manually** → **Test**.
3. Power Automate asks for the inputs. Type sample values:
   - `question` → `Test from Power Automate`
   - `user_full_name` → `Test User`
   - `user_id` → `TEST01`
   - `conversation_id` → `test-001`
   - `user_email` → your own work email
   - `to_address` → the HR mailbox (e.g. `OpenEnrollment@panynj.gov`; separate multiple with `;`)
4. Click **Run flow** → **Done**.
5. Watch the run. Every step should show a **green tick**.
6. Click the **HTTP** step and check **Outputs** → **Status code** should be **200**, and the
   body should read `{"sent": true, ...}`.
7. Check the HR mailbox — a test email should have arrived.

> **If a step shows a red exclamation mark**, click it and read the error. See
> [Part 4 — Troubleshooting](#part-4--troubleshooting); the most common causes are a wrong
> function key (401/403) or Graph permissions not finished (502).

✅ **Checkpoint:** the flow ran green end-to-end and a test email arrived.

### Step 1.8 — Return to Copilot Studio
1. Switch back to the Copilot Studio tab.
2. Refresh the page (F5) so the new flow is picked up.
3. Open **Tools** — **Send HR Email** should now be listed.

✅ **Checkpoint:** *Send HR Email* appears in the agent's Tools list.

---

## Part 2 — Add the conversation logic (Section 8)

Here you tell the agent: *if the answer failed, offer to email HR.*

### Step 2.1 — Open the topic that calls your agent Function
1. In Copilot Studio, open your agent.
2. Left navigation → **Topics**.
3. The list is split into your own topics and **System** topics.
4. Open the topic that calls `agent_httptrigger` (this is **Flow A**). Common names:
   - a custom topic such as *Ask Benefits*
   - **Conversational boosting** (system topic)
   - **Fallback** (system topic)
5. The **authoring canvas** opens showing a vertical chain of boxes.

> **Not sure which topic?** Open each candidate and look for a node that calls a flow/action
> matching your agent Function. That is the one.

> **What if no topic calls the Function?** Then your agent may be calling the Function as a
> **tool** under generative orchestration (see Step 0.2). In that case, either switch to
> classic orchestration and build a topic, or follow Option B in Step 0.2 and drive the
> behaviour from the agent's instructions instead.

> **Save vs Publish — the difference**
> - **Save** stores your work in the editor. Only you see it.
> - **Publish** pushes it live to Teams and other channels.
> You must do **both**: Save as you go, then Publish at the end (Part 3).

### Step 2.2 — Verify the agent action returns `canAnswer`
1. Click the node that calls your agent flow.
2. Check its **Outputs** — you need `message`, `threadId`, and `canAnswer`.

**If `canAnswer` is missing**, the flow calling `agent_httptrigger` is not returning it yet:
1. Open that flow in Power Automate.
2. Add a **Parse JSON** step after its HTTP action, using this sample:
```json
{ "message": "text", "threadId": "text", "canAnswer": true }
```
3. In that flow's **Respond to the agent** step, click **+ Add an output** → **Yes/No**
   (Boolean) → name it `canAnswer` → set its value from Parse JSON → `canAnswer`.
4. **Save** the flow.
5. Back in Copilot Studio, **delete the action node and add it again** so it picks up the new
   output.

✅ **Checkpoint:** the action node lists `canAnswer` among its outputs.

### Step 2.3 — Store the user's question for later
The email needs the original question, so save it into a variable.

1. Click the **+** just **above** the agent action node → **Variable management** →
   **Set a variable value**.
2. **Set variable:** click the box → **Create a new variable** → rename it `UserQuestion`.
3. **To value:** click the box → **System** tab → choose **Activity.Text**.

> If your topic already stores the question in a variable, skip this and use that variable
> later instead.

✅ **Checkpoint:** a *Set a variable value* node sets `Topic.UserQuestion` before the action.

### Step 2.4 — Add the branch on `canAnswer`
1. Click the **+** **below** the agent action node.
2. Choose **Add a condition**.
3. **Left box:** click it → choose the action's **canAnswer** output.
4. **Operator:** leave as **is equal to**.
5. **Right box:** click it, set the value type to **Boolean**, then choose **false**.

> ⚠️ **Common mistake:** entering the word `false` as **text**. It must be the **Boolean**
> value `false`, or the condition will never match.

6. The node now has two paths:
   - the **condition path** = the agent could NOT answer
   - **All other conditions** = the agent answered normally

✅ **Checkpoint:** the canvas shows a condition splitting into two branches.

### Step 2.5 — Build the "could not answer" branch

**a) Show the agent's apology**
1. Click **+** inside the condition (true) branch → **Send a message**.
2. In the message box, click the **{x}** icon (insert variable) → choose the action's
   **message** output.

**b) Ask the Yes/No question**
1. Click **+** below it → **Ask a question**.
2. In **Enter a message**, type:
   `I couldn't find that in the benefits materials. Would you like me to email your question to HR?`
3. Under **Identify**, open the dropdown → choose **Multiple choice options**.
4. Under **Options for user**, click **+ New option** → type `Yes`.
5. Click **+ New option** again → type `No`.
6. On the right of the node, find **Save response as**, click the variable name and rename it
   to `EmailHR`.

✅ **Checkpoint:** the question node shows two options (Yes, No) and saves to `Topic.EmailHR`.
Copilot Studio automatically creates a branch for each option.

**c) On the Yes branch — call the flow**
1. Click **+** inside the **Yes** branch → **Add a tool** (older: **Call an action**).
2. Choose **Send HR Email**.
3. Set each input by clicking the field, then the **{x}** icon (or type `{` to open the
   variable picker):

| Input | Set to | Where it comes from |
|---|---|---|
| `question` | `Topic.UserQuestion` | the variable you created in Step 2.3 |
| `user_full_name` | the user's display name | see note below |
| `user_id` | the user's employee id | see note below |
| `conversation_id` | the agent action's **threadId** output | returned by Flow A |
| `to_address` | the HR mailbox, e.g. `OpenEnrollment@panynj.gov` (separate multiple with `;`) | type it directly, or use a topic variable |

> **Where do `user_full_name` and `user_id` come from?**
> These are the same two values your existing **Flow A** already sends to Azure as
> `parameters.user_full_name` and `parameters.user_id`.
> To find them:
> 1. Open the topic and look at the **inputs** already being passed to the Flow A node —
>    they will be topic variables (e.g. `Topic.UserName`, `Topic.UserId`) or system values.
> 2. Reuse **exactly those same variables** here.
>
> If your agent does not collect them, you can use the built-in Copilot Studio values
> instead: in the variable picker choose the **System** tab and select
> **User.DisplayName** for the name. If you have no employee id available, leave `user_id`
> empty — the Azure Function treats it as optional.

4. Click **+** below the tool node → **Send a message**.
5. Either insert the flow's **result** output using **{x}**, or type a fixed message:
   `Thanks — I've emailed your question to HR. They'll follow up with you directly.`

**d) On the No branch**
1. Click **+** inside the **No** branch → **Send a message**.
2. Type: `No problem. Let me know if there's anything else I can help with.`

✅ **Checkpoint:** the Yes branch calls the flow and confirms; the No branch closes politely.

### Step 2.6 — Build the normal branch
1. Go to the **All other conditions** branch (meaning `canAnswer` was true).
2. Click **+** → **Send a message**.
3. Insert the action's **message** output with **{x}** so the user sees the normal answer.

### Step 2.7 — Save the topic
1. Click **Save** (top-right of the canvas).
2. Fix any red error icons (usually an empty message or unset variable) and save again.

✅ **Checkpoint:** the topic saves with no errors.

---

## Part 3 — Publish and test

### Step 3.1 — Publish
1. In Copilot Studio, click **Publish** (top-right).
2. Confirm in the dialog.
3. Wait for the success message.

> ⚠️ Until you publish, **Teams still runs the old version**. Publish after every change.

### Step 3.2 — Test inside Copilot Studio first
The test panel is faster than Teams for finding mistakes.

1. Open the **Test** panel (right side; if hidden, click **Test** at the top-right).
2. Ask something the agent **can** answer, e.g. *What medical plans are available?*
   - Expect a normal answer, **no** email prompt.
3. Ask something it **cannot** answer, e.g. *What is the company pet policy?*
   - Expect the apology, then the question with **Yes** / **No** buttons.
4. Click **Yes**.
   - Expect the confirmation message.
5. Check the HR mailbox — the email should have arrived.

> **Tip:** enable **Track between topics** (toggle at the top of the Test panel) to watch each
> node light up on the canvas as it runs. This makes debugging much easier.

### Step 3.3 — Test in Teams
1. Open the agent in **Teams**.
2. Ask the same "cannot answer" question.
3. Click **Yes** and confirm the email arrives.

### Step 3.4 — Confirm on the Azure side
Azure Portal → your Function App → **Log stream**. You should see:
- `canAnswer=False` for the unanswerable question
- `send_hr_email trigger invoked.`
- `HR email sent (status 202) ...`

---

## Part 4 — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Copilot Studio is read-only / cannot create a flow | Missing maker permission | Ask your admin for the **Environment Maker** role |
| Clicking "New tool" does nothing | Browser blocked the new tab | Allow pop-ups for Copilot Studio and Power Automate |
| My topic never runs | Generative orchestration is choosing its own path | See Step 0.2 — switch to classic orchestration, or expose the flow as a tool |
| `Send HR Email` not listed in Copilot Studio | Page not refreshed, or wrong environment | Refresh (F5); confirm both tabs use the same environment (Step 0.1) |
| HTTP action shows a "Premium" warning | No Power Automate Premium licence | Request the licence from your admin |
| `canAnswer` not listed in action outputs | The agent flow does not return it | Follow Step 2.2, then delete and re-add the action node |
| Condition never takes the "cannot answer" path | Compared text `"false"` instead of Boolean `false` | Re-open the condition; set the right side type to **Boolean** → `false` |
| Agent never says it cannot answer | `NO_ANSWER` instruction missing | Add it in Foundry (main checklist Section 6) and save the agent |
| Yes/No buttons do not appear | Question node not set to multiple choice | Set **Identify** = *Multiple choice options*, add **Yes** and **No** |
| Flow fails with 401 or 403 | Wrong or missing function key | Re-copy the key; check `?code=` or the `x-functions-key` header |
| Flow returns 502 `Authorization_RequestDenied` | Graph `Mail.Send` not granted | Complete main checklist Section 3 |
| Flow returns 502 `ErrorAccessDenied` | Exchange policy excludes the mailbox | Complete/await main checklist Section 4 |
| `400 Missing required parameter 'question'` | Body field names do not match | Ensure the HTTP body uses the key `question` (Step 1.3) |
| Works in the Test panel but not in Teams | Not published | Click **Publish** (Step 3.1) |

### Where to see what actually happened
- **Power Automate:** left nav → **My flows** → open **Send HR Email** (Flow B) → **28-day run
  history** → click a run → expand each step to inspect **Inputs** and **Outputs**. This
  shows the exact JSON sent to Azure and the response received.
- **Copilot Studio:** the **Test** panel with **Track between topics** enabled.
- **Azure:** Function App → **Log stream**, or Application Insights → **Logs**:

```kql
traces
| where timestamp > ago(30m)
| where message has "canAnswer" or message has "send_hr_email" or message has "Graph sendMail"
| project timestamp, message
| order by timestamp desc
```

---

## Glossary

| Term | Meaning |
|---|---|
| **Agent** | Your chatbot in Copilot Studio (previously called a *copilot*) |
| **Environment** | A container holding agents, flows and data; everything must live in the same one |
| **Topic** | A conversation script made of connected nodes |
| **Node** | One step in a topic (message, question, condition, tool call) |
| **Tool / Action** | Something the agent calls out to, such as a Power Automate flow |
| **Flow** | An automation in Power Automate |
| **Trigger** | The first step of a flow; what starts it |
| **Connector** | A pre-built integration in Power Automate (HTTP, Outlook, …) |
| **Premium connector** | A connector requiring a paid licence (HTTP is one) |
| **Dynamic content** | The picker used to insert variables or earlier step outputs |
| **Variable** | A stored value, e.g. `Topic.EmailHR` |
| **System variable** | Built-in value from Copilot Studio, e.g. `System.Activity.Text` |
| **Orchestration** | How the agent decides what to do — *classic* (topics/trigger phrases) or *generative* (AI chooses) |
| **Publish** | Makes your saved changes live for users |
