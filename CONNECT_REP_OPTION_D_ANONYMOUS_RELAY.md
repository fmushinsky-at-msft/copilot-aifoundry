# Option D — Anonymous Relay (recommended when representatives must stay anonymous)

**What this document is:** a beginner's guide to letting an employee get a **real human
answer** from HR **without ever learning who wrote it**. The employee asks; the agent cannot
answer; the question appears in an HR Teams channel as a card; a representative types the
answer; the agent delivers it back.

**Who this is for:** someone who has never configured Copilot Studio or Power Automate.
Every step says where to click and what you should see afterwards.

**Time required:** about 2 hours.
**Cost:** likely none — see [A note on Power Automate licensing](#a-note-on-power-automate-licensing).

> ## 🔒 Why this option exists
>
> If the employee must **not** see the real name of the person answering, a Teams group chat
> is disqualified — it always shows names, photos and presence, and there is no setting that
> masks it.
>
> This design keeps the human's identity out of everything the employee sees, while still
> returning a genuine human answer. It works today, in GCC, using only standard connectors
> and with no change to `function_app.py`.

---

## Table of contents

- [How to use this document](#how-to-use-this-document)
- [Your scenario — verified facts](#your-scenario--verified-facts)
- [A note on Power Automate licensing](#a-note-on-power-automate-licensing)
- [Background — how the current feature works](#background--how-the-current-feature-works)
- [How the relay works](#how-the-relay-works)
- [The 100-second rule — read before building](#the-100-second-rule--read-before-building)
- [Step D.1 — Create the HR intake channel](#step-d1--create-the-hr-intake-channel)
- [Step D.2 — Create the flow and define its inputs](#step-d2--create-the-flow-and-define-its-inputs)
- [Step D.3 — Respond to the agent FIRST](#step-d3--respond-to-the-agent-first)
- [Step D.4 — Post the card and wait for an answer](#step-d4--post-the-card-and-wait-for-an-answer)
- [Step D.5 — Add a timeout path](#step-d5--add-a-timeout-path)
- [Step D.6 — Deliver the answer anonymously](#step-d6--deliver-the-answer-anonymously)
- [Step D.7 — Wire the flow into the topic](#step-d7--wire-the-flow-into-the-topic)
- [Step D.8 — Publish and test end to end](#step-d8--publish-and-test-end-to-end)
- [Step D.9 — Brief the representatives](#step-d9--brief-the-representatives)
- [🆕 Simpler build if Asynchronous response is available](#-simpler-build-if-asynchronous-response-is-available)
- [🆕 Variant D2 — the native "Request for information" action](#-variant-d2--the-native-request-for-information-action)
- [Pros and cons](#pros-and-cons)
- [Anonymity — what it does and does not protect](#anonymity--what-it-does-and-does-not-protect)
- [Optional — Add telemetry so Power BI stays complete](#optional--add-telemetry-so-power-bi-stays-complete)
- [Troubleshooting](#troubleshooting)
- [Technical questions you are likely to be asked](#technical-questions-you-are-likely-to-be-asked)
- [Reference material](#reference-material)
- [Glossary](#glossary)
- [Sources](#sources)

---

## How to use this document

### Before you build anything

1. Read [The 100-second rule](#the-100-second-rule--read-before-building). Getting the
   action order wrong is the single most likely way to break this.
2. Check whether **Asynchronous response** exists in your environment — if it does, the
   [simpler build](#-simpler-build-if-asynchronous-response-is-available) may suit you better.
3. Decide between the Adaptive Card build (Steps D.1–D.9) and
   [Variant D2](#-variant-d2--the-native-request-for-information-action).

### What to skip on a first read

- **[Reference material](#reference-material)** — a library, not reading material.
- **[Technical questions](#technical-questions-you-are-likely-to-be-asked)** — for when you
  present this to others.
- **[Sources](#sources)** — provenance, for auditing rather than learning.

> ⚠️ **Build it against a test channel and your own account first.** Only point it at the
> real HR channel once the end-to-end test passes.

---

## Your scenario — verified facts

| Fact | Value | Why it matters |
|---|---|---|
| Cloud | **GCC** (not GCC High, not DoD) | Adaptive Cards are unavailable in DoD; GCC is fine |
| Agent channel | **Microsoft Teams** | Proactive messaging is *"fully supported"* here |
| Copilot Studio auth | **Authenticate with Microsoft** | Required for `System.User.PrincipalName` |
| User identity variable | **`System.User.PrincipalName`** | The delivery address for the answer |
| Function App | `func-hrbenefit-dev003` (Flex Consumption, Python) | Three routes; **no change needed** |
| Existing escalation | "Email HR" via `send_hr_email` | You are adding a *second* choice beside it |
| Teams Workflows app | Must be **installed and enabled** | Prerequisite for Adaptive Card actions |

### GCC portal addresses

From Microsoft's
[Copilot Studio US Government service URLs](https://learn.microsoft.com/microsoft-copilot-studio/requirements-licensing-gcc#microsoft-copilot-studio-us-government-service-urls)
table — **not** simple `.com` → `.us` swaps, so do not guess them.

| Purpose | Commercial | **Your GCC address** |
|---|---|---|
| Copilot Studio | `copilotstudio.microsoft.com` | **`gcc.powerva.microsoft.us`** |
| Power Automate | `flow.microsoft.com` | **`gov.flow.microsoft.us`** |
| Power Platform admin | `admin.powerplatform.microsoft.com` | **`gcc.admin.powerplatform.microsoft.us`** |
| Azure Portal | `portal.azure.com` | `portal.azure.us` |

⚠️ **Adaptive Cards are not available in DoD.** GCC is unaffected.

---

## A note on Power Automate licensing

`COPILOT_STUDIO_SETUP_GUIDE.md` lists Power Automate Premium as a licence you **need to
obtain** for the existing email feature — because that flow uses the **HTTP** action, which
is a premium connector. It does not confirm the licence was granted, or to whom.

**This option is likely cheaper:**

| Feature | Action used | Connector tier |
|---|---|---|
| `send_hr_email` (existing) | **HTTP** | **Premium** |
| This option | Teams: post card and wait; post message | **Standard** |

The Teams connector is **standard**, so this may need **no new licence at all**.

⚠️ **Verify rather than assume.** Open the flow designer and look for a **Premium** badge on
the actions you plan to use — no badge means no premium requirement for that action.

Separately, Microsoft's
[Agent flows FAQ](https://learn.microsoft.com/microsoft-copilot-studio/flows-faqs) notes that
agent flows are *"billed in Copilot Studio based on usage"* and are *"not included
entitlements in Power Automate"* — a different axis from connector tiers.

---

## Background — how the current feature works

```
Teams user
	|
	v
Copilot Studio agent (HR Benefits)
	|
	+--► FLOW A: calls  agent_httptrigger
	|         returns { message, threadId, canAnswer }
	|
	|    if canAnswer = false, the topic offers a choice:
	|
	+--► "Email HR"            ──► FLOW B: calls send_hr_email   ← already built
	+--► "Connect to a rep"    ──► THIS DOCUMENT                 ← you are adding this
	v
Azure Function App  (func-hrbenefit-dev003)
	|
	v
Microsoft Foundry (agent + model)
```

**The key variable is `canAnswer`.** When it is `false`, the agent could not answer and your
topic shows the choices. You are adding a **second option** to a decision point that already
exists.

The Function App exposes exactly three routes:

| Route | Purpose |
|---|---|
| `agent_httptrigger` | Ask the Foundry agent a question |
| `send_hr_email` | Email the question to HR via Microsoft Graph |
| `submit_feedback` | Record 👍 / 👎 |

✅ **This option requires no change to `function_app.py`.**

---

## How the relay works

```
Employee (Teams)
	|  asks a question; agent cannot answer
	v
Copilot Studio topic
	|  calls the flow, then immediately tells the user "we're on it"
	v
FLOW
	|
	+--► posts an Adaptive Card into the HR channel
	|         "...and wait for a response"
	|                                   |
	|     an HR rep types the answer ───+
	|
	+--► the answer is sent back to the employee as a proactive message
			  Post as: Microsoft Copilot Studio agent
			  Post in: Chat with agent          ◄── recommended
			  (fallback: Post as Flow bot / Chat with Flow bot)
```

The employee sees a message from **the agent**. The representative's name appears nowhere in
what the employee receives.

---

## The 100-second rule — read before building

This is the single most important constraint, and getting it wrong is the most likely way to
break this design.

- An agent flow must **respond to the agent within 100 seconds**, or it fails with
  `FlowActionTimedOut`.
- A human will not answer within 100 seconds.

> **Note on the number.** General Power Automate documentation cites a 120-second limit for
> synchronous requests, but the Copilot Studio agent-flow documentation is more specific and
> stricter: *"Respond to the agent within the 100 second action limit."* Design for **100
> seconds**.

**The resolution:** actions placed **after** the response action keep running:

> *"Actions in the flow that need to run longer can be placed after the **Respond to the
> agent** action to continue to run up to the flow run duration limit of 30 days."*

So the flow must be ordered like this:

| Order | Action | Why |
|---|---|---|
| 1 | **When an agent calls the flow** (trigger) | Receives the question |
| 2 | **Respond to the agent** — "Your question has been sent" | **Must happen inside 100 s** |
| 3 | Post the Adaptive Card and wait for a response | Runs *after* the response; can take hours |
| 4 | Deliver the answer to the employee | Runs whenever the rep replies |

⚠️ **If you put the waiting step before the response step, the flow times out and the feature
fails.** Order matters more than anything else in this document.

**Maximum wait:** a flow run can last **30 days**; pending steps time out after that. Set a
shorter, explicit timeout — see [Step D.5](#step-d5--add-a-timeout-path).

> 💡 **There may be a simpler way.** If your environment supports **Asynchronous response**,
> see [Simpler build if Asynchronous response is available](#-simpler-build-if-asynchronous-response-is-available).
> The respond-first pattern below works in **both** cases, which is why it remains the
> default.

---

## Step D.1 — Create the HR intake channel

⚠️ **Prerequisite:** Microsoft's adaptive-card tutorial states you need **Microsoft Teams
with the Workflows app installed**. Workflows is available in **GCC** (but not GCC High or
DoD). If cards never appear, verify the Workflows app is enabled in your Teams admin center
before debugging the flow itself.

1. In Teams, go to the HR team.
2. Click **⋯** next to the team name → **Add channel**.
3. Name it, e.g. `Benefits Questions (Anonymous Relay)`.
4. Choose **Standard**.

⚠️ **Standard, not private.** Microsoft documents that posting as a Flow bot in **private
channels** is *"under development."* Shared and standard channels are supported. Choosing
private here will cost you hours of debugging.

5. Add the HR representatives as members.

✅ **Checkpoint:** the channel exists, is standard, and you can post in it manually.

---

## Step D.2 — Create the flow and define its inputs

1. In Copilot Studio (`gcc.powerva.microsoft.us`), open your agent → **Topics** → open the
   topic with the `canAnswer` check.
2. Find the **Question** node offering the "Email HR" choice, click **+ New option**, and
   type `Connect to a representative`.

   > ⚠️ **Teams caps multiple-choice options at six** (hero card limit). Going from one to
   > two is fine; it is a hard ceiling if you later add more paths.

   > 💡 **Just because you can add six does not mean you should.** Every extra choice is a
   > decision the user has to make while already frustrated. Two is usually right.

3. In the new branch: **+ (Add node)** → **Add a tool** → **Create a flow**.
4. In Power Automate, click the **When an agent calls the flow** trigger node.
5. Click **+ Add an input** → **Text**, four times, naming them exactly:

| Input | Carries |
|---|---|
| `Question` | What the employee asked |
| `UserEmail` | Where the answer will be delivered |
| `UserName` | Shown to HR only |
| `ConversationId` | Correlation for telemetry |

> **Action names have changed over time.** The current names are **When an agent calls the
> flow** and **Respond to the agent**. Older documentation says *"When Copilot Studio calls a
> flow"* and *"Respond to Copilot"*. Same actions.

⚠️ **The flow must live in a solution.** Microsoft states: *"To be available to agents, flows
must be stored in a solution in the same Power Platform environment."* Creating the flow from
inside Copilot Studio (step 3) handles this. If you build it from **My flows** instead, add
it to a solution afterwards or the agent will not see it.

✅ **Checkpoint:** four text inputs, spelled exactly as above.

---

## Step D.3 — Respond to the agent FIRST

This is the step that satisfies the 100-second rule. Do it before adding anything else.

1. Click **+ New step**.
2. Search for the **Copilot** connector and select **Respond to the agent**.
3. Add one text output named `Status`.
4. Set its value to: `sent`

⚠️ **Check that Asynchronous response is Off.** Select the **Respond to the agent** action →
**Settings** → under **Networking**, confirm **Asynchronous response** is **Off**. Flows
created from Copilot Studio default to Off, but verify it. With it On in an environment that
does not support the newer callback feature, the agent shows *"Something unexpected happened.
We're looking into it. Error code: 3000."*

✅ **Checkpoint:** the response action sits immediately after the trigger, before any waiting
step.

---

## Step D.4 — Post the card and wait for an answer

1. Click **+ New step** — making sure it lands **below** the response action.
2. Search for **Post an adaptive card to a Teams channel and wait for a response**.

   ⚠️ It must be the **"and wait for a response"** variant. The plain "post" action cannot
   collect input — Microsoft documents that non-waiting cards *"return an error for all
   button actions except OpenURL."*

3. Set **Team** and **Channel** to the channel from Step D.1.
4. In **Message**, paste this Adaptive Card JSON:

```json
{
  "type": "AdaptiveCard",
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "version": "1.4",
  "body": [
	{
	  "type": "TextBlock",
	  "text": "Benefits question needs an answer",
	  "weight": "Bolder",
	  "size": "Medium",
	  "wrap": true
	},
	{
	  "type": "TextBlock",
	  "text": "From: @{triggerBody()['text_2']}",
	  "isSubtle": true,
	  "wrap": true
	},
	{
	  "type": "TextBlock",
	  "text": "@{triggerBody()['text']}",
	  "wrap": true
	},
	{
	  "type": "Input.Text",
	  "id": "answer",
	  "placeholder": "Type the answer the employee will receive",
	  "isMultiline": true
	}
  ],
  "actions": [
	{ "type": "Action.Submit", "title": "Send answer" }
  ]
}
```

> **Do not hand-type the `@{triggerBody()...}` parts.** Delete the placeholder text and use
> the **lightning bolt** icon to insert `Question` and `UserName` from dynamic content. The
> internal names (`text`, `text_2`) vary by flow.

> ### How the answer gets back out of the card
>
> This is the part beginners most often get stuck on.
>
> **The `id` of an `Input.Text` becomes the name of the dynamic-content token.** In the card
> above the input is `"id": "answer"`, so after the card action a dynamic value named
> **`answer`** appears in the lightning-bolt picker. That is what you insert in
> [Step D.6](#step-d6--deliver-the-answer-anonymously).
>
> Microsoft's [lead collection sample](https://learn.microsoft.com/power-automate/lead-collection-sample)
> shows the same mechanism: each `Input.Text` `id` becomes a "Response **output**" token.
>
> ⚠️ **`submitActionId` is different.** Microsoft's proactive-card documentation says *"To use
> the response from the recipient, select **submitActionId**… the value of this variable is
> the `title` of the action the user selected."* That tells you **which button** was pressed —
> not what was typed. You want the **`answer`** token, not `submitActionId`.

> ### ⚠️ Adaptive Card schema version — Teams caps at 1.5
>
> Microsoft's [Adaptive Cards overview](https://learn.microsoft.com/microsoft-copilot-studio/adaptive-cards-overview)
> documents host-specific limits:
>
> | Host | Max schema version |
> |---|---|
> | **Microsoft Teams** | **1.5** |
> | Bot Framework Web Chat | 1.6 (but no `Action.Execute`) |
>
> The card above specifies `"version": "1.4"`, safely inside the Teams limit — **leave it
> alone unless you have a reason to change it.**
>
> ⚠️ **The trap:** the [Adaptive Cards Designer](https://adaptivecards.io/designer/) will
> happily emit a **1.6** card. Paste that into a Teams-bound flow and elements may silently
> fail to render. If you edit the card visually, set the target version to **1.5 or lower**
> before copying the JSON back.

> ### 💡 If you ever add a second button
>
> The card above has one `Action.Submit`. If you add more (for example *Send answer* vs
> *Cannot answer*), Microsoft advises that **each submit action should carry unique
> identifying data**:
>
> > *"Make sure each submit action includes unique data that identifies the card or action.
> > Using card- or action-specific unique data reduces the risk of unexpected behavior when
> > multiple cards are visible or when a user selects a button on an earlier card."*
>
> This matters because your HR channel will accumulate **many similar-looking cards**.
> Details: [Submit button behavior with consecutive cards](https://learn.microsoft.com/microsoft-copilot-studio/authoring-ask-with-adaptive-card#submit-button-behavior-for-agents-with-consecutive-cards).

5. Set **Update message** to: `Answer sent to the employee.`

⚠️ Configure the update message. Without it the card resets and looks unanswered, and a
second representative will answer the same question.

✅ **Checkpoint:** the card action is *below* the response action, and has a multiline text
input plus a submit button.

---

## Step D.5 — Add a timeout path

Without this, an unanswered question hangs for 30 days and the employee is never told.

1. Click the **…** menu on the card action → **Settings**.
2. Set **Timeout** to an ISO 8601 duration — `PT8H` means 8 hours.
3. Click **Done**.
4. Add a **Post message in a chat or channel** action.
5. Click its **…** menu → **Configure run after** → tick **has timed out** (and untick **is
   successful**).
6. Configure it as in Step D.6, with a message such as:

   > `HR did not respond to your question within 8 hours. Your question has been recorded and someone will follow up by email.`

✅ **Checkpoint:** a branch exists that runs only when the card times out.

---

## Step D.6 — Deliver the answer anonymously

This is the step that produces the anonymity. **There are two ways, and the first is
better** — it is Microsoft's officially documented *proactive message* pattern.

### Option 1 (recommended) — deliver as the agent itself

Documented in
[Send proactive Microsoft Teams messages](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message).
The answer arrives from **your benefits agent**, in the same chat the employee was already
using.

1. Add a **Post message in a chat or channel** action after the card action.
2. Configure:

| Field | Value | Why |
|---|---|---|
| **Post as** | `Microsoft Copilot Studio agent` | **The anonymity control**, and it looks like the agent |
| **Post in** | `Chat with agent` | The employee's existing agent chat |
| **Agent** | your HR Benefits agent | Which agent it appears to be from |
| **Recipient** | the `UserEmail` input | Who receives it |
| **Message** | see below | The answer |

✅ **Why this is better than the Flow bot:** the reply lands in the conversation the employee
already has open, rather than in a separate "Flow bot" chat they must go find.

⚠️ **Prerequisites Microsoft states explicitly.** An agent **cannot** deliver a proactive
message if the recipient:
- has not **installed** the agent in Teams,
- has **uninstalled** or **blocked** it, or
- lacks permission to chat with it (you must [share the agent](https://learn.microsoft.com/microsoft-copilot-studio/admin-share-bots)).

In your scenario the employee *just used the agent*, so it is installed.

⚠️ **Other documented limitations:**
- Proactive messages **can only go to a personal chat with the agent** — not to channels.
- The flow **must be in the same environment** as the agent.
- Proactive messages **do not appear in conversation transcripts or analytics session data.**
  This is why the telemetry event below matters.
- If the agent is disconnected and reconnected to Teams, users must reinstall it before
  proactive messages resume.

> **Useful advanced options** (under **Show advanced options**):
>
> | Option | What it does |
> |---|---|
> | **Label as notification** | Prefixes "Notification via" before the agent name |
> | **If the chat with the agent is active** | Send / Don't send and succeed (`300`) / Don't send and fail |
> | **If the agent is not installed** | Fail / Succeed with status code (`100`) |
>
> Status codes: `200` delivered, `100` agent not installed, `300` recipient in an active
> conversation. Branch on these to log failures rather than losing answers silently.

### Option 2 (fallback) — deliver as the Flow bot

Use this if **Post as → Microsoft Copilot Studio agent** is unavailable in your tenant, or if
the agent-installed prerequisite is a problem.

| Field | Value |
|---|---|
| **Post as** | `Flow bot` |
| **Post in** | `Chat with Flow bot` |
| **Recipient** | the `UserEmail` input |

⚠️ **`Post as` must never be `User`.** That sends the message as *the account signed in to
the Teams connector* — usually the flow owner — and anonymity is lost immediately. This is
the single most likely configuration mistake.

### The message body (either option)

3. For **Message**, use text plus the card's response:

   ```
   HR has answered your question:

   <insert the "answer" output from the adaptive card>

   If you need more help, just ask me again.
   ```

   Insert the answer using the lightning bolt → the `answer` field from the card action.

⚠️ **Do not soften "HR has answered your question."** Microsoft's Responsible AI guidance
requires that agents *"make clear when the user is interacting with an agent and when they're
receiving a response from a human."* Hiding **who** answered is fine; obscuring **that a
human answered** is not.

✅ **Checkpoint:** the message is addressed to `UserEmail` and posts as either
`Microsoft Copilot Studio agent` or `Flow bot` — **never** as `User`.

4. Rename the flow to `Anonymous HR Relay` and click **Save**.

---

## Step D.7 — Wire the flow into the topic

1. Return to Copilot Studio and **reload the page**.
2. In your branch: **+ (Add node)** → **Add a tool** → **Anonymous HR Relay**.
3. Map the inputs:

| Flow input | Map to |
|---|---|
| `Question` | your question variable, e.g. `Topic.UserQuestion` |
| `UserEmail` | `System.User.PrincipalName` |
| `UserName` | `System.User.DisplayName` |
| `ConversationId` | `System.Conversation.Id` |

⚠️ **`UserEmail` must not be blank.** It is the delivery address for the answer. If the agent
is not authenticated, `System.User.PrincipalName` is empty and there is nowhere to send the
reply. This is the same dependency your `send_hr_email` feature already has.

> **Why `PrincipalName` and not `Email`?** Both exist, but your other flows already use
> `System.User.PrincipalName` (see `EMAIL_HR_DEPLOYMENT_CHECKLIST.md`, Section 9). Staying
> consistent avoids a class of bug where one flow works and another silently receives a blank.

4. Add a **Send a message** node after it:

   > `I've sent your question to the HR team. You'll get an answer here, usually within a few hours.`

⚠️ **Match the wording to your delivery choice.** If you used **Post as → Microsoft Copilot
Studio agent**, the reply arrives in *this same chat* and the wording above is correct. If you
used the **Flow bot** fallback, change it to *"you'll get an answer as a direct message from
Flow bot"* — otherwise users will not know where to look.

✅ **Checkpoint:** the branch calls the flow, then confirms to the user.

---

## Step D.8 — Publish and test end to end

1. **Save**, then **Publish**.
2. In Teams, ask the agent an unanswerable question and choose **Connect to a representative**.
3. Confirm you get the "sent" confirmation **within a few seconds** — this proves the
   100-second rule is satisfied.
4. Check the HR channel for the card.
5. As a representative, type an answer and click **Send answer**.
6. As the employee, check for the reply.

✅ **Checkpoint — all five must be true:**
- The confirmation appeared immediately, not after a long pause.
- The card reached the HR channel with the question and the employee's name.
- The card updated to `Answer sent to the employee.` after submission.
- The employee received the answer **from the agent** (or Flow bot) — not from a named person.
- **Nowhere in the employee's Teams client does the representative's name appear.**

⚠️ Verify the last point deliberately. Click the sender, open the profile, and confirm it
resolves to the bot and not to a person.

---

## Step D.9 — Brief the representatives

Anonymity is a *convention* as much as a configuration. It survives only if the humans
cooperate.

Tell representatives:
- **Do not sign your answer.** Typing `— Jane` in the answer box defeats the entire design.
- **Do not follow up from your own mailbox or start a Teams chat** with the employee.
- Everything you type in the card goes verbatim to the employee.
- Agree who answers, so one person claims each card. Only the **first** submission counts.

---

## 🆕 Simpler build if Asynchronous response is available

Microsoft has added
**[asynchronous response support for agent flows](https://learn.microsoft.com/microsoft-copilot-studio/flow-asynchronous-response)**.
Where supported, the flow can run past two minutes and **call back to the agent when it
finishes** — which removes the need for the respond-first ordering *and* the separate
proactive-message delivery step.

### Step 1 — Check whether you have it

1. Open any agent flow in Power Automate (`gov.flow.microsoft.us`).
2. Select the **Respond to the agent** action.
3. Open **Settings** → **Networking**.
4. Look for an **Asynchronous response** toggle.

| What you see | What it means |
|---|---|
| Toggle **present** | ✅ Your environment supports it — continue below |
| Toggle **absent** | ❌ Not supported — use the respond-first build in Steps D.1–D.9 |

⚠️ **This requires an environment on the
[new Power Automate infrastructure](https://learn.microsoft.com/power-automate/environment-architecture).**
Do not assume you have it because the feature exists.

### Step 2 — Understand what changes

| | Respond-first build (Steps D.1–D.9) | **Async build** |
|---|---|---|
| Ordering constraint | **Critical** — response must precede the wait | None — normal top-to-bottom order |
| How the answer returns | A separate **proactive message** action | The flow's **own return value** to the agent |
| Where the answer appears | Agent chat (via proactive message) | **Agent chat, as a normal agent reply** |
| Steps required | D.3 + D.6 both needed | D.6 can be **removed entirely** |
| Works without the feature | ✅ Yes | ❌ No |

> **The real gain:** the answer becomes an ordinary agent response rather than a
> proactively-pushed message. That sidesteps the agent-installed prerequisite, the `100`/`300`
> status codes, and the "which chat does the reply land in?" confusion.

### Step 3 — Build it

Follow **Steps D.1 and D.2 unchanged** (create the channel, create the flow, define the four
inputs). Then:

1. Add the **Post an adaptive card to a Teams channel and wait for a response** action
   **first** — there is no ordering constraint now. Configure it exactly as in
   [Step D.4](#step-d4--post-the-card-and-wait-for-an-answer), including the same card JSON,
   the `answer` input id, and the **Update message**.
2. Add the timeout path as in [Step D.5](#step-d5--add-a-timeout-path). Still required —
   async removes the 100-second limit, not the 30-day one.
3. Add **Respond to the agent** **at the end** of the flow.
4. Add a text output named `Answer` and set it to the **`answer`** token from the card.
5. Select the **Respond to the agent** action → **Settings** → **Networking** → turn
   **Asynchronous response** **On**.
6. Save and publish the flow.

Flow shape:

```
When an agent calls the flow
	|
	+--► Post adaptive card to channel AND WAIT   (hours)
	|          |
	|     HR rep types the answer
	|
	+--► Respond to the agent   [Asynchronous response = On]
			 Answer = <answer token from the card>
```

### Step 4 — Wire it into the topic

1. In Copilot Studio, add the flow as a tool exactly as in
   [Step D.7](#step-d7--wire-the-flow-into-the-topic), mapping the same four inputs.
2. Add a **Send a message** node that displays the flow's `Answer` output:

   > `HR has answered your question:` + the `Answer` output

⚠️ **The Responsible AI disclosure still applies.** The reply now looks exactly like an agent
answer, so the wording must still say a human wrote it.

3. Add a message *before* the flow call so the user is not left waiting silently:

   > `I've sent your question to the HR team — I'll reply here as soon as they answer.`

### Step 5 — Test the behaviour that differs

Beyond the normal end-to-end test, check specifically:

| Test | Expected |
|---|---|
| Employee sends another message while waiting | Microsoft: *"the flow runs to completion, but the agent responds to the user's latest request without waiting"* — the answer still arrives afterwards |
| Answer arrives | In the **agent conversation**, as a normal agent reply |
| Nobody answers within the timeout | The timeout branch fires |
| Rep's name anywhere | ❌ Must not appear |

⚠️ **Documented channel limits:** the callback is *"fully supported in Microsoft Teams"*, but
*"callbacks aren't supported for Microsoft 365 Copilot and telephony channels."* Teams is your
channel, so this is fine — but do not reuse this pattern on those channels.

### If you want the agent to respond immediately instead

Microsoft documents a third shape: *"If your environment supports asynchronous response but
you want the agent to respond immediately, **remove the Respond to the agent action** from the
flow. The agent then responds immediately after it successfully triggers the flow."*

That returns you to needing a proactive message for delivery — i.e. the original Step D.6. Use
it only if you want the confirmation to be instant *and* are content with proactive delivery.

⚠️ **In an environment without async support**, Microsoft warns: *"the agent might receive a
'flow completed' response immediately while the flow continues to run in the background."*
That would silently break this design — which is why Step 1 is a hard gate.

---

## 🆕 Variant D2 — the native "Request for information" action

Copilot Studio has a **built-in action** that does most of what Steps D.4–D.5 build by hand:
**[Request for information (RFI)](https://learn.microsoft.com/microsoft-copilot-studio/flows-request-for-information)**,
under **Human review** in the agent-flow designer.

It pauses the flow, emails designated reviewers, collects structured input, and resumes with
their answers as dynamic content. Configure a **Title**, **Message**, **Assigned to**, and
typed inputs (Text, Yes/No, Email, Number, Date — with optional fields, placeholder text, and
single- or multi-select dropdowns).

| | Card build (Steps D.4–D.5) | **RFI action (D2)** |
|---|---|---|
| Where HR responds | Teams channel card | **Outlook email** |
| Setup effort | Hand-written JSON, timeout branch | A few fields in the designer |
| Typed/validated inputs | Manual | ✅ Built in |
| Shared visible queue | ✅ Whole channel sees it | ❌ Individual emails |
| First response wins | ✅ | ✅ |
| Anonymity to the employee | ✅ (delivery step unchanged) | ✅ (delivery step unchanged) |

⚠️ **Constraints Microsoft states explicitly:**
- *"All requests are currently sent via **Outlook only**."*
- *"Requests **can't be sent to users outside of your tenant**."*
- **Known issue:** outputs can come back wrapped in `{{ }}` — *"ensure that input names are
  configured without spaces."*

> **Which to choose?** If HR lives in Outlook and you want the simplest build, D2 is less work
> and gives validated inputs for free. If you want a **visible shared queue** the whole HR team
> can triage, stay with the card build. The anonymous delivery step is identical either way.
>
> Related: [Multistage and AI approvals](https://learn.microsoft.com/microsoft-copilot-studio/flows-advanced-approvals)
> (preview) if an answer ever needs sign-off before reaching the employee.

---

## Pros and cons

**✅ Pros**

| Advantage | Detail |
|---|---|
| **Anonymous by design** | Anonymity comes from the transport, not a setting that can fail open |
| **Closes the loop** | The answer reaches the employee |
| **Answer can arrive from the agent** | Officially documented proactive-message pattern |
| Likely no new licence | Teams connector actions are standard, not premium |
| No code change | `function_app.py` untouched |
| No authentication change | Keeps "Authenticate with Microsoft" — `send_hr_email` unaffected |
| Human answers, bot delivery | Real expertise, no identity exposure |
| Built-in timeout | The employee is told when nobody responds |
| Auditable | Flow run history records who answered what |
| Delivery status codes | `200` / `100` / `300` let you handle failures explicitly |
| Reversible | Delete the flow and the topic branch |

**❌ Cons**

| Limitation | Consequence |
|---|---|
| **Ordering is fragile** | Response must precede the wait, or the flow times out ([Step D.3](#step-d3--respond-to-the-agent-first)) |
| **Invisible to Copilot Studio analytics** | Proactive messages do **not** appear in transcripts or session data |
| **Requires the agent to be installed** | Proactive delivery fails (status `100`) if the employee removed the agent |
| One round trip per card | No follow-up question in the same thread |
| First response wins | Later submissions ignored |
| Card submits once | A rep cannot revise an answer |
| No routing | Every rep sees every card |
| Channel noise at volume | Microsoft names this — built-in connectors *"own the delivery channel."* See [the CAT post on custom human-in-the-loop](https://microsoft.github.io/mcscatblog/posts/human-in-the-loop-custom-connector/) |
| 30-day ceiling | Mitigated by the timeout in [Step D.5](#step-d5--add-a-timeout-path) |
| Anonymity is conventional | One rep signing their name undoes it |
| Not in DoD | Adaptive cards unsupported there. **GCC is fine** |

**Choose this when:** anonymity matters and you want a complete question-and-answer loop.

**Avoid it when:** you need genuine back-and-forth conversation, or you cannot brief
representatives on not signing their answers.

> ⏰ **Consider an operating-hours check.** Microsoft's
> [Alternate escalation paths](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-alternate-escalation-paths)
> guidance recommends checking availability *before* offering escalation. A business-hours
> condition ahead of the choice — offering only "Email HR" outside working hours — prevents an
> employee asking at 22:00 and waiting for the 8-hour timeout.

---

## Anonymity — what it does and does not protect

Be precise with stakeholders, or you will over-promise.

### What is genuinely hidden

✅ The employee does not see the representative's name, photo, presence or contact details.
✅ There is no clickable profile leading back to the person.
✅ The employee cannot start a direct chat with whoever answered.

### What is NOT hidden

❌ **The employee's identity is fully visible to HR.** Deliberate — HR needs to know who is
asking. Anonymity here is **one-directional**.

❌ **Audit, compliance and eDiscovery still see everything.** Teams messages, channel posts and
flow run histories are retained and discoverable. In a government tenant this is a
**requirement**, not a leak.

❌ **Administrators can trace it.** Power Automate run history shows exactly which account
submitted which card.

❌ **Writing style is not anonymised.** In a small HR team, colleagues recognise each other's
phrasing.

> **State it accurately to employees.** Something like: *"Your question is answered by a member
> of the HR benefits team. Individual responders are not identified."* That is true.
> *"Completely anonymous"* is not.

> ⚠️ **Microsoft's Responsible AI guidance makes disclosure a requirement.** The
> [onboarding-agent architecture](https://learn.microsoft.com/power-platform/architecture/solution-ideas/onboarding-agent)
> states agents *"should make clear when the user is interacting with an agent and when they're
> receiving a response from a human."* Anonymising **who** answered is fine. Obscuring **that a
> human answered** is not.

### The human factor

Every technical control here can be undone by one person signing their name.
[Step D.9](#step-d9--brief-the-representatives) is not optional — it is load-bearing.

---

## Optional — Add telemetry so Power BI stays complete

Consider recording that a representative was requested. Without it, your Power BI dashboard
shows failed answers and emails sent — but escalations become invisible, and the deflection
analysis silently understates demand.

⚠️ **For this option telemetry is close to mandatory.** Microsoft documents that *"proactive
messages don't appear in conversation transcripts or analytics session data."* So the answer
delivered back to the employee leaves **no trace** in Copilot Studio analytics. Without your
own event, the entire escalation path is invisible to reporting.

### Two ways to do it

| Approach | Effort | Where it lands |
|---|---|---|
| **From Power Automate** | Low — no code change | Works, since a flow is involved |
| **From the Function** | Small code change | Consistent with the five existing events |

### What the event should look like

| Dimension | Value |
|---|---|
| `agentLabel` | The caller-supplied display name |
| `question` | The question that could not be answered (truncated) |
| `conversationId` | Join key to `AgentInteraction` |
| `userId`, `userName` | Who asked |
| `method` | `relay` |

⚠️ **Two behaviours of the existing telemetry code:**

1. `track_event()` **merges measurements into `customDimensions`**, so `customMeasurements` is
   always empty. Every KQL query must read from `customDimensions`.
2. `_clean_dimensions()` **drops `None` values entirely** — the key will be absent, and
   `tostring()` on a missing key yields `""`, not `null`.

Both are already documented in `ANALYTICS_KQL_QUERIES.md` and `POWERBI_DASHBOARD_GUIDE.md`.

### KQL to verify it later

```kql
customEvents
| where timestamp > ago(7d)
| where name == "RepresentativeRequested"
| extend
	AgentLabel     = tostring(customDimensions.agentLabel),
	Question       = tostring(customDimensions.question),
	ConversationId = tostring(customDimensions.conversationId),
	Method         = tostring(customDimensions.method)
| project timestamp, AgentLabel, Question, ConversationId, Method
| order by timestamp desc
```

> **Alternative worth evaluating:** the
> [Power CAT Agent Insights Hub](https://github.com/microsoft/Power-CAT-Copilot-Studio-Kit/blob/main/AGENT_INSIGHTS_HUB.md)
> aggregates App Insights telemetry into a prebuilt dashboard. Since your Function already
> writes to App Insights, it may give you much of the Power BI dashboard's value without
> building one — **if** it is available in GCC, which is unverified.

> This is deliberately **not implemented yet** — it is a separate decision.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Agent shows an error, or hangs, then fails | The waiting step runs **before** the response | Move **Respond to the agent** directly after the trigger ([Step D.3](#step-d3--respond-to-the-agent-first)) |
| `FlowActionTimedOut` | Flow took over 100 seconds to respond | Same fix — respond first, wait afterwards |
| `Error code: 3000` | Asynchronous response is On in an unsupported environment | Response action → **Settings** → **Networking** → **Off** |
| Card posts, but buttons error | Used the plain "post" action | Use **"…and wait for a response"** |
| Employee sees a person's name as sender | **Post as** set to `User` | Set to `Microsoft Copilot Studio agent` or `Flow bot` ([Step D.6](#step-d6--deliver-the-answer-anonymously)) |
| Answer never arrives; status `100` | Employee has not installed / has removed the agent | Use the Flow bot fallback, or ensure the agent is installed and shared |
| Answer never arrives; status `300` | Employee is in an active chat with the agent | Set **If the chat with the agent is active** to **Send** |
| Employee never receives the answer | Looking in the wrong chat | Depends on your [Step D.6](#step-d6--deliver-the-answer-anonymously) choice — make the confirmation message say which |
| Card never appears | Private channel, or Workflows app not enabled | Use a **standard** channel; check the Workflows app in Teams admin center |
| Card looks unanswered after submitting | **Update message** not configured | Set **Update message** ([Step D.4](#step-d4--post-the-card-and-wait-for-an-answer)) |
| Two reps answer the same question | First response wins; card reset | Configure the update message; brief the team |
| `OperationTimedOut` | Nobody answered | Expected — add the timeout branch ([Step D.5](#step-d5--add-a-timeout-path)) |
| Question text empty on the card | Hand-typed `triggerBody()` | Re-insert via the lightning bolt icon |
| Rep's name appears in the answer | The rep signed it | Brief them ([Step D.9](#step-d9--brief-the-representatives)) |
| `FlowActionBadRequest` | Flow inputs/outputs changed without refreshing | Reload Copilot Studio, re-map the inputs, republish |
| Escalations missing from analytics | Proactive messages excluded from transcripts | Expected — add the telemetry event |
| Flow not listed in Copilot Studio | Page not reloaded, or flow not in a solution | Reload; confirm the flow is in a solution in the same environment |
| RFI output wrapped in `{{ }}` (D2) | Input name contains spaces | Rename inputs without spaces |
| Users still on an old version after publishing | **Teams caches agent updates** | See [Best Practices for Deploying Agents in Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment-ux/) |
| `SystemError` in Teams | Teams using a stale published version | Republish; or disable/re-enable the app in Teams admin center; or toggle the Teams channel off and on. See [known limitations](https://learn.microsoft.com/microsoft-copilot-studio/publication-add-bot-to-microsoft-teams#known-limitations) |
| New option not visible in Teams | Teams cached the old agent | Same as above |

---

## Technical questions you are likely to be asked

**Q: Does this require changing the Azure Function?**
No. This option is configuration-only. The optional telemetry event is the only code change,
and it is not required for the feature to work.

**Q: Will this break the existing "Email HR" feature?**
No. It adds a branch beside it on the same Question node.

**Q: Why respond to the agent before doing the work? That seems backwards.**
Because an agent flow must answer within **100 seconds** or fail with `FlowActionTimedOut`,
and a human will not answer that fast. Microsoft explicitly supports this pattern: actions
placed after **Respond to the agent** keep running for up to 30 days. You are acknowledging
receipt, not reporting completion.

**Q: I heard flows can now run asynchronously — is the respond-first pattern obsolete?**
Possibly, for you. See
[Simpler build if Asynchronous response is available](#-simpler-build-if-asynchronous-response-is-available).
It requires an environment on the new Power Automate infrastructure — check for the toggle
before relying on it. The respond-first pattern works either way.

**Q: Can the answer come back from the agent instead of some other bot?**
Yes, and it should. Use **Post as → Microsoft Copilot Studio agent** with **Post in → Chat
with agent**. The one prerequisite is that the employee has the agent installed — true by
definition here, since they just used it.

**Q: Why do escalations not show up in Copilot Studio analytics?**
Because *"proactive messages don't appear in conversation transcripts or analytics session
data."* Documented behaviour, not a bug — and the main reason to add the telemetry event.

**Q: Does this send data outside our tenant?**
No. Everything stays inside Microsoft 365 / Power Platform in your GCC tenant. Note that
Variant D2 uses Outlook and *"can't be sent to users outside of your tenant."*

**Q: Can we audit who answered what?**
Yes. Power Automate run history shows exactly which account submitted which card. **Anonymity
is from the employee, not from compliance.**

**Q: What happens if the flow fails?**
The user sees a generic Copilot Studio error. Add a fallback message so they are told to use
"Email HR" instead.

**Q: What if nobody answers?**
The timeout branch fires ([Step D.5](#step-d5--add-a-timeout-path)) and the employee is told.
This is a genuine advantage over designs with no closed loop.

**Q: Can a representative revise an answer after sending?**
No. Cards created with *wait for a response* can only be submitted once; the flow continues
after the first response and further submissions are ignored.

**Q: Will this work on Teams mobile?**
Yes. Adaptive Cards and agent messages render on mobile. Test it anyway — long answers in
cards are cramped on a phone.

**Q: How do we test without bothering HR?**
Point the channel at a test channel containing only you and a colleague. Only switch to the
real HR channel after the end-to-end test passes.

**Q: What if volume grows and the channel becomes noisy?**
Microsoft names this limitation: built-in connectors *"own the delivery channel."* The
[custom human-in-the-loop pattern](https://microsoft.github.io/mcscatblog/posts/human-in-the-loop-custom-connector/)
(any UI that can call a REST endpoint, with a prioritised queue) is the sanctioned next step.
**Do not build that first** — build this, measure, then escalate the design if noise becomes
real.

---

## Reference material

### Proactive messaging and Adaptive Cards — official

| Resource | What it covers | Closeness |
|---|---|---|
| [**Send proactive Microsoft Teams messages**](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message) | **Post as agent / Chat with agent, proactive Adaptive Cards, wait-for-response, status codes** | ⭐ **Read this first** |
| [Send a message in Teams using Power Automate](https://learn.microsoft.com/power-automate/teams/send-a-message-in-teams) | Every Post as / Post in combination | **Step-by-step** |
| [Create your first adaptive card](https://learn.microsoft.com/power-automate/create-adaptive-cards) | **Full walkthrough of post-card-and-wait** | **Direct tutorial for Step D.4** |
| [Overview of adaptive cards for Power Automate](https://learn.microsoft.com/power-automate/overview-adaptive-cards) | Wait-for-response actions, update messages, known issues | Reference |
| [Adaptive Cards overview (Copilot Studio)](https://learn.microsoft.com/microsoft-copilot-studio/adaptive-cards-overview) | **Teams caps schema at 1.5**; submit-button best practice | **Before editing the card** |
| [Ask with Adaptive Cards](https://learn.microsoft.com/microsoft-copilot-studio/authoring-ask-with-adaptive-card) | Interactive card directly in a topic | Alternative shape |
| [Lead collection sample](https://learn.microsoft.com/power-automate/lead-collection-sample) | **`Input.Text` `id` → output token** | Shows how card input reaches the flow |
| [Adaptive Cards Designer](https://adaptivecards.io/designer/) | Visual card editor | Editing the Step D.4 card |
| [Adaptive Cards schema explorer](https://adaptivecards.io/explorer/) | Every element and property | Adding fields |

### Agent flows and the async alternative

| Resource | What it covers |
|---|---|
| [**Asynchronous response support for agent flows**](https://learn.microsoft.com/microsoft-copilot-studio/flow-asynchronous-response) | **The simpler alternative** — callback support, Teams-supported, environment requirement |
| [Create an agent flow as a tool](https://learn.microsoft.com/microsoft-copilot-studio/advanced-flow-create) | **100-second limit**; actions after the response run up to 30 days |
| [Modify an existing flow to use with an agent](https://learn.microsoft.com/microsoft-copilot-studio/flow-modify-use-with-agent) | Required trigger/response; **async must be Off** without the feature |
| [Request for information (RFI)](https://learn.microsoft.com/microsoft-copilot-studio/flows-request-for-information) | **Variant D2** — native pause-and-ask-a-human |
| [Multistage and AI approvals](https://learn.microsoft.com/microsoft-copilot-studio/flows-advanced-approvals) (preview) | Staged approval gates |
| [Agent flows overview](https://learn.microsoft.com/microsoft-copilot-studio/flows-overview) | Agent flows vs workflows |
| [Agent flows FAQ](https://learn.microsoft.com/microsoft-copilot-studio/flows-faqs) | Confirms agent flows work in **GCC**; billing model |
| [New Power Automate infrastructure](https://learn.microsoft.com/power-automate/environment-architecture) | The environment requirement for async |
| [Limits of automated, scheduled, and instant flows](https://learn.microsoft.com/power-automate/limits-and-config) | 30-day run duration |
| [Cloud flow error code reference](https://learn.microsoft.com/power-automate/error-reference) | `ActionTimedOut`, `OperationTimedOut`, timeout branches |

### Working code you can read

| Resource | What it demonstrates |
|---|---|
| [**Teams sample: bot-proactive-message**](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/bot-proactive-message) | **Working proactive-messaging code** — the mechanism behind Step D.6 |
| [Teams sample: bot-cards](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/bot-cards) | Card types and actions as rendered in Teams |
| [microsoft/AdaptiveCards](https://github.com/microsoft/AdaptiveCards) | Schema, renderers, samples |
| [**contact-center/skill-handoff**](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/skill-handoff) | **The closest official analogue to this design** — a live handoff that keeps Teams as the channel and uses Teams proactive messaging to deliver the human's replies. Also confirms the engagement-hub pattern *"doesn't work well"* with Teams |
| [microsoft/CopilotStudioSamples](https://github.com/microsoft/CopilotStudioSamples) | Official Copilot Studio sample repository |
| [EmployeeSelfServiceAgent](https://github.com/microsoft/CopilotStudioSamples/tree/main/EmployeeSelfServiceAgent) | HR self-service topic design in the same domain as yours (marked pending deprecation) |
| [Power CAT Copilot Agent Kit](https://github.com/microsoft/Power-CAT-Copilot-Studio-Kit) | Agent Insights Hub (App Insights analytics), batch testing, Agent Debugger. **GCC support unverified** |

### Microsoft CAT team blog — "The Custom Engine"

| Post | Why it matters |
|---|---|
| [**Building a Custom Human-in-the-Loop Experience**](https://microsoft.github.io/mcscatblog/posts/human-in-the-loop-custom-connector/) | **Names this design's scaling limit** — connectors *"own the delivery channel"* |
| [Design Copilot Studio Agents for Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-agent-patterns/) | Eight production patterns with importable YAML |
| [Best Practices for Deploying Agents in Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment-ux/) | Session persistence, update caching |
| [From DEV to PROD: Deploying Agents to Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment/) | Environments, solutions, promotion |

### Community blog posts (not Microsoft-authored)

| Post | Author | Covers |
|---|---|---|
| [Register response from custom Adaptive Cards](https://poszytek.eu/en/microsoft-en/office-365-en/powerautomate-en/register-response-from-custom-adaptive-cards-sent-from-power-automate-to-teams/) | Tomasz Poszytek, **MVP** | Capturing submitted card values |
| [Dynamic Adaptive Cards with Copilot Studio](https://reshmeeauckloo.com/posts/copilotstudio-dynamic-adaptivecard/) | Reshmee Auckloo | Cards whose content varies at run time |
| [Copilot Studio: Create an Agent and Use Adaptive Cards](https://rajeevpentyala.com/2025/07/15/copilot-studio-create-an-agent-and-use-adaptive-cards/) | Rajeev Pentyala | End-to-end card walkthrough |
| [Capturing Adaptive Card Responses Without a Bot](https://devopsaitoolkit.com/blog/teams-workflows-card-response-no-bot/) | Community | Card responses via Workflows |
| [jameswh3/copilot-studio-adaptive-cards](https://github.com/jameswh3/copilot-studio-adaptive-cards) | Community | Card samples and guide |

⚠️ **These are third-party and unversioned.** They can go stale without notice, and none
address GCC. Use them to understand *mechanics*, then confirm against the official docs.

### Free hands-on training

| Module | Covers |
|---|---|
| [**Build Power Automate flows for your agent**](https://learn.microsoft.com/training/modules/build-flows-chatbot-online-workshop/) | Guided workshop: calling flows from topics, passing variables |
| [Enhance Copilot Studio agents](https://learn.microsoft.com/training/modules/enhance-power-virtual-agents-bots/) | Calling Power Automate from topics; analysing agent performance |

⚠️ **Training modules assume a commercial tenant.** Substitute your GCC addresses
(`gcc.powerva.microsoft.us`, `gov.flow.microsoft.us`) and expect screenshot mismatches.

### Escalation design and Responsible AI

| Resource | What it gives you |
|---|---|
| [Alternate escalation paths](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-alternate-escalation-paths) | Operating-hours checks; email fallback |
| [Deflection overview](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-overview) | Official metric definitions |
| [Deflection and escalation analysis](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-topic-escalation-analysis) | Escalation Rate Drivers |
| [Smart onboarding agent architecture](https://learn.microsoft.com/power-platform/architecture/solution-ideas/onboarding-agent) | **Responsible AI: escalation required; human-vs-agent disclosure** |

### Your own repository

| Document | Why it is relevant |
|---|---|
| `COPILOT_STUDIO_SETUP_GUIDE.md` | Click-by-click guide for the existing "Email HR" flow — same patterns |
| `EMAIL_HR_DEPLOYMENT_CHECKLIST.md` | Section 5: authentication dependency. Section 9: variable mappings |
| `CUSTOM_FEEDBACK_SETUP_GUIDE.md` | A second worked Copilot Studio → flow → Function example |
| `ANALYTICS_KQL_QUERIES.md` | Existing event schema for the telemetry event |

---

## Glossary

| Term | Meaning |
|---|---|
| **Adaptive Card** | A JSON-defined interactive block that renders natively in Teams |
| **Agent** | Two meanings. *AI agent* = the bot. *Live agent* = a human |
| **Agent flow** | A flow with the **When an agent calls the flow** trigger, callable from a topic |
| **Channel** (Teams) | A named section inside a team |
| **Flow bot** | The generic bot identity Power Automate uses for messages not tied to a person |
| **GCC** | Government Community Cloud. **Not** the same as GCC High |
| **ISO 8601 duration** | A timeout format. `PT8H` = 8 hours, `PT5M` = 5 minutes |
| **Maker** | Someone permitted to build agents and flows |
| **Proactive message** | A message an agent sends without the user prompting it |
| **RFI** | Request for information — the native pause-and-ask-a-human action |
| **Solution** | A Power Platform container; flows must be in one to be callable by an agent |
| **Topic** | A conversation script |
| **UPN** | User Principal Name — usually the sign-in email address |

---

## Sources

Every non-obvious claim traces to one of these. All verified to resolve.

**Proactive messaging and delivery:**

- [Send proactive Microsoft Teams messages](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message) — **Post as agent / Chat with agent**; installation prerequisites; status codes `200`/`100`/`300`; **proactive messages excluded from transcripts and analytics**; personal chat only
- [Send a message in Teams using Power Automate](https://learn.microsoft.com/power-automate/teams/send-a-message-in-teams) — Post as Flow bot / Copilot Studio agent; Chat with Flow bot
- [Create and send messages (Teams webhooks)](https://learn.microsoft.com/microsoftteams/platform/webhooks-and-connectors/how-to/connectors-using) — **Flow bot unsupported in private channels**

**Adaptive Cards:**

- [Overview of adaptive cards for Power Automate](https://learn.microsoft.com/power-automate/overview-adaptive-cards) — wait-for-response actions; single-submit limit; update messages; **DoD exclusion**
- [Create your first adaptive card](https://learn.microsoft.com/power-automate/create-adaptive-cards) — end-to-end tutorial; **Workflows app prerequisite**
- [Adaptive Cards overview (Copilot Studio)](https://learn.microsoft.com/microsoft-copilot-studio/adaptive-cards-overview) — **Teams caps schema at 1.5**; unique submit-action data
- [Ask with Adaptive Cards](https://learn.microsoft.com/microsoft-copilot-studio/authoring-ask-with-adaptive-card) — submit-button behaviour with consecutive cards
- [Lead collection sample](https://learn.microsoft.com/power-automate/lead-collection-sample) — `Input.Text` `id` becomes the output token

**Agent flows and timing:**

- [Create an agent flow as a tool](https://learn.microsoft.com/microsoft-copilot-studio/advanced-flow-create) — **100-second limit**; actions after the response run to 30 days; solution requirement
- [Modify an existing flow to use with an agent](https://learn.microsoft.com/microsoft-copilot-studio/flow-modify-use-with-agent) — trigger/response actions; async **Off**; `Error code: 3000`
- [Asynchronous response support for agent flows](https://learn.microsoft.com/microsoft-copilot-studio/flow-asynchronous-response) — **the simpler alternative**; Teams supported; M365 Copilot and telephony not; behaviour without support
- [New Power Automate infrastructure](https://learn.microsoft.com/power-automate/environment-architecture) — environment requirement for async
- [Request for information (RFI)](https://learn.microsoft.com/microsoft-copilot-studio/flows-request-for-information) — **Outlook only; first response wins; no external users; `{{ }}` known issue**
- [Multistage and AI approvals](https://learn.microsoft.com/microsoft-copilot-studio/flows-advanced-approvals) — staged approval gates
- [Agent flows FAQ](https://learn.microsoft.com/microsoft-copilot-studio/flows-faqs) — GCC availability; usage-based billing
- [Limits of automated, scheduled, and instant flows](https://learn.microsoft.com/power-automate/limits-and-config) — 30-day run duration
- [Cloud flow error code reference](https://learn.microsoft.com/power-automate/error-reference) — `ActionTimedOut`, `OperationTimedOut`
- [FlowActionBadRequest in channels](https://learn.microsoft.com/troubleshoot/power-platform/copilot-studio/channels/agent-flow-action-bad-request) — schema mismatch after editing a flow
- [Understand error codes](https://learn.microsoft.com/troubleshoot/power-platform/copilot-studio/authoring/error-codes) — `FlowActionTimedOut`, `3000`

**Copilot Studio configuration:**

- [Variables overview](https://learn.microsoft.com/microsoft-copilot-studio/authoring-variables-about) — `User.PrincipalName` and system variables
- [Add user authentication to topics](https://learn.microsoft.com/microsoft-copilot-studio/advanced-end-user-authentication) — auth variables unavailable without authentication
- [Channel experience reference table](https://learn.microsoft.com/microsoft-copilot-studio/publication-fundamentals-publish-channels#channel-experience-reference-table) — **six-option cap** in Teams
- [Share an agent](https://learn.microsoft.com/microsoft-copilot-studio/admin-share-bots) — permission prerequisite for proactive delivery

**GCC:**

- [Copilot Studio US Government service URLs](https://learn.microsoft.com/microsoft-copilot-studio/requirements-licensing-gcc#microsoft-copilot-studio-us-government-service-urls) — **authoritative GCC portal addresses**
- [Plan for government clouds](https://learn.microsoft.com/microsoftteams/platform/concepts/cloud-overview) — Workflows available in GCC, not GCC High/DoD

**Escalation design and Responsible AI:**

- [Alternate escalation paths](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-alternate-escalation-paths) — operating-hours and queue checks
- [Deflection overview](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-overview) — official metric definitions
- [Deflection and escalation analysis](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-topic-escalation-analysis) — Escalation Rate Drivers
- [Smart onboarding agent architecture](https://learn.microsoft.com/power-platform/architecture/solution-ideas/onboarding-agent) — **Responsible AI: escalation required; disclose human vs agent**

**Blog posts:**

- [Building a Custom Human-in-the-Loop Experience](https://microsoft.github.io/mcscatblog/posts/human-in-the-loop-custom-connector/) — connectors *"own the delivery channel"*
- [Design Copilot Studio Agents for Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-agent-patterns/) — production patterns with importable YAML
- [Best Practices for Deploying Agents in Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment-ux/) — session persistence, update caching
- [Register response from custom Adaptive Cards](https://poszytek.eu/en/microsoft-en/office-365-en/powerautomate-en/register-response-from-custom-adaptive-cards-sent-from-power-automate-to-teams/) — community; capturing card submissions
- [Dynamic Adaptive Cards with Copilot Studio](https://reshmeeauckloo.com/posts/copilotstudio-dynamic-adaptivecard/) — community
- [Copilot Studio: Create an Agent and Use Adaptive Cards](https://rajeevpentyala.com/2025/07/15/copilot-studio-create-an-agent-and-use-adaptive-cards/) — community

**Working code:**

- [Teams sample: bot-proactive-message](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/bot-proactive-message) — runnable proactive-messaging bot
- [Teams sample: bot-cards](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/bot-cards) — card types and actions
- [microsoft/AdaptiveCards](https://github.com/microsoft/AdaptiveCards) — schema and renderers
- [Power CAT Copilot Agent Kit](https://github.com/microsoft/Power-CAT-Copilot-Studio-Kit) — Agent Insights Hub, testing, Agent Debugger

**Training:**

- [Build Power Automate flows for your agent](https://learn.microsoft.com/training/modules/build-flows-chatbot-online-workshop/) — topic → flow integration workshop
- [Enhance Copilot Studio agents](https://learn.microsoft.com/training/modules/enhance-power-virtual-agents-bots/) — calling flows from topics
