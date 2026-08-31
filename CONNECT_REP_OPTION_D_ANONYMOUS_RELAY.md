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

> ## 📨 How the answer comes back: proactive delivery
>
> The flow **fires and returns control immediately**, then delivers HR's answer later as a
> **[proactive Teams message](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message)**
> from your agent.
>
> This is Microsoft's documented mode for exactly this shape: *"If your environment supports
> asynchronous response but you want the agent to respond immediately, remove the response
> action from the flow. The agent then responds immediately after it successfully triggers
> the flow."*
>
> **Why not have the flow return the answer directly?** That approach — keeping
> `Respond to the agent` and enabling **Asynchronous response** — was built and tested, and it
> has a confirmed defect: **the agent stops answering other questions** while a card is
> pending, replying *"I was unable to find information…"* until HR responds. A flow invoked as
> a tool holds the topic open regardless of the async setting. See
> [Why not return the answer from the flow?](#why-not-return-the-answer-from-the-flow).
>
> **What proactive delivery costs you:** the answer does not appear in Copilot Studio
> analytics, and the employee must still have the agent installed in Teams. Both are covered
> below — neither is close to as damaging as an agent that goes deaf for hours.

---

## Table of contents

- [How to use this document](#how-to-use-this-document)
- [Your scenario — verified facts](#your-scenario--verified-facts)
- [A note on Power Automate licensing](#a-note-on-power-automate-licensing)
- [Background — how the current feature works](#background--how-the-current-feature-works)
- [How the relay works](#how-the-relay-works)
- [How the agent keeps answering while the flow waits](#how-the-agent-keeps-answering-while-the-flow-waits)
- [Why not return the answer from the flow?](#why-not-return-the-answer-from-the-flow)
- [What proactive delivery requires](#what-proactive-delivery-requires)
- [Step D.1 — Create the HR intake channel](#step-d1--create-the-hr-intake-channel)
- [Step D.2 — Create the flow and define its inputs](#step-d2--create-the-flow-and-define-its-inputs)
- [Step D.3 — Post the card and wait for an answer](#step-d3--post-the-card-and-wait-for-an-answer)
- [Step D.4 — Add a timeout path](#step-d4--add-a-timeout-path)
- [Step D.5 — Deliver the answer proactively](#step-d5--deliver-the-answer-proactively)
- [Step D.6 — Wire the flow into the topic](#step-d6--wire-the-flow-into-the-topic)
- [Step D.7 — Publish and test end to end](#step-d7--publish-and-test-end-to-end)
- [Step D.8 — Brief the representatives](#step-d8--brief-the-representatives)
- [Alternatives worth knowing about](#alternatives-worth-knowing-about)
- [Pros and cons](#pros-and-cons)
- [Anonymity — what it does and does not protect](#anonymity--what-it-does-and-does-not-protect)
- [Making it clear which answers came from a person](#making-it-clear-which-answers-came-from-a-person)
- [Telemetry — near-mandatory for this build](#telemetry--near-mandatory-for-this-build)
- [Troubleshooting](#troubleshooting)
- [Technical questions you are likely to be asked](#technical-questions-you-are-likely-to-be-asked)
- [References](#references)
- [Glossary](#glossary)

---

## How to use this document

### Before you build anything

1. Read [Why not return the answer from the flow?](#why-not-return-the-answer-from-the-flow)
   and [What proactive delivery requires](#what-proactive-delivery-requires). Together they
   explain why the build is shaped the way it is.
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
| Agent channel | **Microsoft Teams** | Proactive delivery targets a personal Teams chat |
| Agent installed by the employee | **Yes, by definition** | They just used it to ask — the prerequisite for proactive delivery |
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

### The flow, block by block

Every block below is one action in Power Automate. There are **six**, and the two delivery
actions are *parallel branches* off the card — not a straight line.

```
┌─────────────────────────────────────────────────────────────────────┐
│  1  TRIGGER   "When an agent calls the flow"                        │
│               Inputs:  Question · UserEmail · UserName ·            │
│                        ConversationId                               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               v
┌─────────────────────────────────────────────────────────────────────┐
│  2  TEAMS     "Post adaptive card and wait for a response"          │
│               Post as : Flow bot          ← channel needs Flow bot  │
│               Post in : Channel           ← the HR intake channel   │
│               Timeout : PT8H                                        │
│                                                                     │
│               ⏸  THE FLOW PAUSES HERE — minutes or hours            │
│                  (the agent is NOT waiting; see below)              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
     is successful                     has timed out
     (a rep answered)                  OR has failed
              │                                 │
              v                                 v
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│  3  TEAMS                    │  │  4  TEAMS                        │
│  "Post message in a chat     │  │  "Post message in a chat         │
│   or channel"                │  │   or channel"                    │
│                              │  │                                  │
│  Post as  : Copilot Studio   │  │  Post as  : Copilot Studio       │
│             agent            │  │             agent                │
│  Post in  : Chat with agent  │  │  Post in  : Chat with agent      │
│  Recipient: UserEmail        │  │  Recipient: UserEmail            │
│                              │  │                                  │
│  Message:                    │  │  Message:                        │
│   💬 Answered by a person    │  │   🤖 Automated message           │
│   + fx(card answer)          │  │   "Nobody answered yet…"         │
│                              │  │                                  │
│  Advanced options:           │  │  Advanced options: same          │
│   not installed → succeed    │  │                                  │
│   chat active   → SEND       │  │  Run after: has timed out        │
│                              │  │             + has failed         │
└──────────────┬───────────────┘  └──────────────────────────────────┘
               │
               v
      status 200 / 100 / 300
               │
               v
┌─────────────────────────────────────────────────────────────────────┐
│  5  (optional)  Log the delivery status  →  telemetry               │
│                 100 = lost answer, needs an email fallback          │
└─────────────────────────────────────────────────────────────────────┘

        ✗  NO "Respond to the agent" action anywhere in this flow.
           That absence is the whole design — see below.
```

### End to end, including the people

```
Employee (Teams)                                  HR channel (Teams)
      │                                                   │
      │ "What's my dental deductible?"                     │
      v                                                    │
 Copilot Studio topic                                       │
      │  1. sends "I've sent your question to HR…"          │
      │  2. calls the flow  ──────────────────────────────► │ card appears
      │  3. TOPIC ENDS  ← agent is free again (< 1 second)  │
      v                                                    │
 ✅ agent answers other questions normally            (hours pass)
      ▲                                                    │
      │                                        a rep types the answer
      │                                                    │
      │        proactive message, sent AS THE AGENT         │
      └────────────────────────────────────────────────────┘
                💬 "Answered by a person on the HR team…"
```

The employee sees a message from **the agent**. The representative's name appears nowhere in
what the employee receives.

---

## How the agent keeps answering while the flow waits

This is the part that surprises people, and it is the reason the build is shaped this way.

### The key idea: the flow is *fired*, not *awaited*

A Power Automate flow and a Copilot Studio conversation are **two separate processes**. What
determines whether the agent blocks is not how long the flow runs — it is **whether the topic
is waiting for the flow to return something**.

| | Topic waits for a return value | Topic does not (this build) |
|---|---|---|
| Flow has `Respond to the agent`? | Yes | **No** |
| What the topic does after calling | Stays open, holding the conversation | Ends immediately |
| Agent while the card is pending | ❌ Parked in the escalation topic | ✅ Free for any other topic |
| How the answer gets back | The flow's return value | A separate proactive message |

Because this flow has **no response action**, Copilot Studio has nothing to wait for. It hands
the request off and the topic reaches its end — typically in under a second. From the agent's
point of view the escalation is *finished* the moment the card is posted.

The flow, meanwhile, is still sitting at block 2. Those two facts are not in conflict: the
flow's run and the conversation's turn are simply unrelated after the hand-off.

### Walking through a real interleaving

```
 t+0s     Employee: "What's my dental deductible?"
          Agent cannot answer → escalation topic runs
          Topic: "I've sent your question to HR…"
          Topic calls flow  ──►  FLOW STARTS
 t+1s     TOPIC ENDS.  Conversation released.        FLOW: waiting at block 2
          │                                          │
 t+30s    Employee: "How many PTO days do I get?"    │  still waiting
          ✅ Agent answers normally — different       │
             topic, unaffected                       │
          │                                          │
 t+5m     Employee: "What about vision coverage?"    │  still waiting
          ✅ Agent answers normally                   │
          │                                          │
 t+3h                                          HR rep answers the card
          │                                          │  FLOW RESUMES
          │                                          v
          │                                    block 3 runs
          │  ◄──── proactive message ──────────────  │
 t+3h     💬 "Answered by a person on the HR team…"   FLOW ENDS
```

At no point does the employee wait, and at no point is the agent unavailable.

### Why the answer can still find them hours later

The proactive message does **not** reply into the old topic — that topic ended at `t+1s` and no
longer exists. Instead the flow starts a **fresh turn** in the employee's personal chat with
the agent, addressed by `UserEmail`. This is why:

- the wait can exceed any conversation or session limit — there is no conversation to expire;
- the employee can have chatted about ten other things in between;
- the message must carry its own 💬 label, because it arrives with no surrounding context.

⚠️ **The trade-off this creates.** Because delivery is a new turn rather than a reply, it
depends on the employee still having the agent installed, and it does not appear in Copilot
Studio transcripts. Both are covered under
[What proactive delivery requires](#what-proactive-delivery-requires).

### What this does *not* protect against

Two employees escalating at once produce **two independent flow runs** — they do not interfere.
But note what the design does *not* do:

- ❌ It does not let the employee *follow up* on the answer in context. The message arrives as
  a fresh turn; a follow-up question starts a new escalation.
- ❌ It does not guarantee ordering. If someone escalates twice, answers may arrive in either
  order, which is why the message quotes enough context to stand alone.

---

## Why not return the answer from the flow?

There is an obvious-looking alternative: keep a **Respond to the agent** action, switch on
**Asynchronous response**, and let the flow hand the answer back as its own return value. The
answer would then arrive as an ordinary agent reply and appear in Copilot Studio analytics.

**That approach was built and tested. It has a confirmed defect.**

While a card is pending, the agent **stops answering questions it would normally handle**,
replying *"I was unable to find information…"* until HR responds. A flow invoked as a **tool**
holds the topic open until it returns. Asynchronous response lets the flow run past 100 seconds
without failing, but the conversation stays parked in the escalation topic the entire time.

Microsoft documents the opposite:

> *"If the user sends another message before the flow completes, the flow runs to completion,
> but the agent responds to the user's latest request without waiting for the flow to finish
> first."*

That is not the observed behaviour when the flow is invoked as a tool from a topic.
**Removing nodes after the tool call does not help** — that was tested too.

### Why this is the wrong trade for an HR agent

Your agent's main job is answering routine benefits questions. Escalation is the *exception*.
A design where one person's escalation disables the primary function for everyone in that
conversation — for hours — is worse than the costs of proactive delivery.

| | Return from flow (async) | **Proactive delivery (this guide)** |
|---|---|---|
| Agent stays responsive while waiting | ❌ **Confirmed defect** | ✅ Never blocks |
| Answer appears in Copilot Studio analytics | ✅ | ❌ Excluded from transcripts |
| Employee must have the agent installed | Not required | ✅ Required — true here, they just used it |
| Delivery status codes to handle | None | `200` / `100` / `300` |
| Long-wait delivery | ⚠️ Undocumented whether callbacks expire | ✅ Works after the topic has ended |

> ⚠️ **A caution about "just try generative orchestration."** The defect was observed on
> classic orchestration, which parks the conversation in the active topic by design, so
> switching looks tempting. But under generative orchestration Copilot Studio decides for
> itself what to invoke, and your escalation topic *"may be skipped"* — including the node
> that calls your Azure Function. **This has been observed:** after switching, the agent
> answered from knowledge search alone, never called the Function, and lost capabilities that
> previously worked. If you try it, verify in the trace that your Function is still being
> called before concluding anything.

---

## What proactive delivery requires

Three things, all documented by Microsoft in
[Send proactive Microsoft Teams messages](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message).

### 1. The employee must have the agent installed

An agent **cannot** deliver a proactive message if the recipient:

- has not **installed** the agent in Teams,
- has **uninstalled** or **blocked** it, or
- lacks permission to chat with it (you may need to
  [share the agent](https://learn.microsoft.com/microsoft-copilot-studio/admin-share-bots)).

✅ **In your scenario this is satisfied by definition** — the employee just used the agent to
ask the question. The realistic failure is someone who removes the agent while waiting.

⚠️ **GCC: the agent must be admin-approved before anyone can install it.** Microsoft:
*"Currently, the only way to approve an agent for Teams is to submit the agent to an admin for
approval."* Commercial tenants allow self-install from a share link; **GCC does not**. Until an
admin approves the agent, delivery fails with a `403` Graph error rather than a clean status
code — see
[403 Forbidden](#-403-forbidden--did-not-receive-installedapplication).

> 💡 **Test the delivery path before briefing HR.** Being able to chat with the agent in the
> Copilot Studio **test pane** does *not* prove it is installed in Teams for that user, and the
> test pane is not what proactive delivery targets.

### 2. The flow must be in the same environment as the agent

Already true if you created the flow from inside Copilot Studio.

### 3. Delivery is to a personal chat only

Proactive messages go to **a personal chat with the agent** — never to a channel. That is
exactly what you want here.

### 4. Reconnecting the agent to Teams silently breaks delivery

⚠️ Microsoft: *"If the agent disconnects and reconnects to Teams, users don't receive
proactive messages until they reinstall the agent."*

This is an operational trap rather than a build step. If anyone toggles the Teams channel off
and on — a commonly suggested fix for Teams serving a stale agent version — **every employee
must reinstall the agent before proactive delivery works for them again**. Nothing surfaces
this; escalations simply stop arriving.

> 💡 **Add this to your runbook.** If you ever reconnect the Teams channel, expect delivery
> failures and treat a spike in `100` status codes as the signal.

### Delivery status codes

The **Post message in a chat or channel** action returns a status you can branch on:

| Code | Succeeded | Meaning |
|---|---|---|
| `200` | True | Delivered |
| `100` | False | **Agent not installed** — the answer did not reach the employee |
| `300` | False | **Not delivered** — the recipient is in an active conversation with the agent |

⚠️ **Two advanced options decide whether your answer actually arrives.** Both are under
**Show advanced options** on the delivery action, and the defaults are wrong for this build:

| Option | Set it to | Why |
|---|---|---|
| **If the agent is not installed** | *Succeed with status code* | Returns `100` instead of failing the run, so you can log it and fall back |
| **If the chat with the agent is active** | **Send** | ⚠️ **Critical.** Otherwise an employee who is *actively chatting with the agent* never receives the answer — exactly the person most likely to be waiting for it |

⚠️ **Handle `100` explicitly** by branching on the status and logging it. Otherwise a lost
answer looks like a successful run.

### What this does *not* change

- **The 30-day ceiling.** A flow run still cannot exceed 30 days, so you still need an explicit
  timeout — [Step D.4](#step-d4--add-a-timeout-path).
- **The Responsible AI disclosure.** The reply arrives styled as the agent, so it must be
  labelled as human-written — see
  [Making it clear which answers came from a person](#making-it-clear-which-answers-came-from-a-person).
- **Anonymity.** That still comes from the transport, not from a setting.

⚠️ **Proactive messages are excluded from Copilot Studio analytics.** Microsoft: *"proactive
messages don't appear in conversation transcripts or analytics session data."* This makes the
[telemetry event](#telemetry--near-mandatory-for-this-build) near-mandatory rather than
optional.

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
| `UserEmail` | **The delivery address for the answer** ([Step D.5](#step-d5--deliver-the-answer-proactively)); also used for telemetry and any email fallback |
| `UserName` | Who asked — **shown on the card** |
| `ConversationId` | Correlation for telemetry |

> **Action names have changed over time.** The trigger is now called **When an agent calls the
> flow**; older documentation says *"When Copilot Studio calls a flow"*. Same action.

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
> returns *to the employee* — delivered as the agent in
> [Step D.5](#step-d5--deliver-the-answer-proactively) — not from how the card reaches HR. The
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
> [Step D.5](#step-d5--deliver-the-answer-proactively).
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

Nothing else bounds the wait. Without a timeout, an unanswered question hangs until the 30-day
flow limit and the employee is never told.

1. Click the **…** menu on the card action → **Settings**.
2. Set **Timeout** to an ISO 8601 duration — `PT8H` means 8 hours.
3. Click **Done**.

⚠️ **Set this to the window HR can realistically staff.** `PT8H` suits a next-business-day
promise; `PT30M`–`PT2H` suits a staffed channel. The employee is told when it expires, so the
choice is about expectations rather than risk.

> ⚠️ **Important: a timed-out card action does not "continue" — it fails.** Power Automate
> reports `OperationTimedOut`, and by default **every following action is skipped**. If you
> stop here, a timed-out escalation leaves the employee waiting forever with no message at
> all. [Step D.5](#step-d5--deliver-the-answer-proactively) adds the branch that prevents
> this, and it is not optional.

✅ **Checkpoint:** the card action has an explicit timeout shorter than 30 days.

---

## Step D.5 — Deliver the answer proactively

This is the step that produces the anonymity. The answer never travels as a message from a
person — the **agent** delivers it into the employee's personal chat, so the representative's
identity appears nowhere.

> ⚠️ **There is no `Respond to the agent` action in this build.** That is deliberate, not an
> omission. Adding one makes the agent stop answering other questions while a card is pending
> — see [Why not return the answer from the flow?](#why-not-return-the-answer-from-the-flow).

### Add the delivery action

1. After the card action, add **Post message in a chat or channel** (Microsoft Teams
   connector).
2. Set the fields:

   | Field | Value |
   |---|---|
   | **Post as** | **Microsoft Copilot Studio agent** |
   | **Post in** | **Chat with agent** |
   | **Agent** | your HR benefits agent |
   | **Recipient** | the `UserEmail` flow input |

> ⚠️ **`Post as` here is different from the card step.** The card is posted into a *channel*,
> which the agent identity cannot do — that step uses **Flow bot**. This step posts into a
> *personal chat*, which is exactly what the agent identity supports. Getting these the wrong
> way round is the most common mistake in this build.

> ⚠️ **Never set `Post as` to `User`.** That would post as the signed-in representative and
> destroy the anonymity this whole design exists to provide.

3. Set the **Message** to text that **discloses a human wrote it**, with the card's answer
   embedded:

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

> 💡 **Why the label matters.** The message arrives styled as the agent, visually identical to
> model-generated answers. See
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

### Handle undelivered answers

The action returns a status code. Two of the three mean the employee got nothing.

4. On the delivery action, open **Show advanced options** and set **both**:

   | Option | Value |
   |---|---|
   | **If the agent is not installed** | **Succeed with status code** |
   | **If the chat with the agent is active** | **Send** |

⚠️ **The second one is easy to miss and breaks the feature silently.** If it is left on
*Don't send and succeed*, the answer is withheld whenever the employee happens to be chatting
with the agent — and the run still reports Succeeded. Since employees often keep the chat open
while waiting, this would fail for the most engaged users.

| Code | Succeeded | Meaning | What to do |
|---|---|---|---|
| `200` | True | Delivered | Nothing |
| `100` | False | **Agent not installed** — answer lost | Log it; fall back to email |
| `300` | False | **Withheld** — recipient in an active chat | Should not occur once **Send** is set; log if it does |

⚠️ **Without this, a lost answer looks like a successful run.** The flow reports Succeeded, HR
believes they answered, and the employee never hears back. Branch on the status and record it
via the [telemetry event](#telemetry--near-mandatory-for-this-build).

### Handle the timeout branch

> 💡 **Building incrementally? Skip this section for now.** The success path works on its own —
> post a card, have a representative answer it, and the delivery action runs. The timeout
> branch only matters when **nobody** answers. Get the happy path working end to end first,
> then come back and add this **before rollout**.
>
> ⚠️ **But do not skip it permanently.** Without it, an unanswered question leaves the employee
> with **no message at all** — see the warning after the flow diagram below.
>
> 💡 **While testing, shorten the timeout.** `PT8H` means a failed test ties up a run for eight
> hours. Set the card's **Timeout** to `PT15M` during testing and raise it before rollout.

Because a timed-out card action **fails**, the delivery step above is skipped when nobody
answers. You need a second delivery action that runs *only* on that path.

⚠️ **This is a parallel branch, not the next step in the chain.** Both delivery actions hang
off the **card action**. Do not add the second one after the first.

5. Hover the **`+`** on the connector **directly below the card action** — the same connector
   that leads to your first **Post message in a chat or channel**.
6. Choose **Add a parallel branch**, *not* **Add an action**.

   > 💡 If your designer does not offer "Add a parallel branch," add the action anywhere after
   > the card and then set its **Configure run after** — the branch shape follows from the
   > run-after configuration.

7. In the new branch, add a second **Post message in a chat or channel**, configured
   identically (**Post as** Microsoft Copilot Studio agent, **Post in** Chat with agent,
   **Recipient** `UserEmail`).
8. On that action: **…** → **Configure run after** → tick **has timed out** and
   **has failed**; untick **is successful**.
9. Set its **Message** to a timeout notice:

    ```
    🤖 **Automated message**

    Nobody from HR has answered yet. Your question has been recorded and someone will
    follow up with you by email.
    ```

⚠️ **Mark this one as automated.** It arrives through the same mechanism as the human answer,
so without a label an employee will read it as something a person typed.

10. Rename the flow to `Anonymous HR Relay` and click **Save**.

Flow shape — note the **two arrows leaving the card action**:

```
Post adaptive card AND WAIT
    |
    +-- (is successful) ----► Post message in a chat or channel
    |                          as agent → employee's chat
    |                          "💬 Answered by a person..." + <fx expression>
    |
    +-- (has timed out /
         has failed) --------► Post message in a chat or channel
                               as agent → employee's chat
                               "🤖 Automated message..."
```

✅ **Verify the shape on the canvas.** The card action should have **two arrows leaving it**.
If you see a single vertical chain instead, the second delivery action was added
sequentially — delete it and re-add it as a parallel branch.

> ⚠️ **What a *missing* timeout branch looks like.** If the canvas shows a single straight
> chain —
>
> ```
> Post adaptive card and wait for a response
>              |
>              v
> Post message in a chat or channel
> ```
>
> — with only **one** delivery action and no second branch, the timeout path was never built.
> This is easy to miss because the flow works perfectly whenever HR answers in time. It fails
> only when nobody answers: the card action fails with `OperationTimedOut`, the delivery action
> is skipped by default, and **the employee is never told anything at all.** Add the parallel
> branch before rollout.

⚠️ **What goes wrong if it is sequential.** The second action inherits the *first delivery
action* as its predecessor rather than the card. When someone answers, both fire and the
employee gets the real answer followed by "nobody answered." When nobody answers, the first is
skipped and the second evaluates its condition against a skipped action, so neither may run.
Both look correct on the canvas, which makes them slow to diagnose.

> 💡 **Why tick "has failed" as well as "has timed out."** A card action can fail for reasons
> other than a timeout — a deleted channel, a permissions change. Without this, those failures
> also leave the employee waiting silently.

✅ **Checkpoint:** the flow ends with **two** `Post message in a chat or channel` actions — one
on success, one on timeout/failure — and **no `Respond to the agent` action anywhere**.

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

⚠️ **Put this message before the tool call.** It is the last thing the topic says.

5. **End the topic immediately after the tool call.** Add nothing after it.

The flow has no `Respond to the agent` action, so it returns control the instant the card is
posted. There is no `Answer` output to display and nothing to wait for — the answer arrives
later as a separate proactive message.

> 💡 **This is what keeps the agent responsive.** The topic ends, the conversation is released,
> and the employee can carry on asking the agent other questions while HR composes a reply.

⚠️ **Do not add a node to display the flow's output.** There is no output to display. Keeping
the tool call last is also what releases the conversation — see
[Why not return the answer from the flow?](#why-not-return-the-answer-from-the-flow) for why
the blocking defect is caused by the tool call itself, not by any node placed after it.

✅ **Checkpoint:** the topic says its message, calls the tool, and ends. The tool call is the
last node in the branch.

---

## Step D.7 — Publish and test end to end

> 💡 **Test the success path first.** Everything below works with **only the success-path
> delivery action** built. If you have not yet added the timeout branch
> ([Handle the timeout branch](#handle-the-timeout-branch)), that is fine for now — a
> representative answering the card exercises the same delivery action, the same connection,
> and the same Graph lookup. Add the timeout branch before rollout, then run
> [And the timeout case](#and-the-timeout-case).

1. **Save**, then **Publish**.
2. In Teams, ask the agent an unanswerable question and choose **Connect to a representative**.
3. Confirm you get the "I've sent your question" message immediately.
4. Check the HR channel for the card.
5. **While the card is still pending, ask the agent an ordinary benefits question.**
   It must answer normally — this is the check that the blocking defect is gone.
6. **Wait several minutes before answering the card.**
7. As a representative, type an answer and click **Send answer**.
8. As the employee, check for the reply.

✅ **Checkpoint — all seven must be true:**
- The "I've sent your question" message appeared immediately.
- The card reached the HR channel with the question and the employee's name.
- **The agent answered an unrelated question while the card was still pending.**
- The card updated to `Answer sent to the employee.` after submission.
- The answer arrived in the employee's chat with the agent.
- The answer was **visibly marked as written by a person**, and you can tell it apart from the
  agent's own AI-generated answers at a glance.
- **Nowhere in the employee's Teams client does the representative's name appear.**

⚠️ Verify the last two deliberately. Click the sender, open the profile, and confirm it
resolves to the agent and not to a person — then scroll the conversation and check you can
distinguish the human reply from the model's answers without reading closely.

### ⚠️ The answer never arrived — diagnose it here

The most common failure in this build: HR submits the card, the flow reports **Succeeded**, and
nothing reaches the employee. **A green run does not mean the message was delivered.** Two of
the three status codes mean "not delivered" while still succeeding.

**Read the status code first. It identifies the cause in one step.**

1. Power Automate (`gov.flow.microsoft.us`) → **My flows** → `Anonymous HR Relay`.
2. Open the **28-day run history** and select the run.
3. Expand **Post message in a chat or channel**.
4. View **raw outputs** and read the status code.

> ⚠️ **First establish whether the flow even resumed.** A card that was submitted does not
> guarantee the flow continued — see
> [The card was answered but the flow never resumed](#the-card-was-answered-but-the-flow-never-resumed)
> below. If the run is still listed as **Running**, no status code exists yet and the delivery
> action is not your problem.

| What you see | Cause | Fix |
|---|---|---|
| Run still shows **Running** after the card was submitted | The card action never received the response | [See below](#the-card-was-answered-but-the-flow-never-resumed) |
| Action is **greyed out / skipped** | The branch never ran — **Configure run after** is wrong, or the actions are sequential rather than parallel | [Handle the timeout branch](#handle-the-timeout-branch) |
| Action **failed** with **`403 Forbidden`** and *"Did not receive InstalledApplication"* | The Graph lookup for the recipient's installed apps was denied | [See below](#-403-forbidden--did-not-receive-installedapplication) — usually **not installed for that user**, or a **DLP policy** |
| Status **`300`** | **Withheld** — the recipient was in an active chat with the agent | Set **If the chat with the agent is active** to **Send** |
| Status **`100`** | Agent not installed, uninstalled, or blocked for that recipient | Reinstall the agent; check [requirement 1](#1-the-employee-must-have-the-agent-installed) |
| Status **`200`** | **It was delivered** — you are looking in the wrong chat | See the `Post as` check below |
| Action ran but **`Recipient` is blank** in raw inputs | The topic is not passing `UserEmail` | Authentication issue — see [Step D.6](#step-d6--wire-the-flow-into-the-topic) |

⚠️ **If you are testing this yourself, `300` is a likely answer.** You may be sitting in the
agent chat when the reply comes back — which is exactly the condition that triggers it. The
default behaviour withholds the message *and reports success*.

#### The card was answered but the flow never resumed

If the run is still **Running** long after HR submitted the card, the delivery action has not
executed yet and nothing about it is at fault. The card action never received the response.

⚠️ **The most common cause is a mismatch between how the card was posted and how the response
comes back.** *Post adaptive card and wait for a response* only resumes when the submitting
user's response is routed back to that specific waiting run.

| Check | What to look for |
|---|---|
| **Did the card visibly update?** | The **Update message** text (`Answer sent to the employee.`) should replace the input fields after submit. If the card still shows the text box, the response never reached Power Automate |
| **Was the card posted with `Post as` = `Flow bot`?** | Required for channel posts. If it was posted as the agent, the card may render but responses may not route back |
| **Did more than one person submit?** | Only the **first** submission counts; later ones are ignored |
| **Was the flow edited and saved while the card was pending?** | Saving a new version can orphan an in-flight run. The old card is then attached to a run that no longer resumes |
| **Did the run exceed the card timeout?** | After `PT8H` the action fails with `OperationTimedOut` and the *timeout* branch runs instead |

💡 **Fastest way to isolate this:** submit the card and watch the run in Power Automate live.
If the card action stays yellow (Running) after submit, the problem is the **card**, not the
delivery. If it turns green, the problem is downstream.

#### ⚠️ `403 Forbidden` — "Did not receive InstalledApplication"

*(Confirmed in a real GCC build.)* The delivery action fails outright with:

```json
{
    "statusCode": 403,
    "body": {
        "id": "",
        "messageLink": "",
        "error": "Did not receive InstalledApplication and received status code
                   Forbidden from graph while getting installed app for user"
    }
}
```

**What it means.** Before delivering, the connector asks Microsoft Graph *"is this agent
installed for this user?"* That Graph call returned `Forbidden`, so the connector never got an
`InstalledApplication` back and refused to send.

**This is not the `100` status code.** `100` is the graceful "agent not installed" result. This
is the *lookup itself* being denied — the connector could not even determine installation
state. It fails the action rather than returning a status.

**The lookup asks: *"is app X installed for user Y?"*** Both halves must resolve, and the
caller must be permitted to ask.

> ✅ **Already ruled out in this build** *(verified against a real GCC tenant)*:
>
> | Ruled out | How it was confirmed |
> |---|---|
> | Agent not installed for the recipient | The agent appears under **Chat** in the recipient's Teams |
> | Agent not admin-approved | Copilot Studio shows **✓ Available in App store**; Teams admin center shows **Available to: Everyone**, **Scope: Personal**, with *"Send me messages and notifications"* consented |
> | `Recipient` not resolving | The run's **Inputs** show a real, resolving email address |
> | Wrong app in the **Agent** field | The delivery action's **Agent** field names the correct agent |
> | GCC platform limitation | Microsoft's [national cloud differences](https://learn.microsoft.com/graph/teamwork-national-cloud-differences) table restricts these installed-app APIs for **GCC High and DoD only** — plain GCC is not listed |
>
> If your own build fails at this step, verify those five first — they are the common causes.
> The check below is what remains when they all pass.

⚠️ **When the agent is installed, approved, and correctly referenced, the denial is on the
*caller*, not the target.** Graph refused to answer the question at all.

> ⚠️ **The agent working normally in Teams does *not* clear this check.** Ordinary chat runs
> over the Copilot Studio Teams channel and involves no Graph call and no Power Automate
> connection. Proactive delivery runs as the **identity stored in the Microsoft Teams
> connection**, which is a different identity on a different code path. A healthy agent and a
> broken connection coexist comfortably — and that combination is exactly what this `403`
> looks like.

| # | Check | Why it produces this error |
|---|---|---|
| 1 | **Is the Teams connection healthy, and who owns it?** | The Graph call runs as the identity stored in the connection, **not** as you and **not** as the agent. That identity needs [`TeamsAppInstallation.ReadForUser`](https://learn.microsoft.com/graph/api/userteamwork-list-installedapps) |

> ⚠️ **A DLP policy is the weaker candidate here.** A DLP violation **suspends the flow** —
> the trigger stops firing and actions never execute. This flow *ran*, reached the delivery
> action, and received a live `403` from Graph. Check it to rule it out (Step 1c below), but
> do not start there.

---

##### Check 1 — Is the Teams connection healthy?

The connector queries Graph **using the identity stored in the Teams connection**. If that
connection's token is stale, or a policy blocks the connector, the Graph call returns
`Forbidden` even when the agent is installed and approved.

**Step 1a — Look at the connection, and note who owns it**

**Fastest route — from inside the flow itself.** This shows the connection actually bound to
the failing action, so there is no risk of inspecting the wrong one:

1. Open **Power Automate** (`gov.flow.microsoft.us`) → **My flows** → **Anonymous HR Relay**.
2. Select **Edit**.
3. Select the **Post message in a chat or channel** action.
4. At the bottom of the action's settings, look for the connection line — it names the
   connection and the account it runs as, with a **Change connection** link.

⚠️ **The account shown here is the identity making the Graph call.** If it is not you, that is
the account being refused — not your own.

**Alternative route — the Connections list.** *(This corrects an earlier path in this guide:
**More → Connections** does not exist on every tenant.)*

Microsoft's documented location is **Data → Connections**, but the left navigation is
**customisable**, so the entry may be pinned, unpinned, or absent:

| Where to look | Notes |
|---|---|
| **Data** → **Connections** | Microsoft's documented path |
| **More** (bottom of the left nav) → **Connections** | Where it sits when unpinned. Selecting **More** lists the unpinned pages |
| Direct URL | Append `/connections` to your Power Automate host, e.g. `gov.flow.microsoft.us/connections` — bypasses the navigation entirely |
| **Power Apps** (`make.gov.powerapps.us`) → **Data** → **Connections** | Connections are shared between Power Apps and Power Automate — the same list appears in both |

> 💡 **The left navigation is customisable.** Microsoft: use **More** to pin and unpin items.
> If **Connections** is not visible, it is unpinned rather than unavailable — select **More**,
> then optionally pin it.

Once you find it:

1. Confirm the environment picker (top right) shows the **same environment** as your agent.
2. Find **Microsoft Teams** in the list.
3. Check the **Status** column **and the owner/created-by column**.

| Status | Meaning | Action |
|---|---|---|
| **Connected** | Token is valid | Go to Step 1c |
| **Fix connection** link, or a warning icon | ❌ Token is stale or invalid | Step 1b |

> 💡 **See exactly which flows use a connection.** Select the connection → **…** → **Details**,
> then **Flows using this connection**. Useful for confirming you are looking at the one your
> relay actually uses.

**Step 1b — Repair it**

1. Select the **Fix connection** link next to the status.
2. Sign in when prompted, using the account that owns the flow.
3. Wait for the status to return to **Connected**.
4. Re-run your end-to-end test.

> 💡 **Repair before deleting.** *(This corrects earlier advice in this guide.)* Microsoft's
> documented fix is **Fix connection**, not deletion. Deleting a connection detaches it from
> every flow using it, and you must then reopen each flow and re-select the connection.

> ⚠️ **If the connection is owned by someone else**, you cannot repair it. Microsoft: you need
> that person to re-authenticate, or you create your own connection and update the flow to use
> it.

**Step 1c — Check for a DLP policy blocking the connector**

⚠️ **This is a genuine cause of `403` and is easy to miss**, because nothing in your flow
changed — an administrator changed a policy. Microsoft lists a DLP block as a leading cause of
`403 Forbidden` in cloud flows.

Government tenants commonly run stricter Data Loss Prevention policies than commercial ones, so
this is worth checking in GCC even if the flow previously worked.

**The reliable test — run Flow Checker.** *(There is no **Properties** button on the modern
flow page; older guidance that says otherwise is out of date.)*

1. Open **Power Automate** (`gov.flow.microsoft.us`) → **My flows** → **Anonymous HR Relay**.
2. Select **Edit**.
3. Select **Flow checker** on the command bar (a checklist icon; it may show an error count).
4. Read the panel that opens.

| What Flow Checker reports | Meaning |
|---|---|
| No DLP entry | ✅ Policy is not blocking this flow |
| A data-loss-prevention violation | ❌ An admin's policy blocks this connector combination |

Microsoft's documented method: *"To know if your flow is suspended, try to edit the flow and
save it. The flow checker reports it if the flow violates a DLP policy."*

**Also check whether the flow is Suspended:**

1. **My flows** → look at the **Status** column for `Anonymous HR Relay`.

| Status | Meaning |
|---|---|
| **On** | Not DLP-suspended |
| **Suspended** | ❌ Blocked by a DLP policy — `FlowSuspensionReason=CompanyDlpViolation` |

If you have Power Platform admin access, confirm directly:
**Power Platform admin center** (`gcc.admin.powerplatform.microsoft.us`) → **Policies** →
**Data policies**. Check whether a policy covering your environment places **Microsoft Teams**
in a blocked or separate data group.

> ⚠️ **DLP is now unlikely to be your cause.** A DLP violation **suspends the flow** — the
> trigger stops firing and actions do not execute. Your flow *ran*, reached the delivery
> action, and received a `403` **from Graph** with a descriptive message. That is a live call
> being refused, not a policy block. Check it to rule it out, but if the flow shows **On** and
> Flow Checker is clean, look at the connection identity in Step 1b instead.

> 💡 **A strong signal it *is* DLP:** several unrelated flows break at the same time without
> anyone editing them, and they show as **Suspended**.

> ⚠️ **You cannot fix a DLP policy yourself** unless you are a Power Platform administrator.
> Ask your admin which policy applies to your environment and whether the Microsoft Teams
> connector is permitted.

**Step 1d — Other reasons a connection breaks**

Microsoft documents these causes. Scan them if the status looked healthy but delivery still
fails:

| Cause | Tell-tale sign |
|---|---|
| Password changed or expired | Connection broke around the time you changed your password |
| MFA or Conditional Access policy changed | An admin altered sign-in requirements recently |
| Admin revoked consent | Multiple connectors broke simultaneously |
| Token expired through inactivity | The flow had not run for roughly 90 days |
| Terms of Use policy added | Status reads *"Failed to refresh access token for service"* |

✅ **Checkpoint for Check 1:** the Microsoft Teams connection shows **Connected**, the flow
shows **On** (not Suspended) in **My flows**, and **Flow checker** reports no DLP violation.

> 💡 **"This connection isn't being used by any apps" is not a problem.** That panel lists
> **Power Apps**, not flows. To see flows, use **… → Details → Flows using this connection**.

---

##### If the connection is healthy and owned by you

At this point installation, approval, recipient, the **Agent** field, and the connection have
all been verified. Two things in the raw `403` response are worth reading before escalating —
both are easy to scroll past:

| Header | Value seen | What it suggests |
|---|---|---|
| `x-ms-apihub-cached-response` | `true` | ⚠️ **The response was served from cache.** The `403` may predate a fix you have already applied |
| `x-ms-apihub-obo` | `false` | The call is not made *on behalf of* the signed-in user — it uses the connection's own token |

⚠️ **A cached `403` is the trap here.** If the flow was tested **before** the agent was
installed, approved, or fully propagated, that failure can be returned again on later runs even
though the underlying cause is fixed. Everything you check afterwards looks correct, and the
error still appears.

**Check the timeline before assuming the error is current:**

1. Note the `Date` header on the failing run.
2. Compare it with when the agent was **published**, **approved**, and **installed**.
3. If the `403` is from *before* or *within minutes of* those events, it may be stale or a
   propagation race rather than a live permission problem.

**Two fixes, cheapest first:**

1. **Re-run the flow now.** Escalate a fresh question and answer the card. If the earlier
   failure was cached or a propagation race, this alone can resolve it. Costs one test.
2. **Create a new connection.** This is the one case where *recreate* beats *repair*: it issues
   a **new token carrying current permissions** and a **new connection ID**, which bypasses any
   cached response keyed to the old one.

   **From Copilot Studio** (where the flow is usually open):

   1. Open the flow → select the **Post message in a chat or channel** action.
   2. Select the connection line → **Change connection**.
   3. In the panel, select **Add new**.
   4. Sign in when prompted.
   5. Confirm the new connection is selected (radio button), then **Save** and republish.

   **From Power Automate:** delete the connection, then reopen the flow and re-select it on the
   delivery action.

> ⚠️ **A token issued before the agent existed cannot carry permissions for it.** If the Teams
> connection was created *before* the agent was published and approved, its token may predate
> the app's Graph permissions. The status still reads **Connected**, because the token is valid
> — it is simply missing scope. Creating a new connection is the only way to refresh it.

> 💡 **Check the connection's `Created` date against the agent's publish date.** Select the
> connection's **…** → **Connection details**. If the connection is older than the agent, it is
> a candidate regardless of what the status says.

> ⚠️ **A recent `Modified` timestamp does not mean the token was reissued with new scope.**
> Refreshing an existing connection renews the *same* grant. Only **Add new** produces a fresh
> consent and a new connection ID.

---

##### If a brand-new connection still returns `403`

A fresh connection eliminates stale tokens and cached responses. If the `403` persists, read
the action's **raw inputs and outputs** together.

**First, confirm the failure is live, not replayed:**

| Header | Value | Meaning |
|---|---|---|
| `x-ms-apihub-cached-response` | `false` | ✅ **Live refusal** — Graph was called and said no. Not a stale result |
| `x-ms-apihub-cached-response` | `true` | ⚠️ Replayed from cache — may predate a fix. Re-run before concluding anything |
| `x-ms-apihub-obo` | `false` | The call uses the connection's own token, not the signed-in user's |

⚠️ **A live `403` on a brand-new connection is conclusive.** It rules out stale tokens, expired
consent, cached responses, and connection ownership in one result. The call is reaching Graph
and being refused on its merits.

**The raw inputs name the app being asked about:**

```json
"parameters": {
    "poster": "Power Virtual Agents",
    "location": "powerva",
    "body/bot": "cr637_agentH88-Vz",
    "body/recipient": "user@contoso.gov",
    "body/installedError": "Fail"
}
```

| Field | What to check |
|---|---|
| `body/bot` | ⚠️ **The Dataverse logical name of the agent** — this is the app Graph is asked about, *not* the display name you picked from the dropdown |
| `body/recipient` | The target user |
| `body/installedError` | `Fail` makes the action error out instead of returning status `100` |
| `poster` | `Power Virtual Agents` is expected — the internal name for agent-identity posting |

💡 **Set `installedError` to `Succeed with status code` before escalating.** If the action then
returns `100` instead of `403`, the problem is installation-related and you have a cleaner
signal. If it still returns `403`, the Graph call itself is being refused.

> ⚠️ **A `403` that survives this change is diagnostically important.** *(Confirmed in a real
> GCC build.)* The `installedError` setting only governs what happens **after** Graph answers
> *"not installed."* A `403` means Graph never answered at all — the lookup was refused before
> installation state could be determined. This is why the two outcomes mean different things:
>
> | Result after the change | Meaning |
> |---|---|
> | `100` | Graph answered *"not installed"* — an installation or visibility problem |
> | Still `403` | ❌ **Graph refused the question** — a permission problem on the caller, which no flow-level setting can influence |

**What a live, persistent `403` means.** The connector must call
[`TeamsAppInstallation.ReadForUser`](https://learn.microsoft.com/graph/api/userteamwork-list-installedapps)
before it will send. When the agent is installed, admin-approved, correctly referenced, the
connection is brand new, the response is **not cached**, and the `403` **survives setting
`installedError` to succeed**, the remaining explanation is that the **Teams connector's
service principal lacks tenant consent for that Graph permission**.

⚠️ **No amount of reconnecting fixes this.** Consent is granted once at the tenant level, not
per connection.

**Escalate to a Global Administrator:**

1. **Microsoft Entra admin center** → **Identity** → **Applications** → **Enterprise
   applications**.
2. Find the **Microsoft Teams** connector application used by Power Platform.
3. Open **Permissions** and check for tenant-wide admin consent covering
   `TeamsAppInstallation.ReadForUser`.
4. Ask them to
   [grant tenant-wide admin consent](https://learn.microsoft.com/entra/identity/enterprise-apps/grant-admin-consent)
   if it is missing.

> 💡 **Why this fits a government tenant.** Many GCC tenants disable user consent and require
> explicit admin consent for every Graph permission. Ordinary agent chat is unaffected because
> it never calls Graph — only proactive delivery does, which is exactly the split you see when
> the agent answers questions normally but delivery fails.

> ⚠️ **Take the evidence with you.** From the failing run's raw outputs, give your admin the
> `x-ms-service-request-id`, the `RequestId` quoted inside the error body, the `Date` header,
> and `x-ms-tenant-id`. Microsoft Support can trace the denied Graph call directly from those
> values.

> 💡 **If admin consent turns out to be present**, this is a supportable defect rather than a
> configuration error. Open a Microsoft Support case with the same identifiers — the request
> IDs let Support locate the exact refused call.

---

##### If you are the tenant administrator — verify before granting consent

⚠️ **Do not go straight to "Grant admin consent."** Microsoft warns that granting tenant-wide
consent *"may revoke permissions that have already been granted tenant-wide for that
application."* On a shared first-party connector, that can break unrelated flows across the
whole tenant. Confirm the diagnosis first — it costs about five minutes.

**Step A — Confirm the refusal in the sign-in logs.** This converts an inference into fact and
names the exact service principal being denied:

1. Sign in to the **Microsoft Entra admin center** (`entra.microsoft.com`) as at least a
   **Reports Reader**.
2. Go to **Entra ID** → **Monitoring & health** → **Sign-in logs**.
3. Open the **Service principal sign-ins** tab. *(Connector calls are **not** on the default
   interactive tab.)*
4. Set the time filter to the window around the failing run — use the `Date` header from the
   raw output, which is in **UTC**.
5. Add filter **Status = Failure**.
6. Find the entry matching your run and open it.

| What to record | Why |
|---|---|
| **Application** name and ID | ⚠️ The exact service principal to fix — do not assume which app it is |
| **Sign-in error code** (`AADSTS…`) | Look it up at [the error lookup tool](https://login.microsoftonline.com/error) |
| **Failure reason** | Distinguishes missing consent from Conditional Access or a disabled app |
| **Correlation ID** | Ties the entry to your flow run |

| Failure reason indicates | Meaning |
|---|---|
| Consent / permission not granted | ✅ The diagnosis holds — continue to Step B |
| **Conditional Access** blocked the sign-in | ❌ Different fix — a CA policy is catching the service principal |
| Application **disabled** for sign-in | ❌ Different fix — re-enable it in **Properties** |
| **No failure entries at all** | ⚠️ **Expected in this scenario** — see below |

> ⚠️ **An empty sign-in log does not disprove the diagnosis.** *(Confirmed in a real GCC
> build.)* Microsoft draws a hard line between the two:
>
> | Concept | Purpose | Failure code |
> |---|---|---|
> | **Authentication** — "who are you?" | Verify identity | `401 Unauthorized` |
> | **Authorization** — "may you do this?" | Verify permissions | **`403 Forbidden`** |
>
> **Sign-in logs record authentication, not authorization.** Your `403` means a token was
> issued successfully — sign-in *succeeded* — and Graph then rejected the call because the
> token lacked the required scope. A successful sign-in produces no failure entry, and the
> authorization refusal happens at the Graph resource, which Entra sign-in logs do not cover.
>
> The connector also multiplexes calls through **shared first-party service principals**, so
> there may be no entry that visibly corresponds to your agent at all.
>
> **What this changes:** an empty log is *consistent with* a missing-scope problem rather than
> evidence against it. It removes a confirmation route, not the hypothesis. Skip to Step B.

**Step B — Inspect what is already consented, before changing anything:**

1. **Entra ID** → **Enterprise applications** → **All applications**.
2. Clear the filters and search for the application named in Step A.
3. Open it → **Security** → **Permissions**.
4. Record what is currently granted — screenshot it. This is your rollback reference.

**Step C — Grant consent only if it is genuinely missing.**

Required roles (Microsoft's own list):

| Role | Can consent to |
|---|---|
| **Privileged Role Administrator** | Any permission, including **Microsoft Graph application permissions** |
| Cloud Application Administrator / Application Administrator | Any permission **except** Microsoft Graph app roles |

1. On the app's **Permissions** page, review every permission requested.
2. Select **Grant admin consent for \<tenant\>**.
3. Re-run the flow and check the delivery action's status code.

> ⚠️ **Global Administrator alone may not be enough.** For Microsoft Graph *application*
> permissions, Microsoft specifies **Privileged Role Administrator**. If **Grant admin consent**
> is greyed out, this is usually why.

> ⚠️ **Consent takes effect immediately and is not subject to review.** There is no staged
> rollout and no confirmation step after the click.

> 💡 **Cheaper test first.** Before touching tenant consent, set **If the agent is not
> installed** to **Succeed with status code** and re-run. If the action returns `100` instead
> of `403`, the problem is installation-related and no consent change is needed. **If it still
> returns `403`, that test is exhausted** — proceed with Step A below.

---

##### Check 2 — Was the Teams channel disconnected and reconnected?

If anyone toggled the Teams channel off and on — a common fix for stale-version problems —
**every user must reinstall the agent** before proactive delivery works for them again.

1. In **Copilot Studio**, open your agent → **Channels**.
2. Select the **Teams and Microsoft 365 Copilot** tile.
3. If the panel offers **Add channel**, the channel is currently disconnected — reconnect it,
   then **Publish**.
4. Have each user reinstall the agent: Copilot Studio → **Channels** → **Microsoft 365 and
   Microsoft Teams** → **See agent in Teams** → **Add**.

See [requirement 4](#4-reconnecting-the-agent-to-teams-silently-breaks-delivery) for why this
happens.

💡 **Where to focus.** With installation, approval, recipient, and the **Agent** field all
verified, the connection identity is the remaining suspect. Start with **Step 1a** — note the
connection's **owner**, not just its status. An owner who is a service account, a departed
colleague, or an account subject to Conditional Access is the likeliest explanation for a Graph
call being refused while the agent itself works normally.

#### If the status is `200` but you still see nothing

The message was delivered somewhere. Check **`Post as` on the delivery action**:

| `Post as` | Where the message actually went |
|---|---|
| **Microsoft Copilot Studio agent** ✅ | The employee's chat with your agent — correct |
| **Flow bot** ❌ | A separate **Flow bot** chat in Teams, not your agent |

This happens when the delivery action is created by copying the card action, which uses
**Flow bot** for the channel post. Scroll your Teams chat list for a *Flow bot* conversation —
if the answer is sitting there, that is the cause.

#### If everything looks right and it still fails

- **Was the Teams channel recently disconnected and reconnected?** Microsoft: *"If the agent
  disconnects and reconnects to Teams, users don't receive proactive messages until they
  reinstall the agent."* See
  [requirement 4](#4-reconnecting-the-agent-to-teams-silently-breaks-delivery).
- **Is the agent published, and installed in your own Teams?** Proactive delivery requires
  both.
- **Does the recipient's UPN differ from their primary SMTP address?** The connector resolves a
  name or email address. If your tenant's UPN and mail attributes differ, temporarily hardcode
  your own email in **Recipient** to isolate the variable.

### Test the undelivered path

Proactive delivery fails silently if the employee removed the agent. Prove your handling works:

1. From a test account, escalate a question.
2. **Uninstall the agent** from that account's Teams while the card is pending.
3. Answer the card.
4. Open the flow run and confirm the delivery action returned **`100`**, and that your
   telemetry recorded it.

If the run reports Succeeded with no trace of the failure, revisit
[Handle undelivered answers](#handle-undelivered-answers) — that is the silent-failure mode.

### Test a realistic wait

Proactive messages are designed to reach a user outside an active conversation, so a long wait
should behave exactly like a short one. Confirm it once at your real duration anyway:

1. Escalate a question from your own account.
2. **Leave the chat completely idle.** Do not send the agent anything.
3. Wait at your intended answer window (4–8 hours).
4. Answer the card.
5. Check whether the answer arrives in Teams.

| Result | What it means | What to do |
|---|---|---|
| Answer arrives normally | ✅ Working as designed | Proceed |
| Nothing arrives; delivery returned `100` | The agent was uninstalled mid-wait | Expected — your fallback should have logged it |
| Nothing arrives; flow shows Succeeded with `200` | Unexpected | Check the recipient address resolved to the right user |

⚠️ **Check the flow run history either way.** A run marked Succeeded while the employee
received nothing is the failure mode to watch for, and it will not announce itself.

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

### ⚠️ Returning the answer from the flow (asynchronous response) — not recommended

This is the variation you will find in Microsoft's documentation, and it looks tidier: keep a
**Respond to the agent** action, turn on **Asynchronous response**, and the answer comes back
as the flow's own return value. It would appear as an ordinary agent reply and show up in
Copilot Studio analytics.

**It was built and tested, and it has a confirmed defect.** While a card is pending the agent
stops answering other questions, replying *"I was unable to find information…"* until HR
responds. The cause is the **tool call itself** — a flow invoked as a tool holds the topic open
until it returns. Removing the node after the tool call does **not** help *(tested)*.

Full reasoning and the comparison table:
[Why not return the answer from the flow?](#why-not-return-the-answer-from-the-flow)

If you want to investigate it anyway, two things are worth checking first:

| Check | Why |
|---|---|
| `environmentFlowHostingType` = `SelfHostMultiTenant`? | Ctrl+Alt+A in Power Automate. Async requires the new infrastructure; on `LogicApps` it does nothing, and Microsoft warns the agent *"might receive a 'flow completed' response immediately while the flow continues to run in the background."* |
| Classic or generative orchestration? | **Settings → Generative AI.** Classic parks the conversation in the active topic by design. ⚠️ Generative may avoid that, but it also decides for itself which topics and tools to invoke — **it has been observed skipping the topic that calls the Azure Function**, breaking unrelated agent capabilities. Verify the Function is still called before drawing conclusions |

> ⚠️ Async is also **not portable to all channels**. Microsoft: callbacks are *"fully supported
> in Microsoft Teams"* but *"aren't supported for Microsoft 365 Copilot and telephony
> channels."* Proactive delivery has the same Teams-only constraint, so this is not a reason to
> prefer one over the other — but do not reuse either pattern on those channels.

### If you need a shorter, staffed window

Nothing here depends on an 8-hour wait. If HR would rather guarantee a fast reply during
business hours, set the card timeout to `PT30M`–`PT2H` and staff the channel. Everything else
in this guide stays as written.

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

The anonymous delivery step ([Step D.5](#step-d5--deliver-the-answer-proactively)) is identical
either way, so anonymity holds in both.

⚠️ **Constraints Microsoft states explicitly:** Outlook only; cannot be sent outside your
tenant; a known issue where outputs come back wrapped in `{{ }}` unless input names are
configured without spaces.

---

## Pros and cons

**✅ Pros**

| Advantage | Detail |
|---|---|
| **Anonymous by design** | Anonymity comes from the transport, not a setting that can fail open |
| **Closes the loop** | The answer reaches the employee |
| **The agent stays available** | The topic ends at the tool call, so employees can keep asking other questions while HR composes a reply |
| **Delivers outside the original conversation** | Microsoft's documented use case is *"letting a recipient know that their earlier request is complete"* — the same shape as this relay, so a multi-hour wait is not a special case |
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
| **Invisible to Copilot Studio analytics** | Microsoft: proactive messages *"don't appear in conversation transcripts or analytics session data."* The [telemetry event](#telemetry--near-mandatory-for-this-build) is how you get the data back |
| **The employee must still have the agent installed** | Delivery fails with status `100` if they uninstalled or blocked it. True by definition at escalation time, but they can remove it while waiting |
| **Failure is silent unless you handle it** | The flow run reports Succeeded on status `100` — [handle the code explicitly](#handle-undelivered-answers) |
| **Capacity exhaustion disables escalation silently** | Agent flow runs are blocked while the agent keeps answering — a partial outage nobody reports. See [Copilot Credits](#️-copilot-credits--the-cost-axis-that-can-switch-this-feature-off) |
| **Not portable to all channels** | Proactive delivery targets a personal Teams chat; do not reuse this on other channels |
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

### Why this build makes it harder

The answer is delivered **as the agent**, into the same personal chat the agent already uses.
It lands from the same sender, in the same visual style, as everything the model generates.
Nothing distinguishes a human answer from an AI one unless you add the distinction yourself.

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

**For the human answer** — set the delivery message in
[Step D.5](#step-d5--deliver-the-answer-proactively) to:

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

⚠️ **1. Never let the model rewrite a human answer.** The delivery action sends its message
verbatim, which is what you want. Do not route the card's answer through a generative node or
ask the model to summarise or "improve" it — the reply would become model-generated text
*about* a human answer, and your label would become false. This is the single easiest way to
break transparency without noticing.

⚠️ **2. Label inside the flow's message.** The wording lives in the **flow's** delivery action,
not in the Copilot Studio topic. The topic has already ended by the time the answer is sent, so
there is nowhere else it could go — but it is worth stating, because it is the reason the label
survives however long the wait was.

### What to tell employees up front

One line in your agent's greeting or help topic prevents most confusion:

> `Most of my answers are AI-generated from HR benefits documents. If I can't answer, I can send your question to a person on the HR team — their reply will be clearly marked as coming from a person.`

✅ **Checkpoint:** ask a question you know the agent cannot answer, escalate it, and confirm the
employee can tell at a glance which of the four message types each reply is.

---

## Telemetry — near-mandatory for this build

Record that a representative was requested. In most designs this is a nice-to-have; here it is
close to essential.

⚠️ **Proactive messages are invisible to Copilot Studio analytics.** Microsoft: proactive
messages *"don't appear in conversation transcripts or analytics session data."* The escalation
question and the human answer will not show up in your transcripts at all. Without your own
event, escalations become invisible and the deflection analysis silently understates demand.

⚠️ **It is also your only detector for undelivered answers.** A delivery that fails with status
`100` still leaves the flow reporting Succeeded. Emit an event when an escalation is **raised**
and a second when an answer is **delivered**, including the status code. A persistent gap
between the two counts is the signal that answers are being lost.

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
| Delivery fails with **`403`** and *"Did not receive InstalledApplication… Forbidden from graph"* | The connector's Graph lookup for the recipient's installed apps was denied — **not** the same as status `100` | Agent not installed in the recipient's personal Teams scope, or (in GCC) **not yet approved by a Teams admin**. Full checklist: [403 Forbidden](#-403-forbidden--did-not-receive-installedapplication) |
| Several unrelated flows break at once, with no edits by anyone | **A Data Loss Prevention policy changed.** Microsoft: DLP changes take effect immediately and block flows without warning | Check **My flows** for a **Suspended** status, and run **Flow checker** inside the flow. Confirm with your Power Platform admin — see [Check 1](#check-1--is-the-teams-connection-healthy) |
| Rep submits the card, flow shows **Succeeded**, employee gets nothing | Could be any of four causes — a green run does not mean delivered | **Read the status code from the run** — the full decision table is in [The answer never arrived](#-the-answer-never-arrived--diagnose-it-here) |
| Employee never receives the answer; delivery returned `100` | **The employee does not have the agent installed** — uninstalled or blocked it while waiting | Expected failure mode. Confirm you set **If the agent is not installed** to *Succeed with status code* and that you log it ([Step D.5](#step-d5--deliver-the-answer-proactively)) |
| Employee never receives the answer; delivery returned `300` | **If the chat with the agent is active** is set to *Don't send…* — the answer is withheld because the employee is actively chatting with the agent | Set it to **Send** ([Step D.5](#step-d5--deliver-the-answer-proactively)). This hits the most engaged users, who keep the chat open while waiting |
| Delivery action fails outright instead of returning a code | **If the agent is not installed** left as *Fail* | Set it to **Succeed with status code** under **Show advanced options** |
| Answer is delivered to the wrong person, or nobody | `Recipient` not bound to the `UserEmail` input | Check the topic passes `System.User.PrincipalName` ([Step D.6](#step-d6--wire-the-flow-into-the-topic)) |
| Employee never gets a reply, flow still running | The card is still waiting, or the branch that ran has no delivery action | Both branches off the card action must end in **Post message in a chat or channel** |
| Answer arrives blank | Referenced `submitActionId` instead of `answer` | Point the expression at the **`answer`** value |
| No `answer` token in the lightning-bolt picker | Card JSON is pasted content, so the designer cannot infer its schema — only **Body** is offered | Use the **`fx`** expression button instead ([Step D.5](#step-d5--deliver-the-answer-proactively)). Do not select **Body** |
| Agent replies *"I was unable to find information…"* to unrelated questions while a card is pending | **A `Respond to the agent` action is still in the flow**, holding the topic open | Remove it — this build does not use one ([why](#why-not-return-the-answer-from-the-flow)) |
| Agent replies *"I was unable to find information…"* to questions it used to answer, **with no card pending** | ⚠️ **Not this feature.** The topic that calls your Azure Function is being bypassed entirely — the trace shows only *Search sources*, never the Function | Check **Settings → Generative AI**: under generative orchestration your topic *"may be skipped"*. Confirm in the trace that `agent_httptrigger` is actually called |
| Employee sees the "Answered by a person" label twice | Disclosure wording added in **both** the flow's delivery message and a topic message | Keep it only in the flow's delivery message; the topic should not display the answer at all |
| Answer arrives as raw JSON | Selected **Body** from the picker | Replace with the `fx` expression targeting the `answer` value |
| Escalation stops working but the agent still answers normally | **Copilot Studio capacity exhausted** — new agent flow runs are blocked while the parent agent keeps working | Check **Agent flow actions** in the Power Platform admin center; reallocate credits or enable pay-as-you-go |
| Nobody answered and the employee got no message at all | Timeout branch missing, added **sequentially** instead of as a parallel branch, or **Configure run after** not set | The second delivery action must branch off the **card action**, not follow the first one ([Step D.5](#step-d5--deliver-the-answer-proactively)) |
| Employee gets the real answer **and then** "nobody answered" | Second delivery action was added sequentially, so both fire | Re-add it as a **parallel branch** off the card action |
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
| `SystemError` in Teams | Teams using a stale published version | Republish first. ⚠️ **Only if that fails**, disable/re-enable the app in Teams admin center or toggle the Teams channel off and on — but see the warning below. [Known limitations](https://learn.microsoft.com/microsoft-copilot-studio/publication-add-bot-to-microsoft-teams#known-limitations) |
| New option not visible in Teams | Teams cached the old agent | Same as above |

⚠️ **Reconnecting the Teams channel breaks proactive delivery until every user reinstalls the
agent.** Microsoft: *"If the agent disconnects and reconnects to Teams, users don't receive
proactive messages until they reinstall the agent."* The two fixes above are the standard
advice for stale-version problems, but on this build they will silently stop HR answers from
reaching employees. Try **Republish** first, and if you must reconnect the channel, tell users
to reinstall — see
[Reconnecting the agent to Teams silently breaks delivery](#4-reconnecting-the-agent-to-teams-silently-breaks-delivery).

---

## Technical questions you are likely to be asked

**Q: Does this require changing the Azure Function?**
No. This option is configuration-only. The optional telemetry event is the only code change,
and it is not required for the feature to work.

**Q: Will this break the existing "Email HR" feature?**
No. It adds a branch beside it on the same Question node.

**Q: How can a flow wait hours when agent flows must respond in 100 seconds?**
The 100-second rule applies to flows that **return a result to the agent**. This flow does not
— it has no **Respond to the agent** action, so the agent stops waiting the moment the flow is
triggered. The flow then continues in the background for as long as the card timeout allows,
and delivers the answer as a separate proactive message.

**Q: Why not have the flow return the answer directly? That seems simpler.**
It is simpler, and it was tested. While a card is pending the agent stops answering other
questions, because a flow invoked as a tool holds the topic open until it returns. Removing the
node after the tool call does not fix it. See
[Why not return the answer from the flow?](#why-not-return-the-answer-from-the-flow).

**Q: The flow can run for 30 days — so can a rep answer 3 days later?**
Yes, within whatever timeout you set on the card. Proactive messages are designed to reach a
user outside an active conversation, so a long wait is not a special case — the employee does
not need to still be in the chat. The practical ceiling is the 30-day flow limit, and your own
timeout should be far shorter than that.

**Q: Does the employee have to keep the agent installed for the answer to arrive?**
Yes. Proactive delivery fails with status `100` if they uninstalled or blocked the agent. This
is satisfied by definition at escalation time — they just used the agent — but they could
remove it while waiting. That is why the status code is handled explicitly in
[Step D.5](#step-d5--deliver-the-answer-proactively).

**Q: How would we even know if answers were being lost?**
From the delivery status code, provided you log it. A `100` result still reports the run as
Succeeded, so nothing surfaces the loss on its own. That is the argument for the telemetry
event and reconciling "escalations raised" against "answers delivered."

**Q: Will this show up in Copilot Studio analytics?**
No. Microsoft states proactive messages *"don't appear in conversation transcripts or analytics
session data."* This is the main cost of the design, and the reason
[telemetry](#telemetry--near-mandatory-for-this-build) is treated as near-mandatory here rather
than optional.

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
| [**Send proactive Microsoft Teams messages**](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message) | ⭐ **The basis of this build.** Agent-identity delivery to a personal chat; the agent-installed prerequisite; status codes `200`/`100`/`300`; the analytics exclusion |
| [**Create your first adaptive card**](https://learn.microsoft.com/power-automate/create-adaptive-cards) | The post-card-and-wait walkthrough — the exact action [Step D.3](#step-d3--post-the-card-and-wait-for-an-answer) uses. Also states the **Workflows app** prerequisite |
| [**Create an agent flow as a tool**](https://learn.microsoft.com/microsoft-copilot-studio/advanced-flow-create) | The **100-second limit** this design avoids by not returning a result; the 30-day ceiling behind [Step D.4](#step-d4--add-a-timeout-path); the solution requirement |
| [**Asynchronous response support for agent flows**](https://learn.microsoft.com/microsoft-copilot-studio/flow-asynchronous-response) | ⚠️ **The approach this guide rejects.** Read it to understand *"remove the response action from the flow"* — the mode this build uses — and why the alternative blocks the agent |
| [**Responsible AI guidance**](https://learn.microsoft.com/microsoft-copilot-studio/responsible-ai-overview) | The requirement to disclose when a response comes from a human rather than the agent |

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
| [Cloud flow error code reference](https://learn.microsoft.com/power-automate/error-reference) | `OperationTimedOut` and **Configure run after** — how Step D.5's timeout branch works |
| [Billing rates and management](https://learn.microsoft.com/microsoft-copilot-studio/requirements-messages-management) | ⚠️ **Capacity exhaustion blocks agent flow runs** while the agent keeps answering — escalation dies silently. Also the M365 Copilot exemption and pay-as-you-go |
| [Agent flows overview](https://learn.microsoft.com/microsoft-copilot-studio/flows-overview) | Capacity per run; **test runs are free**, so the long-wait tests cost nothing |
| [Best Practices for Deploying Agents in Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment-ux/) | Why Teams serves a stale agent version — behind two troubleshooting rows |

### Tier 4 — long waits and Teams conversation behaviour

Background for the multi-hour wait, and for the session figures that are easy to misread.

| Resource | Why it matters here |
|---|---|
| [Deploy agents in Microsoft Teams](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deploy-agent-teams) | Teams threads persist *"indefinitely"*; also documents token expiry over long threads |
| [Inactivity trigger](https://learn.microsoft.com/microsoft-copilot-studio/guidance/inactivity-trigger-guidance) | Teams persistent-conversation model; 30-minute transcript boundary (**not** a delivery limit) |
| [Manage sessions and capacity](https://learn.microsoft.com/microsoft-copilot-studio/requirements-sessions-management) | ⚠️ **Legacy billing article.** Listed *only* so you do not misread its 30/60-minute figures as delivery deadlines |
| [Power Automate environments move to new architecture](https://learn.microsoft.com/power-automate/environment-architecture) | How to check `environmentFlowHostingType` — relevant only if you investigate the async alternative |

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
| [contact-center/skill-handoff](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/skill-handoff) | **The closest official analogue to this design** — a live handoff that keeps Teams as the channel and delivers by proactive messaging, the same shape used here |
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
| [Send proactive Microsoft Teams messages](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message) | Listed in Tier 1 — repeated here because the **RFI/Outlook variant** uses the same delivery step |
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
| **Asynchronous response** | A per-action setting that lets a flow run past the 100-second limit and still return its result to the agent. **Not used by this build** — see [why](#why-not-return-the-answer-from-the-flow) |
| **Callback** | The delayed result an asynchronous flow sends back to the agent once it completes. Not used here |
| **Channel** (Teams) | A named section inside a team |
| **Configure run after** | The per-action setting controlling which predecessor outcomes (succeeded / failed / timed out) allow an action to run. Used to build the timeout branch |
| **Copilot Credits** | The usage meter agent flows consume. Exhausting the environment's capacity **blocks new agent flow runs** |
| **`FlowActionTimedOut`** | The error when a flow fails to answer the agent within 100 seconds. **You should not see it in this build**, because the flow returns no result — if you do, a `Respond to the agent` action is still present |
| **Flow bot** | The generic bot identity Power Automate posts as when a message is not tied to a person. **Used by this build** to post the card into the HR channel ([Step D.3](#step-d3--post-the-card-and-wait-for-an-answer)) — the employee never sees it |
| **GCC** | Government Community Cloud. **Not** the same as GCC High |
| **ISO 8601 duration** | A timeout format. `PT8H` = 8 hours, `PT5M` = 5 minutes |
| **Maker** | Someone permitted to build agents and flows |
| **Post as** / **Post in** | The two Teams-connector settings controlling sender identity and destination. This build uses **`Flow bot` + `Channel`** for the card ([Step D.3](#step-d3--post-the-card-and-wait-for-an-answer)) and **`Microsoft Copilot Studio agent` + `Chat with agent`** for delivery ([Step D.5](#step-d5--deliver-the-answer-proactively)). `User` would expose the flow owner and must never be used |
| **Proactive message** | A message an agent sends without the user prompting it. **How this build delivers the answer** ([Step D.5](#step-d5--deliver-the-answer-proactively)). Requires the recipient to have the agent installed, and is excluded from Copilot Studio transcripts and analytics |
| **RFI** | Request for information — a built-in pause-and-ask-a-human action that emails reviewers instead of posting a card. See [Alternatives](#alternatives-worth-knowing-about) |
| **Solution** | A Power Platform container; flows must be in one to be callable by an agent |
| **Token** (dynamic content) | A value produced by an earlier action, inserted via the lightning-bolt picker. ⚠️ Values from a **pasted** Adaptive Card do not appear as tokens — retrieve them with an **`fx`** expression |
| **Topic** | A conversation script |
| **Update message** | The text replacing the card after submission, so a second rep does not answer the same question |
| **UPN** | User Principal Name — usually the sign-in email address |
