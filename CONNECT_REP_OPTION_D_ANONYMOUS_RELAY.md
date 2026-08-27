# Option D — Anonymous Relay (recommended when representatives must stay anonymous)

**What this document is:** a beginner's guide to letting an employee get a **real human
answer** from HR **without ever learning who wrote it**. The employee asks; the agent cannot
answer; the question appears in an HR Teams channel as a card; a representative types the
answer; the agent delivers it back.

**Who this is for:** someone who has never configured Copilot Studio or Power Automate.
Every step says where to click and what you should see afterwards.

**Time required:** about 1.5 hours.
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

> ## ⚡ This guide uses Asynchronous response
>
> This document is written for the **[asynchronous response](https://learn.microsoft.com/microsoft-copilot-studio/flow-asynchronous-response)**
> build, which you have confirmed is available in your environment.
>
> With it, the flow can wait for a human and then **return the answer to the agent as its own
> result** — so the answer appears as an ordinary agent reply. This removes the fragile
> action-ordering rule, the separate proactive-message delivery step, and the requirement that
> the employee still have the agent installed.
>
> ⚠️ **One thing to validate before rollout.** Async lifts the limit on how long the *flow*
> runs. Microsoft does not document how long a **callback stays deliverable** to the
> conversation. Teams threads persist indefinitely and Teams is the only channel with formal
> callback support, so this most likely works — but it is unverified. Read
> [The unresolved risk](#the-unresolved-risk--the-flow-outlives-the-conversation) and test at
> your intended wait time before promising HR an 8-hour window.
>
> ⚠️ **It is off by default on each flow.** You turn it on in
> [Step D.5](#step-d5--return-the-answer-to-the-agent).

---

## Table of contents

- [How to use this document](#how-to-use-this-document)
- [Your scenario — verified facts](#your-scenario--verified-facts)
- [A note on Power Automate licensing](#a-note-on-power-automate-licensing)
- [Background — how the current feature works](#background--how-the-current-feature-works)
- [How the relay works](#how-the-relay-works)
- [How asynchronous response shapes this build](#how-asynchronous-response-shapes-this-build)
- [The unresolved risk — the flow outlives the conversation](#the-unresolved-risk--the-flow-outlives-the-conversation)
- [Step D.1 — Create the HR intake channel](#step-d1--create-the-hr-intake-channel)
- [Step D.2 — Create the flow and define its inputs](#step-d2--create-the-flow-and-define-its-inputs)
- [Step D.3 — Post the card and wait for an answer](#step-d3--post-the-card-and-wait-for-an-answer)
- [Step D.4 — Add a timeout path](#step-d4--add-a-timeout-path)
- [Step D.5 — Return the answer to the agent](#step-d5--return-the-answer-to-the-agent)
- [Step D.6 — Wire the flow into the topic](#step-d6--wire-the-flow-into-the-topic)
- [Step D.7 — Publish and test end to end](#step-d7--publish-and-test-end-to-end)
- [Step D.8 — Brief the representatives](#step-d8--brief-the-representatives)
- [Alternatives worth knowing about](#alternatives-worth-knowing-about)
- [Pros and cons](#pros-and-cons)
- [Anonymity — what it does and does not protect](#anonymity--what-it-does-and-does-not-protect)
- [Making it clear which answers came from a person](#making-it-clear-which-answers-came-from-a-person)
- [Optional — Add telemetry so Power BI stays complete](#optional--add-telemetry-so-power-bi-stays-complete)
- [Troubleshooting](#troubleshooting)
- [Technical questions you are likely to be asked](#technical-questions-you-are-likely-to-be-asked)
- [References](#references)
- [Glossary](#glossary)

---

## How to use this document

### Before you build anything

1. Read [How asynchronous response shapes this build](#how-asynchronous-response-shapes-this-build).
   It explains the one setting the whole design depends on.
2. Build Steps D.1–D.8. If HR would rather answer from Outlook than a Teams channel, see
   [Alternatives worth knowing about](#alternatives-worth-knowing-about) first.

### What to skip on a first read

- **[References](#references)** — Tier 1 is worth reading before you build; Tiers 2–8 are
  there for when you hit a specific problem.
- **[Technical questions](#technical-questions-you-are-likely-to-be-asked)** — for when you
  present this to others.

> ⚠️ **Build it against a test channel and your own account first.** Only point it at the
> real HR channel once the end-to-end test passes.

---

## Your scenario — verified facts

| Fact | Value | Why it matters |
|---|---|---|
| Cloud | **GCC** (not GCC High, not DoD) | Adaptive Cards are unavailable in DoD; GCC is fine |
| Agent channel | **Microsoft Teams** | Async callbacks are *"fully supported"* here |
| **Asynchronous response** | **Available in your environment** (confirmed) | The basis of this build; **off by default per flow** |
| Copilot Studio auth | **Authenticate with Microsoft** | Required for `System.User.PrincipalName` |
| User identity variable | **`System.User.PrincipalName`** | Identifies the asker to HR |
| Function App | `func-hrbenefit-dev003` (Flex Consumption, Python) | Three routes; **no change needed** |
| Existing escalation | "Email HR" via `send_hr_email` | You are adding a *second* choice beside it |
| Teams Workflows app | Must be **installed and enabled** | Prerequisite for Adaptive Card actions |
| Browser popups | Must be **allowed** for `[*.]powerautomate.com` and `[*.]microsoft.us` | The Teams connector sign-in is an OAuth popup; blocked popups stop you adding the card action |

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

### ⚠️ Copilot Credits — the cost axis that can switch this feature off

Connector tier is not the only thing that can stop this design working. Agent flows consume
**Copilot Credits**, and running out has a specific, documented consequence:

> *"Once you fully consume your environment's prepaid Copilot Studio capacity, **new agent
> flow runs are blocked** until capacity is available. Running agent flows complete
> normally."*

**What this means for your escalation feature specifically:**

| Behaviour | Consequence for you |
|---|---|
| New agent flow runs are **blocked** | "Connect to a representative" stops working |
| The parent agent **keeps working** | The agent still answers normally, so the failure is **partial and easy to miss** |
| In-progress runs finish | Answers already waiting on a card still get delivered |
| Resets monthly | The feature may appear to fix itself, masking the cause |

⚠️ **This is a nastier failure than it first appears.** The agent keeps answering questions,
so nobody reports "the agent is down" — only the escalation path dies, and only for as long
as capacity is exhausted.

**Cost per escalation.** Each run from a topic consumes **one Classic answer** plus the
**agent flow actions** it executes. Agent flow actions are billed at **13 Copilot Credits per
100 actions**, so an individual escalation is cheap — the risk is aggregate consumption across
*every* agent flow in the environment, not this feature alone.

> 💡 **Two things worth checking before rollout:**
>
> 1. **Are your users Microsoft 365 Copilot licensed?** If so, agent flow runs triggered by
>    **"When an agent calls the flow"** are documented as **no charge** and **exempt from
>    enforcement** — this whole risk may not apply to you. Confirm it rather than assume it.
> 2. **Ask your admin whether pay-as-you-go is enabled.** With a PAYG meter linked,
>    enforcement does not apply. Without one, an exhausted environment silently disables
>    escalation.
>
> Monitor under **Power Platform admin center → Licensing → Copilot Studio → Environments**,
> in the **Agent flow actions** line of the credit consumption grid.

**Testing does not cost you anything.** Microsoft: *"Testing an agent flow in the flow
designer or from the agent's test chat doesn't consume Copilot Studio capacity."* So the
long-wait tests recommended in this guide are free.

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
	|  says "I've sent your question to HR", then calls the flow
	v
FLOW  [Asynchronous response = On]
	|
	+--► posts an Adaptive Card into the HR channel
	|         "...and wait for a response"          (may take hours)
	|                                   |
	|     an HR rep types the answer ───+
	|
	+--► Respond to the agent   ◄── returns the answer as the flow's result
			  |
			  v
		The agent replies to the employee in the same conversation
```

The employee sees a message from **the agent**. The representative's name appears nowhere in
what the employee receives.

---

## How asynchronous response shapes this build

Everything in this design rests on one setting. Understand it before you build.

### The problem it solves

An agent flow normally must **respond to the agent within 100 seconds**, or it fails with
`FlowActionTimedOut`. A human will not answer a benefits question in 100 seconds.

**Asynchronous response removes that constraint.** Microsoft:

> *"Asynchronous flows continue running beyond the previous two-minute limit while still
> returning a response to the agent after execution completes."*

So the flow can post a card, wait for a human, and then hand the answer back to the agent as
its **own return value**. The agent replies to the employee normally — no separate delivery
step, no dependency on the employee still having the agent installed, and no delivery status
codes to handle.

### What it does *not* change

- **The 30-day ceiling.** A flow run still cannot exceed 30 days, so you still need an
  explicit timeout — [Step D.4](#step-d4--add-a-timeout-path).
- **The Responsible AI disclosure.** The reply now looks exactly like an agent answer, so it
  must be labelled as human-written — see
  [Making it clear which answers came from a person](#making-it-clear-which-answers-came-from-a-person).
- **Anonymity.** That still comes from the transport, not from a setting.
- **The conversation session clock.** This is the important one — see the next section.

### The unresolved risk — the flow outlives the conversation

**Read this before committing to an 8-hour answer window.** It is the one part of this design
Microsoft's documentation does not answer, and it is worth 30 minutes of testing.

Asynchronous response removes the limit on **how long the flow may run**. It says nothing
about how long the **conversation** remains able to receive the callback. Nothing in Microsoft's
documentation states that a callback expires — but nothing states that it doesn't, either.

#### What is actually documented

Be careful with the numbers you may find, because two of the most-cited ones do **not** mean
what they appear to mean:

| Figure | What it actually governs | Does it limit callback delivery? |
|---|---|---|
| **30 min** / **60 min** session rules | *Billed sessions* under the **legacy Power Virtual Agents licence** (withdrawn January 2024). A billing boundary, not a delivery boundary | ❌ No — do not plan around these |
| **30 min** inactivity | When a **new transcript record** is started, and the default for the optional *inactivity trigger* | ❌ No — affects analytics grouping, not delivery |
| **30 days** | Maximum agent flow run duration | ✅ Yes — a hard ceiling on the wait |
| **7 days** | Maximum inactivity-trigger duration | Only if you add inactivity topics |

> ⚠️ **This corrects an earlier reading.** The 30-minute and 60-minute figures come from a
> [legacy billing article](https://learn.microsoft.com/microsoft-copilot-studio/requirements-sessions-management)
> that carries a note limiting it to a licence no longer sold. They describe when Microsoft
> stops counting a session for billing — not when Teams stops accepting a message. Treating
> them as delivery deadlines would be wrong.

#### What points toward this working

The evidence is actually reasonably encouraging for your specific setup:

- **Teams is the one channel with formal callback support.** Microsoft: the callback feature
  *"is fully supported in Microsoft Teams"*, while other channels *"aren't formally tested."*
- **Teams conversations do not expire.** Microsoft's Teams deployment guidance states threads
  persist *"indefinitely"* and that the conversation *"never truly 'ends' from Teams'
  perspective"* — the article treats this persistence as a **problem** to manage (stale
  context, token expiry), which only makes sense if long-lived threads are the norm.
- **Microsoft anticipates users messaging mid-wait.** The documented behaviour — *"the flow
  runs to completion, but the agent responds to the user's latest request"* — describes a wait
  long enough for the user to get bored and do something else.

#### What remains genuinely unknown

- **No stated callback lifetime.** No Microsoft document gives a maximum age for an async
  callback.
- **No published example resembles your use case.** Every async example is a long-running
  *process*; none is a multi-hour wait on a human.
- **Token expiry is a documented risk over long threads.** The Teams guidance explicitly lists
  *"connectors can expire during long sessions"*. Your agent uses **Authenticate with
  Microsoft**, so a stale token could affect the turn that delivers the answer.

#### Realistic outcomes

| Outcome | Likelihood | Employee experience |
|---|---|---|
| Callback delivers into the persistent Teams thread | **Most likely** | ✅ Works as this guide describes |
| Callback delivers, but topic variables were reset | Possible | ⚠️ Answer appears, possibly without the surrounding wording |
| Callback dropped after some undocumented expiry | **Least likely, but unverified** | ❌ **Silent failure** — flow shows Succeeded, employee gets nothing |

The last row is the one to design against — not because it is probable, but because **the
flow run history will report success either way**. Nothing would alert you.

#### The test that settles it

Cheap, and it converts an unknown into a fact: escalate a question, leave the chat completely
idle, and answer the card after **90 minutes** — then repeat at your real target duration.
The full procedure is in
[Step D.7](#step-d7--publish-and-test-end-to-end); run it **before briefing HR**, because the
result determines what you can promise.

#### If the long wait does not survive

Three fallbacks, in order of preference:

1. **Shorten the promise.** Set the card timeout to `PT30M`–`PT2H` and staff the channel
   during business hours. Pair this with the operating-hours check described under
   [Pros and cons](#pros-and-cons).
2. **Deliver by proactive message instead** — see
   [Alternatives worth knowing about](#alternatives-worth-knowing-about).
   Proactive messages are explicitly designed to reach a user *outside* an active
   conversation. The cost is the agent-installed prerequisite and the analytics blind spot.
3. **Send the answer by email**, reusing the pattern your `send_hr_email` feature already
   proves works.

> 💡 **A belt-and-braces option if this feature is business-critical.** Return the answer to
> the agent **and** send a proactive message. If the callback lands, the employee sees it
> immediately; if it is ever dropped, the proactive message still reaches them. The cost is an
> occasional duplicate — cheaper than a silently lost answer. Worth it only if you cannot
> tolerate the failure; otherwise test first and keep the build simple.

### Channel support

> ⚠️ Microsoft: *"The callback feature for asynchronous flows is **fully supported in
> Microsoft Teams**. Other channels might also support callbacks, but they aren't formally
> tested. Callbacks **aren't supported for Microsoft 365 Copilot and telephony channels**."*
>
> Teams is your channel, so this is supported — but do not reuse this pattern on those
> channels.

### The environment requirement

Asynchronous response exists only in environments on the
**[new Power Automate infrastructure](https://learn.microsoft.com/power-automate/environment-architecture)**
(*SelfHost Multitenant*). You have confirmed the toggle is available, so this is satisfied.

> **If you ever need to re-verify** — for example in a different environment — sign in to
> Power Automate (`gov.flow.microsoft.us`), select the environment, press
> **Ctrl + Alt + A**, and look for **`environmentFlowHostingType`**:
> `SelfHostMultiTenant` means new architecture; `LogicApps` means it is not.

> ⚠️ **Do not enable async on a flow in an environment that does not support it.** Microsoft
> warns the agent *"might receive a 'flow completed' response immediately while the flow
> continues to run in the background"* — the employee would get an empty answer and never
> learn the real one. On older infrastructure the agent instead errors with
> *"Something unexpected happened… Error code: 3000."*

---

## Step D.1 — Create the HR intake channel

⚠️ **Prerequisite:** Microsoft's adaptive-card tutorial states you need **Microsoft Teams
with the Workflows app installed**. Workflows is available in **GCC** (but not GCC High or
DoD). If cards never appear, verify the Workflows app is enabled in your Teams admin center
before debugging the flow itself.

1. In Teams, go to the HR team — **the team itself can be public or private; it makes no
   difference.** Most HR teams are private, and that is fine.
2. Click **⋯** next to the team name → **Add channel**.
3. Name it, e.g. `Benefits Questions (Anonymous Relay)`.
4. Choose **Standard**.

> ⚠️ **The constraint is on the *channel type*, not the team's privacy setting.** These are two
> unrelated settings, and it is easy to read the warning below as applying to the team.
>
> | Setting | What it controls | Does it affect this build? |
> |---|---|---|
> | **Team privacy** (public / private) | Who can join the team | ❌ No — a private team is fine |
> | **Channel type** (standard / private / shared) | Who in the team sees the channel | ✅ **Yes — must be standard** |
>
> A **standard channel inside a private team** is exactly what you want: only HR team members
> can see it, and the flow can post to it.

⚠️ **Why standard and not private or shared.** Microsoft's channel feature comparison lists
**bots, connectors, and messaging extensions** as supported in standard channels only — *not*
in private or shared channels. The Teams connector documentation states the same from the
other side: *"Sending a message in private channels isn't supported."* Choosing either will
cost you hours of debugging a flow that is actually correct.

5. Add the HR representatives as members **of the team**. In a standard channel, every team
   member automatically has access — there is no separate channel membership to manage.
6. Set the channel layout to **Posts**, not Threads: **⋯** next to the channel name →
   **Edit channel** → under **Layout**, choose **Posts** → **Save**. If you see no Layout
   option, your tenant only has Posts and there is nothing to do.

> 💡 **Why Posts rather than Threads — and how firm this is.** Unlike the standard/private
> rule above, this is a **preference, not a documented constraint.** Microsoft publishes
> nothing saying Adaptive Cards fail in the Threads layout. Three reasons to prefer Posts
> anyway:
>
> 1. **It is what every tutorial assumes.** Microsoft's post-card-and-wait walkthrough, the
>    screenshots, and the community write-ups in [References](#references) were all authored
>    against Posts. If something renders oddly, you want to be on the well-trodden path.
> 2. **Threads is still rolling out and is not universally available.** It began rolling out
>    in mid-2025 and is absent from some tenants and account types. There are documented cases
>    of it appearing and then disappearing again.
> 3. **Mixed views break notifications.** During a partial rollout, Teams itself warns:
>    *"Some people in this channel have a different view from you. Some messages may appear
>    out of order and disconnected from a thread. This may impact notifications."* For an
>    intake queue where reps must notice new questions, that is the wrong risk to take.
>
> There is also a by-design notification difference in Threads: replies inside a thread do
> **not** bold the channel name in the left navigation, and Microsoft states there is no
> setting to change it. New cards arrive as new top-level posts, so they should still bold —
> but the follow-up behaviour around an answered card is less predictable.

✅ **Checkpoint:** the channel exists, is **standard** (no lock icon next to its name), uses
the **Posts** layout, and you can post in it manually.

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
| `Question` | What the employee asked — **shown on the card** |
| `UserEmail` | Identifies the asker; used for telemetry and any email fallback |
| `UserName` | Who asked — **shown on the card** |
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

## Step D.3 — Post the card and wait for an answer

> ⚠️ **Before you start: the Teams connector will ask you to sign in.** It uses OAuth, which
> needs a **popup**. If your browser blocks it, the action cannot be added at all.
>
> Add permanent exceptions for **popups** *and* **third-party cookies** covering:
>
> ```
> [*.]powerautomate.com
> [*.]microsoft.us
> ```
>
> The second entry matters in GCC — you are on `gov.flow.microsoft.us`, so a rule covering
> only `powerautomate.com` will not help. Dismissing the browser's one-off "popup blocked"
> prompt is not enough; it will block again on the next connector.
>
> If the popup opens but sign-in loops or fails, **sign out inside the popup, then sign back
> in within that same window** — a documented quirk of OAuth connectors.
>
> ⚠️ **The account you sign in with becomes the connection's identity.** It does not affect
> anonymity (this build never posts as `User`), but that account must be able to post to the
> HR channel, and it should not be one that might be deprovisioned. A shared or service
> account is safer if your tenant allows it.

1. Click **+ New step**.
2. Search for **Post an adaptive card to a Teams channel and wait for a response**.

   ⚠️ It must be the **"and wait for a response"** variant. The plain "post" action cannot
   collect input — Microsoft documents that non-waiting cards *"return an error for all
   button actions except OpenURL."*

3. Set **Post as** to **`Flow bot`**.
4. Set **Post in** to **`Channel`**.
5. Set **Team** and **Channel** to the channel from Step D.1.

> ⚠️ **`Post as` must be `Flow bot` here, not `Microsoft Copilot Studio agent`.** Agent
> identity is only supported for posting into a **personal chat with the agent** — not into a
> channel.
>
> **The symptom if you get this wrong:** `Post in` collapses from a dropdown into a
> **free-text box**, because the designer has no valid channel list to offer. *(Confirmed
> against the product, not just the docs.)*
>
> **Do not paste a channel ID into that box.** It is the connector degrading, not a
> workaround, and you would be relying on an unsupported combination.
>
> **This costs you nothing.** Only HR sees this card. Anonymity comes from how the answer
> returns *to the employee* — as the flow's return value, spoken by the agent in
> [Step D.5](#step-d5--return-the-answer-to-the-agent) — not from how the card reaches HR. The
> employee never sees the Flow bot at all.

> ⚠️ **`Post as` must never be `User`** on any Teams action in this flow. That sends the
> message as the account signed in to the Teams connector — usually the flow owner — and
> anonymity is lost immediately.

> 💡 **If the Channel dropdown is empty or your channel is missing**, it is almost certainly
> private or shared. Bots cannot post to either — it must be a **standard** channel
> ([Step D.1](#step-d1--create-the-hr-intake-channel)).

6. In **Message**, paste this Adaptive Card JSON:

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
> **The `id` of an `Input.Text` is what identifies the value in the card's response.** In the
> card above the input is `"id": "answer"`, so the submitted text comes back under that name
> in the action's output.
>
> ⚠️ **You will not find it in the lightning-bolt picker.** *(Confirmed against the product.)*
> Because the card is pasted in as JSON, the designer cannot infer its schema and offers only
> a generic **Body**. You retrieve the value with an **`fx` expression** instead — see
> [Step D.5](#step-d5--return-the-answer-to-the-agent).
>
> Microsoft's [lead collection sample](https://learn.microsoft.com/power-automate/lead-collection-sample)
> shows the same `id`-to-output mechanism, but with a card built through the designer rather
> than pasted JSON — which is why its tokens appear and yours do not.
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

7. Set **Update message** to: `Answer sent to the employee.`

⚠️ Configure the update message. Without it the card resets and looks unanswered, and a
second representative will answer the same question.

✅ **Checkpoint:** **Post as** is `Flow bot`, **Post in** is `Channel`, the card has a
multiline text input plus a submit button, and an **Update message** is configured.

---

## Step D.4 — Add a timeout path

Asynchronous response removes the 100-second limit, **not** the 30-day one. Without a
timeout, an unanswered question hangs for 30 days and the employee is never told.

1. Click the **…** menu on the card action → **Settings**.
2. Set **Timeout** to an ISO 8601 duration — `PT8H` means 8 hours.
3. Click **Done**.

⚠️ **Do not treat `PT8H` as settled until you have tested it at that duration.** The flow will
wait 8 hours, but callback deliverability over long waits is undocumented. See
[The unresolved risk](#the-unresolved-risk--the-flow-outlives-the-conversation). If the test
fails, fall back to `PT30M`–`PT2H` with business-hours staffing.

> ⚠️ **Important: a timed-out card action does not "continue" — it fails.** Power Automate
> reports `OperationTimedOut`, and by default **every following action is skipped**. If you
> stop here, a timed-out escalation leaves the employee waiting forever with no message at
> all. [Step D.5](#step-d5--return-the-answer-to-the-agent) adds the branch that prevents
> this, and it is not optional.

✅ **Checkpoint:** the card action has an explicit timeout shorter than 30 days.

---

## Step D.5 — Return the answer to the agent

This is the step that both produces the anonymity and enables the long wait. The answer never
travels as a message from a person — it travels as **the flow's return value**, and the agent
speaks it.

### Add the response action

1. Add a **Respond to the agent** action at the **end** of the flow (search the **Copilot**
   connector).
2. Add one text output named `Answer`.
3. Set its value to text that **discloses a human wrote it**, with the card's answer embedded:

   ```
   💬 **Answered by a person on the HR benefits team**

   <the answer from the adaptive card — inserted as an expression, see below>

   —
   Individual responders are not identified. If you need more help, just ask me again.
   ```

> ⚠️ **The lightning-bolt picker will not offer an `answer` token.** *(Confirmed against the
> product.)* Because the card JSON is pasted in as content, the designer cannot infer the
> card's input schema — it lists only a generic **Body** under the card action.
>
> **Do not select `Body`.** That inserts the whole JSON object.
>
> **Use the `fx` (expression) button instead**, next to the lightning bolt. Place the cursor
> where the answer belongs, click **`fx`**, and enter:
>
> ```
> body('Post_adaptive_card_and_wait_for_a_response')?['data']?['answer']
> ```
>
> The action name must match yours exactly, with spaces replaced by underscores. **Code view**
> on the action shows the exact internal name.

> ⚠️ **Verify the path against a real run before you rely on it.** The exact shape of the
> response is not documented, and `answer` may sit at the top of `body` rather than under
> `data`:
>
> 1. **Save draft**, then **Test** the flow, supplying the four inputs manually.
> 2. Answer the card when it posts to your HR channel.
> 3. Open the run under **Activity**, expand the card action, and view **raw outputs**.
>
> The JSON there gives you the exact path. If `data` is absent, use
> `body('Post_adaptive_card_and_wait_for_a_response')?['answer']`.
>
> 💡 Test runs **do not consume Copilot Credits**, so this costs nothing.

> 💡 **Worth trying first:** save the flow, reload the designer, and re-open the picker. The
> schema is occasionally populated after a save. If an `answer` token appears, use it — the
> expression works either way.

> 💡 **Why the label matters more under async.** The reply now arrives as an ordinary agent
> message, visually identical to model-generated answers. See
> [Making it clear which answers came from a person](#making-it-clear-which-answers-came-from-a-person)
> for the full labelling scheme, including the timeout message.

> ⚠️ **`answer` is the typed text; `submitActionId` is the button.** Microsoft's card
> documentation notes that `submitActionId` holds *"the `title` of the action the user
> selected."* That tells you **which button** was pressed, not what was written. You want
> **`answer`**.

⚠️ **Do not soften or remove the "Answered by a person" label.** Microsoft's Responsible AI
guidance requires that agents *"make clear when the user is interacting with an agent and when
they're receiving a response from a human."* Hiding **who** answered is fine; obscuring **that
a human answered** is not.

### Turn on Asynchronous response

4. Select the **Respond to the agent** action → **Settings**.
5. Turn **Asynchronous response** **On**.
6. **Save** the flow.

> ⚠️ **This is the setting the whole design depends on.** If it is Off, the flow must reply
> within 100 seconds; a human will not, and the run fails with `FlowActionTimedOut`.

> **Where the toggle lives.** Microsoft's asynchronous-response article says
> **Settings → Asynchronous response**; the agent-flow requirements articles describe the
> same toggle as being under **Networking** in the action settings. Panel grouping has moved
> between releases — if you do not see it directly under **Settings**, look under
> **Networking**.

### Handle the timeout branch

Because a timed-out card action **fails**, the success path above is skipped when nobody
answers. You need a second response action that runs *only* on that path.

⚠️ **This is a parallel branch, not the next step in the chain.** Both response actions hang
off the **card action**. Do not add the second one after the first.

7. Hover the **`+`** on the connector **directly below the card action** — the same connector
   that leads to your first **Respond to the agent**.
8. Choose **Add a parallel branch**, *not* **Add an action**.

   > 💡 If your designer does not offer "Add a parallel branch," add the action anywhere after
   > the card and then set its **Configure run after** — the branch shape follows from the
   > run-after configuration.

9. In the new branch, add a second **Respond to the agent**.
10. On that action: **…** → **Configure run after** → tick **has timed out** and
    **has failed**; untick **is successful**.
11. Give it the **same output name** — `Answer` — with a timeout message as its value:

    ```
    🤖 **Automated message**

    Nobody from HR has answered yet. Your question has been recorded and someone will
    follow up with you by email.
    ```

⚠️ **Mark this one as automated.** It arrives through the same mechanism as the human answer,
so without a label an employee will read it as something a person typed.

12. Turn **Asynchronous response** **On** for this action too.
13. Rename the flow to `Anonymous HR Relay` and click **Save**.

Flow shape — note the **two arrows leaving the card action**:

```
Post adaptive card AND WAIT
    |
    +-- (is successful) ----► Respond to the agent  [async On]
    |                          Answer = "💬 Answered by a person..." + <fx expression>
    |
    +-- (has timed out /
         has failed) --------► Respond to the agent  [async On]
                               Answer = "🤖 Automated message..."
```

✅ **Verify the shape on the canvas.** The card action should have **two arrows leaving it**.
If you see a single vertical chain instead, the second response action was added
sequentially — delete it and re-add it as a parallel branch.

⚠️ **What goes wrong if it is sequential.** The second action inherits the *first response
action* as its predecessor rather than the card. When someone answers, both fire and the
employee gets the real answer followed by "nobody answered." When nobody answers, the first is
skipped and the second evaluates its condition against a skipped action, so neither may run.
Both look correct on the canvas, which makes them slow to diagnose.

> ⚠️ **Every branch must respond, and with the same outputs.** Microsoft: the response action
> *"can be used at multiple branches in the flow, but must have the same outputs at each
> usage."* Both actions must expose an output named `Answer` — a mismatch causes
> `FlowActionBadRequest` when Copilot Studio maps the result.

> 💡 **Why tick "has failed" as well as "has timed out."** A card action can fail for reasons
> other than a timeout — a deleted channel, a permissions change. Without this, those failures
> also leave the employee waiting silently.

✅ **Checkpoint:** the flow ends with **two** `Respond to the agent` actions — one on success,
one on timeout/failure — both with **Asynchronous response On** and both exposing an output
named `Answer`.

---

## Step D.6 — Wire the flow into the topic

1. Return to Copilot Studio and **reload the page**.
2. In your branch: **+ (Add node)** → **Add a tool** → **Anonymous HR Relay**.
3. Map the inputs:

| Flow input | Map to |
|---|---|
| `Question` | your question variable, e.g. `Topic.UserQuestion` |
| `UserEmail` | `System.User.PrincipalName` |
| `UserName` | `System.User.DisplayName` |
| `ConversationId` | `System.Conversation.Id` |

⚠️ **`UserName` is what HR actually sees on the card.** If the agent is not authenticated,
`System.User.DisplayName` and `System.User.PrincipalName` are both empty — HR gets an
anonymous question they often cannot answer correctly, and your telemetry loses the join key.
This is the same authentication dependency your `send_hr_email` feature already has.

> **Why `PrincipalName` and not `Email`?** Both exist, but your other flows already use
> `System.User.PrincipalName` (see `EMAIL_HR_DEPLOYMENT_CHECKLIST.md`, Section 9). Staying
> consistent avoids a class of bug where one flow works and another silently receives a blank.

4. Add a **Send a message** node **before** the flow call, so the employee is not left
   watching a silent screen while the flow waits:

   > `I've sent your question to a person on the HR team — I'll post their reply here as soon as they answer, marked 💬 Answered by a person.`

⚠️ **Put this message before the tool call, not after.** Under asynchronous response the flow
does not return until a human answers, so a node placed *after* the call will not run until
then.

5. Add a **Send a message** node **after** the flow call, and insert the flow's `Answer`
   output into it:

   - Click the **`{x}`** (insert variable) icon in the message box — Copilot Studio uses this,
     **not** the lightning bolt you saw in Power Automate.
   - Pick the **`Anonymous HR Relay`** output, usually shown as `Answer` or `Topic.Answer`.
   - Alternatively switch the message to **Formula** (`fx`) mode and type the variable name.

⚠️ **Send the variable on its own — do not re-add the disclosure wording.** The
`💬 Answered by a person on the HR benefits team` label is already inside the flow's `Answer`
value from [Step D.5](#step-d5--return-the-answer-to-the-agent). Adding it here too means the
employee sees it twice.

> 💡 **If `Answer` does not appear in the picker**, work through these in order:
>
> | Symptom | Fix |
> |---|---|
> | No outputs listed at all | Reload the Copilot Studio page — the tool schema is cached |
> | Still nothing after reload | The flow was not **published** after its outputs were added. Publish it in Power Automate, then reload |
> | Listed but greyed out or stale | On the tool node, click **…** → **Refresh** to re-read the schema |
>
> ⚠️ **Check both response actions expose an output named exactly `Answer`.** If the timeout
> branch named it differently, Copilot Studio may show no output at all, or fail with
> `FlowActionBadRequest` when it maps the result.

✅ **Checkpoint:** the branch says "I've sent your question", calls the flow, and then shows
the `Answer` output — already carrying its label — when it eventually returns.

---

## Step D.7 — Publish and test end to end

1. **Save**, then **Publish**.
2. In Teams, ask the agent an unanswerable question and choose **Connect to a representative**.
3. Confirm you get the "I've sent your question" message immediately.
4. Check the HR channel for the card.
5. **Wait several minutes before answering.** This is the point of the test — a fast reply
   would also have worked without async and proves nothing.
6. As a representative, type an answer and click **Send answer**.
7. As the employee, check for the reply.

✅ **Checkpoint — all seven must be true:**
- The "I've sent your question" message appeared immediately.
- The card reached the HR channel with the question and the employee's name.
- The card updated to `Answer sent to the employee.` after submission.
- The answer arrived **in the same agent conversation**, as a normal agent reply.
- The answer arrived even though the wait exceeded 100 seconds — **this is what proves
  asynchronous response is working.**
- The answer was **visibly marked as written by a person**, and you can tell it apart from the
  agent's own AI-generated answers at a glance.
- **Nowhere in the employee's Teams client does the representative's name appear.**

⚠️ Verify the last two deliberately. Click the sender, open the profile, and confirm it
resolves to the agent and not to a person — then scroll the conversation and check you can
distinguish the human reply from the model's answers without reading closely.

### ⚠️ The test that actually decides the design

Everything above proves the mechanism works over a *short* wait. This one proves whether it
survives a **realistic** wait — and it is the difference between a feature that works and one
that silently loses answers.

1. Escalate a question from your own account.
2. **Leave the chat completely idle.** Do not send the agent anything.
3. Wait **90 minutes**.
4. Answer the card.
5. Check whether the answer arrives in Teams.
6. **Repeat the whole test at your real target duration** (4–8 hours). A passing 90-minute
   test does not prove 8 hours.

| Result | What it means | What to do |
|---|---|---|
| Answer arrives normally | ✅ The persistent Teams thread carries the callback | Proceed; retest at your real target duration |
| Answer arrives but looks odd or bare | ⚠️ Callback delivered, topic context reset | Put the full disclosure wording in the **flow's** output, not the topic |
| Nothing arrives; flow shows Succeeded | ❌ **Silent failure** | Do not roll out at 8 hours — use one of the fallbacks in [The unresolved risk](#the-unresolved-risk--the-flow-outlives-the-conversation) |

⚠️ **Check the flow run history either way.** A run marked Succeeded while the employee
received nothing is exactly the failure mode to watch for, and it will not announce itself.

### Also test the interruption case

Microsoft documents this behaviour explicitly:

> *"If the user sends another message before the flow completes, the flow runs to completion,
> but the agent responds to the user's latest request without waiting for the flow to finish
> first."*

So ask the agent something else while the card is still unanswered, and confirm the HR answer
**still arrives afterwards**. Employees will do this in practice.

### And the timeout case

Temporarily set the card timeout to `PT5M`, leave it unanswered, and confirm the employee
receives the timeout message. Set it back to `PT8H` afterwards.

---

## Step D.8 — Brief the representatives

Anonymity is a *convention* as much as a configuration. It survives only if the humans
cooperate.

Tell representatives:
- **Do not sign your answer.** Typing `— Jane` in the answer box defeats the entire design.
- **Do not follow up from your own mailbox or start a Teams chat** with the employee.
- Everything you type in the card goes verbatim to the employee.
- Agree who answers, so one person claims each card. Only the **first** submission counts.

---

## Alternatives worth knowing about

Two variations exist. **Neither is recommended over the build above** — they are here so you
recognise them if you need them.

### If long waits turn out not to work

If the long-wait test in [Step D.7](#step-d7--publish-and-test-end-to-end) shows callbacks are
*not* delivered after several hours, you have two options, in order of preference:

1. **Shorten the window.** Set the card timeout to `PT30M`–`PT2H` and staff the channel during
   business hours. Everything else in this guide stays as written.
2. **Deliver by proactive message instead.** Remove the **Respond to the agent** action, and
   add a **Post message in a chat or channel** action configured with
   **Post as → `Microsoft Copilot Studio agent`** and **Post in → `Chat with agent`**. See
   [Send proactive Microsoft Teams messages](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message).

   Proactive messages are explicitly designed to reach a user *outside* an active conversation,
   which is exactly the failure mode in question. The costs: the employee must still have the
   agent **installed** (delivery fails with status `100` otherwise), and proactive messages
   *"don't appear in conversation transcripts or analytics session data."*

   💡 **Agent identity works here but not in [Step D.3](#step-d3--post-the-card-and-wait-for-an-answer)** —
   because this posts to a **personal chat**, which is the only destination
   `Microsoft Copilot Studio agent` supports. The channel card must use `Flow bot`.

   ⚠️ `Post as` must **never** be `User` — that sends the message as the account signed in to
   the Teams connector, usually the flow owner, and anonymity is lost immediately.

### If HR would rather answer from Outlook

Copilot Studio has a built-in
**[Request for information](https://learn.microsoft.com/microsoft-copilot-studio/flows-request-for-information)**
action (under **Human review**) that replaces Steps D.3–D.4: it pauses the flow, emails
designated reviewers, collects typed input, and resumes with their answers.

| | Card build (this guide) | Request for information |
|---|---|---|
| Where HR responds | Teams channel card | **Outlook email** |
| Setup effort | Hand-written JSON, timeout branch | A few fields in the designer |
| Typed/validated inputs | Manual | ✅ Built in |
| **Shared visible queue** | ✅ Whole channel sees it | ❌ Individual emails — nobody sees what is outstanding |

The anonymous delivery step ([Step D.5](#step-d5--return-the-answer-to-the-agent)) is identical
either way, so anonymity holds in both.

⚠️ **Constraints Microsoft states explicitly:** Outlook only; cannot be sent outside your
tenant; a known issue where outputs come back wrapped in `{{ }}` unless input names are
configured without spaces.

⚠️ **This does not sidestep the long-wait risk.** An RFI pauses the flow waiting on a human
exactly as the card does, so it depends on the same asynchronous callback surviving the wait.

---

## Pros and cons

**✅ Pros**

| Advantage | Detail |
|---|---|
| **Anonymous by design** | Anonymity comes from the transport, not a setting that can fail open |
| **Closes the loop** | The answer reaches the employee |
| **Answer arrives as a normal agent reply** | The flow returns it directly — no separate delivery step, and no dependency on the agent still being installed |
| **Visible to Copilot Studio analytics** | The answer is an ordinary agent turn, so it appears in transcripts and session data |
| Likely no new licence | Teams connector actions are standard, not premium |
| No code change | `function_app.py` untouched |
| No authentication change | Keeps "Authenticate with Microsoft" — `send_hr_email` unaffected |
| Human answers, agent delivery | Real expertise, no identity exposure |
| Built-in timeout | The employee is told when nobody responds |
| Auditable | Flow run history records who answered what |
| Reversible | Delete the flow and the topic branch |

**❌ Cons**

| Limitation | Consequence |
|---|---|
| **Callback delivery over long waits is unverified** | Microsoft documents no callback expiry, but also no guarantee. Evidence favours it working in Teams. **Test at your intended wait time before rollout** — see [The unresolved risk](#the-unresolved-risk--the-flow-outlives-the-conversation) |
| **Failure is silent if it does occur** | The flow run reports Succeeded even if the employee never receives the answer |
| **Depends on Asynchronous response** | Requires an environment on the new Power Automate infrastructure; the toggle is **off by default on every flow** |
| **Capacity exhaustion disables escalation silently** | Agent flow runs are blocked while the agent keeps answering — a partial outage nobody reports. See [Copilot Credits](#️-copilot-credits--the-cost-axis-that-can-switch-this-feature-off) |
| **Not portable to all channels** | Callbacks are unsupported on **Microsoft 365 Copilot and telephony**; fine for Teams |
| One round trip per card | No follow-up question in the same thread |
| First response wins | Later submissions ignored |
| Card submits once | A rep cannot revise an answer |
| No routing | Every rep sees every card |
| Channel noise at volume | Microsoft names this — built-in connectors *"own the delivery channel."* See [the CAT post on custom human-in-the-loop](https://microsoft.github.io/mcscatblog/posts/human-in-the-loop-custom-connector/) |
| 30-day ceiling | Mitigated by the timeout in [Step D.4](#step-d4--add-a-timeout-path) |
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

> ⚠️ **Anonymity and transparency pull in opposite directions.** Hiding **who** answered is
> fine; obscuring **that a human answered** is not — Microsoft's Responsible AI guidance makes
> that disclosure a requirement. How to satisfy both is the next section:
> [Making it clear which answers came from a person](#making-it-clear-which-answers-came-from-a-person).

### The human factor

Every technical control here can be undone by one person signing their name.
[Step D.8](#step-d8--brief-the-representatives) is not optional — it is load-bearing.

---

## Making it clear which answers came from a person

Anonymity hides **who** answered. Transparency reveals **what kind of thing** answered. They
are opposite obligations, and you must satisfy both.

### Why async makes this harder

Under the old proactive-message design, a human answer arrived as a visibly different message.
Under this build it returns as **the flow's value, spoken by the agent** — so it lands in the
same conversation, from the same sender, in the same visual style as everything the model
generates. Nothing distinguishes them unless you add the distinction yourself.

Microsoft's requirement is explicit:

> *"Agents should make clear when the user is interacting with an agent and when they're
> receiving a response from a human."*
> — [Smart onboarding agent architecture](https://learn.microsoft.com/power-platform/architecture/solution-ideas/onboarding-agent)

And more broadly, on transparency:

> *"Clearly communicate the presence and role of AI within the product experience… clear
> indicators, like labels such as 'AI-generated content may be incorrect,' help set
> appropriate expectations."*
> — [Responsible AI for agent design](https://learn.microsoft.com/agents/design-guidelines/responsible-ai)

### The four message types your employee will see

This is the part most designs miss. There are **four** kinds of message in this feature, not
two, and only one of them is written by a human:

| # | Message | Who authored it | Must be labelled |
|---|---|---|---|
| 1 | The agent's normal answers | **The model** (via `agent_httptrigger`) | AI-generated |
| 2 | "I've sent your question to HR" | **You** (scripted topic text) | Automated |
| 3 | The relayed answer | **A real person** | **Human** |
| 4 | The timeout message | **You** (scripted, no human involved) | Automated |

⚠️ **Message 4 is the trap.** It arrives in the same place, at the same point in the flow, and
through the same mechanism as message 3. If it is not clearly marked as automated, an employee
will reasonably read *"Nobody from HR answered…"* as something a person typed.

### How to label them

Use a **consistent visual marker** so employees learn it. Pick one convention and apply it
everywhere.

**For the human answer** — set the `Answer` output in
[Step D.5](#step-d5--return-the-answer-to-the-agent) to:

```
💬 **Answered by a person on the HR benefits team**

<the "answer" output from the adaptive card>

—
Individual responders are not identified. If you need more help, just ask me again.
```

**For the timeout message** — same step, the timeout branch:

```
🤖 **Automated message**

Nobody from HR has answered yet. Your question has been recorded and someone will
follow up with you by email.
```

**For the acknowledgement** in [Step D.6](#step-d6--wire-the-flow-into-the-topic), set the
expectation *before* the wait so the labelling makes sense when it arrives:

> `I've sent your question to a person on the HR team. I'll post their reply here — it will be marked as coming from a person.`

**For the agent's own answers**, add a standard AI disclosure to your existing generative
responses, following Microsoft's example wording: *"AI-generated — may be incorrect."*

> 💡 **Why emoji plus bold text, rather than one or the other.** Teams renders a limited
> Markdown subset, and screen readers announce emoji names aloud. The bold label carries the
> meaning; the emoji makes it scannable. Do not rely on the emoji alone.

### Two rules that protect the distinction

⚠️ **1. Never let the model rewrite a human answer.** Pass the flow's `Answer` output straight
into a **Send a message** node, which renders text verbatim. If you route it through a
generative node or ask the model to summarise or "improve" it, the reply becomes
model-generated text *about* a human answer — and your label becomes false. This is the single
easiest way to break transparency without noticing.

⚠️ **2. Label at the source, not in the topic.** Put the wording inside the **flow's** `Answer`
output rather than adding it in the Copilot Studio topic. If a callback ever arrives after the
topic's variables have been reset — one of the documented outcomes in
[The unresolved risk](#the-unresolved-risk--the-flow-outlives-the-conversation) — the flow's
text still carries the label, while topic-side wording could be lost.

### What to tell employees up front

One line in your agent's greeting or help topic prevents most confusion:

> `Most of my answers are AI-generated from HR benefits documents. If I can't answer, I can send your question to a person on the HR team — their reply will be clearly marked as coming from a person.`

✅ **Checkpoint:** ask a question you know the agent cannot answer, escalate it, and confirm the
employee can tell at a glance which of the four message types each reply is.

---

## Optional — Add telemetry so Power BI stays complete

Consider recording that a representative was requested. Without it, your Power BI dashboard
shows failed answers and emails sent — but escalations become invisible, and the deflection
analysis silently understates demand.

✅ **Good news for this build:** because the answer returns as a normal agent turn rather than
a proactive message, it is **not** subject to the *"proactive messages don't appear in
conversation transcripts or analytics session data"* limitation. Copilot Studio analytics will
see the conversation.

⚠️ **But telemetry is your only detector for the silent-failure mode.** If a callback is ever
dropped, the flow still reports success and nothing surfaces the loss. Emitting an event when
an escalation is **raised**, and a second when an answer is **returned**, lets you reconcile
the two counts. A persistent gap between them is the signal that answers are being lost — see
[The unresolved risk](#the-unresolved-risk--the-flow-outlives-the-conversation).

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
| `FlowActionTimedOut` after ~100 s | **Asynchronous response is Off** | Response action → **Settings** → turn **Asynchronous response** **On** ([Step D.5](#step-d5--return-the-answer-to-the-agent)) |
| Agent replies instantly with an empty answer | Environment does not actually support async, so it returned "flow completed" early | Verify `environmentFlowHostingType` is `SelfHostMultiTenant` |
| `Error code: 3000` | Async is On but the environment is on old infrastructure | Same check as above; if `LogicApps`, async is unavailable |
| Employee never gets a reply, flow still running | No response action on the branch that ran | Every branch must end in **Respond to the agent** with the same outputs |
| Answer arrives blank | Returned `submitActionId` instead of `answer` | Map the `Answer` output to the **`answer`** value |
| No `answer` token in the lightning-bolt picker | Card JSON is pasted content, so the designer cannot infer its schema — only **Body** is offered | Use the **`fx`** expression button instead ([Step D.5](#step-d5--return-the-answer-to-the-agent)). Do not select **Body** |
| Flow's `Answer` output missing in Copilot Studio | Flow not published after outputs were added, or the tool schema is cached | Publish the flow, reload Copilot Studio, then **…** → **Refresh** on the tool node ([Step D.6](#step-d6--wire-the-flow-into-the-topic)) |
| Employee sees the "Answered by a person" label twice | Disclosure wording added in **both** the flow output and the topic message | Keep it only in the flow's `Answer` value; the topic node should send the variable alone |
| Answer arrives as raw JSON | Selected **Body** from the picker | Replace with the `fx` expression targeting the `answer` value |
| Answer never arrives after a long wait; run shows Succeeded | Possible callback expiry — undocumented | Test at your target duration; see [The unresolved risk](#the-unresolved-risk--the-flow-outlives-the-conversation) |
| Escalation stops working but the agent still answers normally | **Copilot Studio capacity exhausted** — new agent flow runs are blocked while the parent agent keeps working | Check **Agent flow actions** in the Power Platform admin center; reallocate credits or enable pay-as-you-go |
| Nobody answered and the employee got no message at all | Timeout branch missing, added **sequentially** instead of as a parallel branch, or **Configure run after** not set | The second response action must branch off the **card action**, not follow the first response action ([Step D.5](#step-d5--return-the-answer-to-the-agent)) |
| Employee gets the real answer **and then** "nobody answered" | Second response action was added sequentially, so both fire | Re-add it as a **parallel branch** off the card action |
| Auth prompt or failure on the delivering turn | **Connector tokens can expire during long Teams threads** | Documented Teams risk; have the employee reauthenticate, or shorten the wait window |
| Agent behaves oddly in a long-lived thread | Teams keeps conversation history indefinitely; context accumulates | `/debug clearstate` in the Teams chat resets conversation state |
| Card posts, but buttons error | Used the plain "post" action | Use **"…and wait for a response"** |
| **Post in** is a free-text box instead of a dropdown | **Post as** is set to `Microsoft Copilot Studio agent`, which only supports personal chats | Set **Post as** to `Flow bot` ([Step D.3](#step-d3--post-the-card-and-wait-for-an-answer)). Do not paste a channel ID into the text box |
| Sign-in popup blocked when adding the Teams action | The connector uses OAuth and needs a popup | Allow popups **and** third-party cookies for `[*.]powerautomate.com` and `[*.]microsoft.us`, then retry. If sign-in loops, sign out *inside* the popup and back in within the same window |
| Card never appears | **Private or shared channel** (bots are not supported in either), or Workflows app not enabled | Use a **standard** channel — the team's own privacy setting is irrelevant. Check the Workflows app in Teams admin center |
| Reps say cards render oddly or replies look out of order | Channel is on the **Threads** layout, or reps are mid-rollout with **mixed views** | Switch the channel to **Posts** ([Step D.1](#step-d1--create-the-hr-intake-channel)). Teams warns that mixed views can disconnect messages from threads and affect notifications |
| Reps miss new cards despite notifications being on | Threads layout — thread replies do **not** bold the channel name, by design | Use the **Posts** layout; there is no setting to change the Threads behaviour |
| Card looks unanswered after submitting | **Update message** not configured | Set **Update message** ([Step D.3](#step-d3--post-the-card-and-wait-for-an-answer)) |
| Two reps answer the same question | First response wins; card reset | Configure the update message; brief the team |
| `OperationTimedOut` | Nobody answered | Expected — the timeout path handles it ([Step D.4](#step-d4--add-a-timeout-path)) |
| Question text empty on the card | Hand-typed `triggerBody()` | Re-insert via the lightning bolt icon |
| Rep's name appears in the answer | The rep signed it | Brief them ([Step D.8](#step-d8--brief-the-representatives)) |
| `FlowActionBadRequest` | Flow inputs/outputs changed without refreshing | Reload Copilot Studio, re-map the inputs, republish |
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

**Q: How can a flow wait hours when agent flows must respond in 100 seconds?**
Because **Asynchronous response** is turned on. Microsoft: *"Asynchronous flows continue
running beyond the previous two-minute limit while still returning a response to the agent
after execution completes."* If anyone turns it off, the feature breaks immediately — every
escalation fails with `FlowActionTimedOut` after about 100 seconds. It is a per-flow setting,
so anyone editing the flow can affect it. Worth noting in your runbook.

**Q: The flow can run for 30 days — so can a rep answer 3 days later?**
The flow will still be running, and Microsoft documents no expiry on the callback. But it also
gives no guarantee, and no published example waits that long on a human. Teams threads persist
indefinitely, which is encouraging, but treat multi-day waits as unproven until you test them.
Be wary of one trap: the widely-quoted "30-minute" and "60-minute" session figures come from a
**legacy billing article** and describe billed sessions, not message delivery. See
[The unresolved risk](#the-unresolved-risk--the-flow-outlives-the-conversation).

**Q: How would we even know if answers were being lost?**
You would not, from the flow alone — a dropped callback still reports a successful run. That
is the strongest argument for adding the telemetry event and reconciling "escalations raised"
against "answers delivered."

**Q: Does the employee have to keep the agent installed for the answer to arrive?**
No — and that is one of the main advantages here. The answer returns as the flow's own result
and the agent speaks it in the existing conversation, so there is no separate delivery step
that can fail because the agent was removed.

**Q: What happens if the employee asks something else while waiting?**
Microsoft documents this: *"the flow runs to completion, but the agent responds to the user's
latest request without waiting for the flow to finish first."* The HR answer still arrives
afterwards. Test this case — employees do it routinely.

**Q: Will escalations show up in Copilot Studio analytics?**
The answer arrives as a normal agent turn rather than an excluded proactive message, so it is
not subject to the *"proactive messages don't appear in conversation transcripts or analytics
session data"* limitation. Add the telemetry event anyway if you want escalation counts in
Power BI alongside your existing events.

**Q: Does this send data outside our tenant?**
No. Everything stays inside Microsoft 365 / Power Platform in your GCC tenant. Note that
Variant D2 uses Outlook and *"can't be sent to users outside of your tenant."*

**Q: Can we audit who answered what?**
Yes. Power Automate run history shows exactly which account submitted which card. **Anonymity
is from the employee, not from compliance.**

**Q: What happens if the flow fails?**
The user sees a generic Copilot Studio error. Because the flow now holds the conversation open
until it returns, add a fallback message telling them to use "Email HR" instead.

**Q: What if nobody answers?**
The timeout branch fires ([Step D.4](#step-d4--add-a-timeout-path)) and the employee is told.
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

## References

Grouped by how close each item is to the build you are doing. **Tier 1 is what you actually
need.** Everything below it is there to resolve a specific problem or decision, and every
entry says which one.

### Tier 1 — read these before you build

The five that carry this design. If you read nothing else, read these.

| Resource | Why it matters here |
|---|---|
| [**Asynchronous response support for agent flows**](https://learn.microsoft.com/microsoft-copilot-studio/flow-asynchronous-response) | ⭐ **The basis of this build.** Enabling the toggle; Teams callback support; what happens in an environment without it |
| [**Power Automate environments move to new architecture**](https://learn.microsoft.com/power-automate/environment-architecture) | The environment prerequisite for async; how to check `environmentFlowHostingType` |
| [**Create your first adaptive card**](https://learn.microsoft.com/power-automate/create-adaptive-cards) | The post-card-and-wait walkthrough — the exact action [Step D.3](#step-d3--post-the-card-and-wait-for-an-answer) uses. Also states the **Workflows app** prerequisite |
| [**Create an agent flow as a tool**](https://learn.microsoft.com/microsoft-copilot-studio/advanced-flow-create) | The **100-second limit** async lifts; the 30-day ceiling behind [Step D.4](#step-d4--add-a-timeout-path); the solution requirement |
| [**Modify an existing flow to use with an agent**](https://learn.microsoft.com/microsoft-copilot-studio/flow-modify-use-with-agent) | **Same outputs at every branch** — the rule [Step D.5](#step-d5--return-the-answer-to-the-agent)'s two response actions must satisfy. ⚠️ Predates async; **ignore its "set Asynchronous response Off" instruction** |

### Tier 2 — while building the card (Step D.3)

| Resource | Why it matters here |
|---|---|
| [Overview of adaptive cards for Power Automate](https://learn.microsoft.com/power-automate/overview-adaptive-cards) | Why the plain "post" action fails; single-submit limit; **Update message** behaviour; DoD exclusion |
| [Adaptive Cards overview (Copilot Studio)](https://learn.microsoft.com/microsoft-copilot-studio/adaptive-cards-overview) | **Teams caps schema at 1.5** — read before editing the card JSON |
| [Lead collection sample](https://learn.microsoft.com/power-automate/lead-collection-sample) | Proves `Input.Text` `id` → output token — the mechanism behind the `answer` token |
| [Ask with Adaptive Cards](https://learn.microsoft.com/microsoft-copilot-studio/authoring-ask-with-adaptive-card) | Submit-button behaviour with **consecutive cards** — your HR channel will accumulate similar-looking ones |
| [Adaptive Cards Designer](https://adaptivecards.io/designer/) | Visual editing — **set target version to 1.5 or lower** before copying JSON back |

### Tier 3 — when something breaks

| Resource | Why it matters here |
|---|---|
| [Understand error codes](https://learn.microsoft.com/troubleshoot/power-platform/copilot-studio/authoring/error-codes) | **`FlowActionTimedOut`** — what you see if the async toggle is Off. Also `3000` |
| [FlowActionBadRequest in channels](https://learn.microsoft.com/troubleshoot/power-platform/copilot-studio/channels/agent-flow-action-bad-request) | **Output-name mismatch between branches** — the most likely error after Step D.5 |
| [Cloud flow error code reference](https://learn.microsoft.com/power-automate/error-reference) | `OperationTimedOut` and **Configure run after** — how Step D.5's timeout branch works |
| [Billing rates and management](https://learn.microsoft.com/microsoft-copilot-studio/requirements-messages-management) | ⚠️ **Capacity exhaustion blocks agent flow runs** while the agent keeps answering — escalation dies silently. Also the M365 Copilot exemption and pay-as-you-go |
| [Agent flows overview](https://learn.microsoft.com/microsoft-copilot-studio/flows-overview) | Capacity per run; **test runs are free**, so the long-wait tests cost nothing |
| [Best Practices for Deploying Agents in Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment-ux/) | Why Teams serves a stale agent version — behind two troubleshooting rows |

### Tier 4 — the unresolved long-wait risk

Everything bearing on [the one open question](#the-unresolved-risk--the-flow-outlives-the-conversation).

| Resource | Why it matters here |
|---|---|
| [Deploy agents in Microsoft Teams](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deploy-agent-teams) | Teams threads persist *"indefinitely"* — **the main evidence the long wait should work**. Also documents token expiry over long threads |
| [Inactivity trigger](https://learn.microsoft.com/microsoft-copilot-studio/guidance/inactivity-trigger-guidance) | Teams persistent-conversation model; 30-minute transcript boundary (**not** a delivery limit) |
| [Manage sessions and capacity](https://learn.microsoft.com/microsoft-copilot-studio/requirements-sessions-management) | ⚠️ **Legacy billing article.** Listed *only* so you do not misread its 30/60-minute figures as callback deadlines |

### Tier 5 — configuration facts this build depends on

| Resource | Why it matters here |
|---|---|
| [Copilot Studio US Government service URLs](https://learn.microsoft.com/microsoft-copilot-studio/requirements-licensing-gcc#microsoft-copilot-studio-us-government-service-urls) | **Authoritative GCC portal addresses** — they are not `.com` → `.us` swaps |
| [Variables overview](https://learn.microsoft.com/microsoft-copilot-studio/authoring-variables-about) | `System.User.PrincipalName` and other system variables mapped in Step D.6 |
| [Add user authentication to topics](https://learn.microsoft.com/microsoft-copilot-studio/advanced-end-user-authentication) | Why those variables are empty without **Authenticate with Microsoft** |
| [Channel experience reference table](https://learn.microsoft.com/microsoft-copilot-studio/publication-fundamentals-publish-channels#channel-experience-reference-table) | **Six-option cap** on multiple choice in Teams |
| [Plan for government clouds](https://learn.microsoft.com/microsoftteams/platform/concepts/cloud-overview) | Workflows app available in GCC, not GCC High/DoD |
| [Teams channel feature comparison](https://learn.microsoft.com/microsoftteams/teams-channels-overview#channel-feature-comparison) | **Bots and connectors are standard-channel only** — the constraint behind [Step D.1](#step-d1--create-the-hr-intake-channel). Team privacy is a separate setting |
| [Channel resource type — `layoutType`](https://learn.microsoft.com/graph/api/resources/channel) | Confirms **Posts** and **Threads** (`post` / `chat`) are the two layouts, and that either can be set per channel |

### Tier 6 — transparency and escalation design

| Resource | Why it matters here |
|---|---|
| [Smart onboarding agent architecture](https://learn.microsoft.com/power-platform/architecture/solution-ideas/onboarding-agent) | **"Make clear when the user is… receiving a response from a human"** — the requirement behind [the labelling section](#making-it-clear-which-answers-came-from-a-person) |
| [Responsible AI for agent design](https://learn.microsoft.com/agents/design-guidelines/responsible-ai) | The transparency principle; example label *"AI-generated content may be incorrect"* |
| [Alternate escalation paths](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-alternate-escalation-paths) | Operating-hours checks — prevents an employee asking at 22:00 and waiting out the timeout |
| [Building a Custom Human-in-the-Loop Experience](https://microsoft.github.io/mcscatblog/posts/human-in-the-loop-custom-connector/) | **Names this design's scaling limit** — connectors *"own the delivery channel."* The sanctioned next step if channel noise becomes real |

### Tier 7 — working code and worked examples

| Resource | Why it matters here |
|---|---|
| [contact-center/skill-handoff](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/skill-handoff) | **The closest official analogue to this design** — a live handoff that keeps Teams as the channel. Predates async (so it uses proactive messaging), but confirms the overall shape |
| [Register response from custom Adaptive Cards](https://poszytek.eu/en/microsoft-en/office-365-en/powerautomate-en/register-response-from-custom-adaptive-cards-sent-from-power-automate-to-teams/) | Tomasz Poszytek (**MVP**) — the `answer` token mechanism worked through end to end |
| [Build Power Automate flows for your agent](https://learn.microsoft.com/training/modules/build-flows-chatbot-online-workshop/) | Guided practice at calling a flow from a topic — exactly what [Step D.6](#step-d6--wire-the-flow-into-the-topic) does |
| [Power CAT Copilot Agent Kit](https://github.com/microsoft/Power-CAT-Copilot-Studio-Kit) | Agent Insights Hub — possible alternative to building the Power BI dashboard. **GCC support unverified** |

⚠️ **Third-party and training material is unversioned and assumes a commercial tenant.**
Substitute your GCC addresses (`gcc.powerva.microsoft.us`, `gov.flow.microsoft.us`) and expect
screenshot mismatches. Use them for *mechanics*, then confirm against the official docs.

### Tier 8 — only if you take an alternative

See [Alternatives worth knowing about](#alternatives-worth-knowing-about). You do not need
these for the recommended build.

| Resource | Why it matters here |
|---|---|
| [Request for information (RFI)](https://learn.microsoft.com/microsoft-copilot-studio/flows-request-for-information) | The **Outlook alternative** to the Teams card — Outlook-only; no external users; `{{ }}` known issue |
| [Send proactive Microsoft Teams messages](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message) | The **fallback if long waits fail** — Post as agent / Chat with agent; installation prerequisite; status codes `100`/`300`; **excluded from transcripts and analytics** |
| [Send a message in Teams using Power Automate](https://learn.microsoft.com/power-automate/teams/send-a-message-in-teams) | Proactive fallback — every Post as / Post in combination |
| [Share an agent](https://learn.microsoft.com/microsoft-copilot-studio/admin-share-bots) | Proactive fallback — permission prerequisite for delivery |

### Your own repository

| Document | Why it matters here |
|---|---|
| `COPILOT_STUDIO_SETUP_GUIDE.md` | Click-by-click guide for the existing "Email HR" flow — same patterns, already working |
| `EMAIL_HR_DEPLOYMENT_CHECKLIST.md` | Section 5: authentication dependency. Section 9: variable mappings |
| `CUSTOM_FEEDBACK_SETUP_GUIDE.md` | A second worked Copilot Studio → flow → Function example |
| `ANALYTICS_KQL_QUERIES.md` | Existing event schema, if you add the telemetry event |

---

## Glossary

| Term | Meaning |
|---|---|
| **Adaptive Card** | A JSON-defined interactive block that renders natively in Teams |
| **Agent** | Two meanings. *AI agent* = the bot. *Live agent* = a human |
| **Agent flow** | A flow with the **When an agent calls the flow** trigger, callable from a topic |
| **Asynchronous response** | The per-action setting this build depends on. With it **On**, a flow may run past the 100-second limit and return its result to the agent when it finishes ([Step D.5](#step-d5--return-the-answer-to-the-agent)) |
| **Callback** | The delayed result an asynchronous flow sends back to the agent once it completes |
| **Channel** (Teams) | A named section inside a team |
| **Configure run after** | The per-action setting controlling which predecessor outcomes (succeeded / failed / timed out) allow an action to run. Used to build the timeout branch |
| **Copilot Credits** | The usage meter agent flows consume. Exhausting the environment's capacity **blocks new agent flow runs** |
| **`FlowActionTimedOut`** | The error when a flow fails to answer the agent within 100 seconds. Under this build it means **Asynchronous response is Off** |
| **Flow bot** | The generic bot identity Power Automate posts as when a message is not tied to a person. **Used by this build** to post the card into the HR channel ([Step D.3](#step-d3--post-the-card-and-wait-for-an-answer)) — the employee never sees it |
| **GCC** | Government Community Cloud. **Not** the same as GCC High |
| **ISO 8601 duration** | A timeout format. `PT8H` = 8 hours, `PT5M` = 5 minutes |
| **Maker** | Someone permitted to build agents and flows |
| **Post as** / **Post in** | The two Teams-connector settings controlling sender identity and destination. This build uses **`Flow bot`** + **`Channel`**. `Microsoft Copilot Studio agent` supports personal chats only; `User` would expose the flow owner and must never be used |
| **Proactive message** | A message an agent sends without the user prompting it. Not used by this build — only by the [fallback](#alternatives-worth-knowing-about) if long waits fail |
| **RFI** | Request for information — a built-in pause-and-ask-a-human action that emails reviewers instead of posting a card. See [Alternatives](#alternatives-worth-knowing-about) |
| **Solution** | A Power Platform container; flows must be in one to be callable by an agent |
| **Token** (dynamic content) | A value produced by an earlier action, inserted via the lightning-bolt picker. ⚠️ Values from a **pasted** Adaptive Card do not appear as tokens — retrieve them with an **`fx`** expression |
| **Topic** | A conversation script |
| **Update message** | The text replacing the card after submission, so a second rep does not answer the same question |
| **UPN** | User Principal Name — usually the sign-in email address |
