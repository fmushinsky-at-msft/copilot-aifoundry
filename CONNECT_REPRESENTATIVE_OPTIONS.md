# Connect to a Representative — Options A, B, C and D

**What this document is:** a beginner's guide to four different ways of adding a
**"Connect to a representative"** choice to the HR Benefits agent, so that when the agent
cannot answer a question the user can choose between *emailing HR* (which already exists)
and *talking to a person*.

**Who this is for:** someone who has never configured Copilot Studio, Power Automate or
Microsoft Graph. Every step says where to click and what you should see afterwards.

**Read this first:** you do **not** implement all four. Read
[Part 0](#part-0--choosing-between-the-options), pick one, then jump to that Part.

> ## 🔒 If representatives must stay anonymous, read this first
>
> If the employee must **not** see the real name of the person answering, that single
> requirement decides most of the design:
>
> | Option | Can hide the representative's identity? |
> |---|---|
> | **A — Teams deep link** | ❌ **No. Impossible.** A Teams group chat always shows real names, photos and presence |
> | **B — Dynamics 365** | ✅ Yes — built-in **nickname** setting ([Step B.6](#step-b6--hide-representative-names-anonymity)) |
> | **C — Channel post** | ✅ Yes — but it is one-way; no reply reaches the user |
> | **D — Anonymous relay** | ✅ Yes — **recommended**; works today, in GCC, no new licences |
>
> **Option A is disqualified** by an anonymity requirement. There is no setting, no
> workaround, no configuration that masks identity in a Teams group chat.
>
> ➡️ If you need anonymity, go to [Part D](#part-d--anonymous-relay-recommended-for-anonymity).

---

## How to use this document

It is long because it covers four options plus reference material. **You will read a small
fraction of it.**

### If you have 5 minutes

1. Read [Part 0 — the options at a glance](#the-options-at-a-glance) (one table).
2. Answer one question: **must the representative stay anonymous?**
   - **Yes** → build **[Option D](#part-d--anonymous-relay-recommended-for-anonymity)** (~2 hours)
   - **No** → build **[Option A](#part-a--teams-deep-link-to-a-group-chat)** (~30 minutes)
3. Ignore everything else until you have built one.

### The shortest useful path

| Step | Where | Time |
|---|---|---|
| 1. Decide | [Decision guide](#decision-guide) | 5 min |
| 2. Check your facts | [Your scenario](#your-scenario--verified-facts-this-document-assumes) | 5 min |
| 3. Build | Part A, C or D | 30 min – 2 hrs |
| 4. Test with yourself first | The checkpoints in each Part | 15 min |
| 5. Brief HR | [Step D.9](#step-d9--brief-the-representatives) or [Step A.8](#step-a8--brief-the-hr-representatives) | 10 min |

### What to skip on a first read

- **Part B** unless you already own Dynamics 365 — it is a multi-week project
- **[Official Microsoft tutorials](#official-microsoft-tutorials-and-quickstarts)** — a
  reference library, not reading material. Come back when something breaks
- **[Questions you are likely to be asked](#questions-you-are-likely-to-be-asked)** — for
  when you present this to stakeholders, not for building
- **[Sources](#sources)** — provenance for every claim, for auditing rather than learning

> ⚠️ **The most common failure with this document is reading all of it.** Pick one option,
> build it against a test channel and your own account, and let what breaks tell you which
> section to read next.

---

## Your scenario — verified facts this document assumes

Everything below was checked against this repository and against Microsoft Learn. If any of
it changes, revisit the recommendations.

| Fact | Value | Why it matters |
|---|---|---|
| Cloud | **GCC** (not GCC High, not DoD) | Decides which options exist at all |
| Agent channel | **Microsoft Teams** | Rules out the standard D365 handoff pattern |
| Copilot Studio auth | **Authenticate with Microsoft** | Required today by `send_hr_email` |
| User identity variable | **`System.User.PrincipalName`** | What your existing flows already pass as `user_email` |
| Function App | `func-hrbenefit-dev003` (Flex Consumption, Python) | Three routes; no change needed for any option |
| Existing escalation | "Email HR" via `send_hr_email` | You are adding a *second* choice beside it |
| Licensing | `send_hr_email` requires **Power Automate Premium** (it uses the HTTP action) | Options C and D use the **standard** Teams connector — may need no new licence. **Verify** |

### ⚠️ A conflict you must know about before choosing Option B

Your agent currently uses **Authenticate with Microsoft**. Microsoft's documentation states
plainly:

> *"the **Authenticate with Microsoft** option isn't available for agents that integrate
> with Dynamics 365 Customer Service."*

And `EMAIL_HR_DEPLOYMENT_CHECKLIST.md` (Section 5) records that your email feature
**requires** that setting, because with **No authentication**
`System.User.PrincipalName` is empty and `send_hr_email` fails with
`400 Missing required parameter 'user_email'`.

**So adopting Option B may force you to switch to *Authenticate manually* (Microsoft Entra
ID) and re-verify that the email feature still works.** This is not a blocker — manual
Entra ID authentication also populates `User.PrincipalName` — but it is real work and real
risk that must be in the plan. Options A, C and D do not touch authentication at all.

---

## Table of contents

- [How to use this document](#how-to-use-this-document)
- [Your scenario — verified facts this document assumes](#your-scenario--verified-facts-this-document-assumes)
- [Part 0 — Choosing between the options](#part-0--choosing-between-the-options)
  - [What "connect a representative" can actually mean](#what-connect-a-representative-can-actually-mean)
  - [The options at a glance](#the-options-at-a-glance)
  - [What your GCC tenant allows](#what-your-gcc-tenant-allows)
  - [A note on Power Automate licensing](#a-note-on-power-automate-licensing)
  - [Decision guide](#decision-guide)
- [Background — how the current feature works](#background--how-the-current-feature-works)
- [Part A — Teams deep link to a group chat](#part-a--teams-deep-link-to-a-group-chat)
- [Part B — Copilot Studio handoff to Dynamics 365](#part-b--copilot-studio-handoff-to-dynamics-365)
- [Part C — Post to an HR Teams channel via Power Automate](#part-c--post-to-an-hr-teams-channel-via-power-automate)
- [Part D — Anonymous relay (recommended for anonymity)](#part-d--anonymous-relay-recommended-for-anonymity)
  - [Variant D2 — use the native "Request for information" action instead](#-variant-d2--use-the-native-request-for-information-action-instead)
- [Anonymity — what it does and does not protect](#anonymity--what-it-does-and-does-not-protect)
- [Official Microsoft tutorials and quickstarts](#official-microsoft-tutorials-and-quickstarts)
  - [Reference implementations (working code you can read)](#reference-implementations-working-code-you-can-read)
  - [Power CAT Copilot Agent Kit — for measuring whether this feature works](#power-cat-copilot-agent-kit--for-measuring-whether-this-feature-works)
  - [Microsoft CAT team blog — "The Custom Engine"](#microsoft-cat-team-blog--the-custom-engine)
  - [Alternate escalation paths — Microsoft's own guidance](#alternate-escalation-paths--microsofts-own-guidance)
  - [Community blog posts (not Microsoft-authored)](#community-blog-posts-not-microsoft-authored)
  - [Case studies and adoption material](#case-studies-and-adoption-material)
  - [Free hands-on training (Microsoft Learn)](#free-hands-on-training-microsoft-learn)
  - [Architecture guidance and reference solutions](#architecture-guidance-and-reference-solutions)
- [Questions you are likely to be asked](#questions-you-are-likely-to-be-asked)
- [Optional — Add telemetry so Power BI stays complete](#optional--add-telemetry-so-power-bi-stays-complete)
- [Troubleshooting](#troubleshooting)
- [Glossary](#glossary)
- [Sources](#sources)

---

## Part 0 — Choosing between the options

### What "connect a representative" can actually mean

Before comparing options, be clear about which of these you want, because they are very
different products:

| Meaning | Description | Which option |
|---|---|---|
| **Live chat** | The user types, a person answers within seconds, in the same window | B (properly), A (approximately) |
| **Direct contact** | The user is dropped into a Teams chat with named HR people | A |
| **Async request** | A work item appears somewhere; a human follows up later | C |
| **Anonymous Q&A** | The user gets a real human answer without learning who wrote it | **D**, or B with nicknames |

⚠️ **The most common mistake** is asking for "live chat" and building C. C is a ticket
queue with a chat-shaped front end. It is perfectly good, but nobody is waiting on the
other end.

### The options at a glance

| | **A — Deep link** | **B — D365 handoff** | **C — Channel post** | **D — Anonymous relay** |
|---|---|---|---|---|
| User experience | Teams chat opens with HR reps, question pre-filled | True live handoff, same window | "We've notified HR" | The agent delivers a human's answer |
| Live or async? | Near-live (a real Teams chat) | **Live** | **Async** | Async (minutes) |
| **Hides rep identity** | ❌ **Impossible** | ✅ (nickname; 2 leaks) | ✅ | ✅ |
| Reply reaches the user | ✅ | ✅ | ❌ | ✅ |
| New licences | **None** | D365 Customer Service / Contact Center | Likely none — Teams connector is standard ([verify](#a-note-on-power-automate-licensing)) | Likely none — Teams connector is standard ([verify](#a-note-on-power-automate-licensing)) |
| New Azure resources | **None** | None (D365 side only) | None | None |
| Code changes | **None required** | None required | None required | None required |
| Build time | ~30 min | Days to weeks | ~45 min | ~2 hours |
| Routing / queueing | ❌ | ✅ | ❌ | ❌ |
| Presence-aware (skips people who are away) | ❌ | ✅ | ❌ | ❌ |
| SLA + reporting | ❌ | ✅ | Partial | Partial |
| Works in GCC | ✅ | ✅ (see caveat) | ✅ | ✅ |
| Risk | Low | **Medium — needs a POC** | Low | Low |

### What your GCC tenant allows

Your tenant is **GCC** (Government Community Cloud). This is *not* the same as GCC High or
DoD, and the difference matters a lot here — several things that are blocked in GCC High
work fine for you.

| Capability | GCC | GCC High | Why it matters |
|---|---|---|---|
| Copilot Studio **Transfer to agents** | ✅ | ❌ | Option B is possible for you |
| Copilot Studio **Teams channel** | ✅ | ❌ | Your agent is published here |
| Teams **Workflows** / Power Automate | ✅ | ❌ | Option C is possible for you |
| Third-party Teams apps | ✅ (off by default) | ❌ | — |

**Teams URL for GCC is `teams.microsoft.com`** — the *standard commercial* address.
Only GCC High (`gov.teams.microsoft.us`) and DoD (`dod.teams.microsoft.us`) use special
addresses. This is why the deep link in Option A works for you unchanged.

⚠️ **But note these GCC blockers**, which rule out approaches you might otherwise consider:

- **Azure Communication Services ↔ Teams interop is NOT supported in GCC** — in *either*
  direction. So you cannot build a custom web chat that bridges into Teams calls or chats.
- **Microsoft Graph cannot post a chat message as an application.** Sending a message with
  app-only permissions requires `Teamwork.Migrate.All`, which is for *migrating historical
  data*, not live messaging. There is no app-only equivalent of "send this message now."

> **GCC portal addresses** used throughout this document. These come from Microsoft's
> [Copilot Studio US Government service URLs](https://learn.microsoft.com/microsoft-copilot-studio/requirements-licensing-gcc#microsoft-copilot-studio-us-government-service-urls)
> table — they are **not** simple `.com` → `.us` swaps, so do not guess them.
>
> | Purpose | Commercial | **Your GCC address** |
> |---|---|---|
> | Copilot Studio | `copilotstudio.microsoft.com` | **`gcc.powerva.microsoft.us`** |
> | Power Automate | `flow.microsoft.com` | **`gov.flow.microsoft.us`** |
> | Power Platform admin | `admin.powerplatform.microsoft.com` | **`gcc.admin.powerplatform.microsoft.us`** |
> | Azure Portal | `portal.azure.com` | `portal.azure.us` |
> | Teams (deep links) | `teams.microsoft.com` | `teams.microsoft.com` (unchanged — GCC is not sovereign) |
>
> ⚠️ **Correction:** earlier drafts of this document — and
> `CUSTOM_FEEDBACK_SETUP_GUIDE.md` in this repo — cite
> `gcc.copilotstudio.microsoft.us` and `make.gov.powerautomate.us`. Neither appears in
> Microsoft's official table. Use the values above.

### A note on Power Automate licensing

Earlier drafts of this document asserted that you *"already have Power Automate Premium."*
**That was an assumption, not a verified fact**, and it is corrected here.

What is actually known:

- `COPILOT_STUDIO_SETUP_GUIDE.md` states the **HTTP** action is a **premium connector** and
  lists Power Automate Premium as a licence you **need to obtain** — written as a
  prerequisite, not a confirmation that it was granted.
- If `send_hr_email` works in production today, *somebody* has that licence. Who, and
  whether it covers the account that will run a new flow, is unverified.

**Why this matters in your favour:**

| Feature | Action | Connector tier |
|---|---|---|
| `send_hr_email` (existing) | **HTTP** | **Premium** |
| Options C and D | Teams: post message / post card and wait | **Standard** |

The new options use the **standard Teams connector**, so they may need **no new licence at
all** — a better position than "you already pay for Premium."

⚠️ **Verify before budgeting either way.** Open the flow designer and look for a **Premium**
badge on the actions you intend to use; no badge means no premium requirement for that
action. Note separately that Microsoft's
[Agent flows FAQ](https://learn.microsoft.com/microsoft-copilot-studio/flows-faqs) says agent
flows are *"billed in Copilot Studio based on usage"* and are *"not included entitlements in
Power Automate"* — a different axis from connector tiers.

### Decision guide

Answer these in order and stop at your first **Yes**:

1. **Must the employee be prevented from seeing who answered?**
   → **Option D** (or **B** if you already run Dynamics 365).
   **Option A is eliminated** — it cannot hide identity under any configuration.

2. **Do you already own and run Dynamics 365 Customer Service / Contact Center?**
   → **Option B.** You have paid for the right tool; use it.

3. **Is a genuine live conversation a hard requirement, with budget to match?**
   → **Option B**, but run the POC in [Step B.1](#step-b1--prove-it-works-before-you-commit)
   *before* committing.

4. **Is "a human follows up within a few hours" acceptable, and identity is not a concern?**
   → **Option C** if you want a tracked queue HR already monitors.

5. **Otherwise** → **Option A.** Zero cost, zero new infrastructure, ~30 minutes.

> **Recommended starting point**
>
> - **No anonymity requirement:** **Option A.** It sits naturally beside the existing
>   "Email HR" button, costs nothing, and does not block moving to B later.
> - **Anonymity required:** **Option D.** Same zero-licence, zero-infrastructure profile,
>   about two hours to build, and it is the only option that both hides identity *and*
>   returns a real answer to the user without buying Dynamics 365.
>
> Either way, building the cheap option first produces the usage data that justifies (or
> does not justify) the spend on B.

> ⏰ **Whichever you choose, consider an operating-hours check.** Microsoft's
> [Alternate escalation paths](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-alternate-escalation-paths)
> guidance recommends checking availability *before* offering escalation, and redirecting to
> email or a callback when nobody is available.
>
> All four options here silently assume someone is on the other end. A business-hours
> condition ahead of the choice — offering only "Email HR" outside working hours — prevents
> the worst failure mode: an employee asking at 22:00 and hearing nothing until morning.
> Your existing "Email HR" option is itself a Microsoft-recommended escalation path, so
> keeping both is the documented pattern.

---

## Background — how the current feature works

You need to understand the existing flow before changing it.

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

**The key variable is `canAnswer`.** The Function returns it from `agent_httptrigger`. When
it is `false`, the agent could not answer, and your topic shows the choices. You are adding
a **second option** to a decision point that already exists — you are not building a new
conversation path from scratch.

The Function App currently exposes exactly three routes:

| Route | Purpose |
|---|---|
| `agent_httptrigger` | Ask the Foundry agent a question |
| `send_hr_email` | Email the question to HR via Microsoft Graph |
| `submit_feedback` | Record 👍 / 👎 |

✅ **Good news for all four options:** none of them *require* a change to
`function_app.py`. The only optional code change is telemetry, covered at the end.

---

## Part A — Teams deep link to a group chat

> 🔒 **Skip this Part if representatives must stay anonymous.**
> A Teams group chat shows every participant's real name, profile photo and presence
> status to everyone else in it. This is core Teams behaviour — there is no setting,
> policy or workaround that masks it. If anonymity is required, go to
> [Part D](#part-d--anonymous-relay-recommended-for-anonymity) instead.

**What you will build:** when the agent cannot answer, it shows a link. Clicking it opens
Microsoft Teams with a group chat containing the user **and** your HR representatives, with
the user's original question already typed into the message box. The user presses **Send**.

**Time required:** about 30 minutes.
**Cost:** none.
**Prerequisites:** maker access to the Copilot Studio agent. Nothing else.

### How deep links work

A *deep link* is a specially-formatted web address that Teams understands. When clicked,
instead of opening a web page, it tells the Teams app to do something — in this case,
"open a chat with these people."

```
https://teams.microsoft.com/l/chat/0/0?users=<who>&topicName=<title>&message=<text>
```

| Part | Meaning |
|---|---|
| `users` | Comma-separated list of the people to include. **Email addresses (UPNs) only** |
| `topicName` | The chat's display name. **Only applies when the chat has 3 or more people** |
| `message` | Text pre-filled into the user's message box |

Three behaviours to understand before you build this:

1. **The person who clicks is always added automatically.** Do not put them in `users`.
2. **The message is NOT sent automatically.** It is only *typed into the box*. The user must
   press Send. This is a Teams security behaviour and cannot be turned off — treat it as a
   feature (the user gets to edit before sending).
3. **If a chat with exactly those people already exists, Teams opens that existing chat**
   rather than creating a new one. Ongoing conversations therefore stay in one thread.

### Step A.1 — Decide who the representatives are

Write down the **email addresses** of the HR people who should receive these requests.

| Consideration | Guidance |
|---|---|
| How many? | 2–5 works well. More than ~8 makes a noisy chat |
| Use a distribution list? | ❌ **No.** Deep links need individual user addresses, not group addresses |
| Shared mailbox? | ❌ **No.** Must be real user accounts that can sign in to Teams |
| Who? | People who actually monitor Teams during business hours |

Example: `jane.doe@panynj.gov,john.smith@panynj.gov`

⚠️ **Everyone listed sees every request, and they all see each other.** If HR needs
requests split by topic or kept private between rep and employee, Option A is the wrong
choice — go to Option B.

✅ **Checkpoint:** you have a comma-separated list of 2–5 real user email addresses, with
**no spaces** around the commas.

### Step A.2 — Build and test the link by hand

Before touching Copilot Studio, prove the link works.

1. Take this template and replace the addresses with your own:

   ```
   https://teams.microsoft.com/l/chat/0/0?users=jane.doe@panynj.gov,john.smith@panynj.gov&topicName=HR%20Benefits%20Support&message=Test%20message
   ```

2. Paste it into your browser's address bar and press Enter.
3. Teams should open (or switch to the app) and show a **draft** chat with those people and
   `Test message` in the box.

✅ **Checkpoint:** the chat opens with the right people and the pre-filled text.
❌ If nothing happens, see [Troubleshooting](#troubleshooting).

> **Why `%20` instead of spaces?** Web addresses cannot contain spaces, so a space is
> written as `%20`. This is called *URL encoding*. In the next step Copilot Studio does
> this for you automatically.

### Step A.3 — Open the topic in Copilot Studio

1. Go to `https://gcc.powerva.microsoft.us` and sign in with your work account.
2. In the left navigation, click **Agents**.
3. Click your HR Benefits agent to open it.
4. Click **Topics** in the agent's left navigation.
5. Open the topic that currently offers the "Email HR" choice — the one that checks
   `canAnswer`.

✅ **Checkpoint:** you can see the existing Question node offering the email option.

### Step A.4 — Add the second choice

1. Find the **Question** node where the user is asked whether to email HR.
2. Click into the node's list of options.
3. Click **+ New option**.
4. Type: `Connect to a representative`

You now have two options where before there was one. Copilot Studio automatically adds a
new empty branch under the Question node for the new choice.

> ⚠️ **Teams caps multiple-choice options at six.** Copilot Studio's channel reference table
> notes that in Teams, multiple-choice options are *"supported up to six (as hero card)."*
> You are going from one option to two, so this is not a problem now — but it is a hard
> ceiling if you later add more escalation paths.

✅ **Checkpoint:** the Question node shows both `Email HR` (or your existing wording) and
`Connect to a representative`, and there is an empty branch for the new option.

> **This step is shared by all four options.** Options B, C and D each add a differently
> configured branch under this same Question node, so the instructions here are referenced
> from those Parts rather than repeated.

### Step A.5 — Build the link with a formula

The link must contain the user's actual question, so it has to be assembled at run time.

1. In the new branch, click **+ (Add node)** → **Variable management** → **Set a variable
   value**.
2. For **Set variable**, click the dropdown and choose **Create a new variable**. Name it
   `RepChatLink`.
3. For **To value**, click the **fx** button to switch to a formula.
4. Paste this, replacing the email addresses with yours, and replacing
   `Topic.UserQuestion` with whatever your topic actually calls the user's question:

   ```powerfx
   Concatenate(
	 "https://teams.microsoft.com/l/chat/0/0?users=",
	 "jane.doe@panynj.gov,john.smith@panynj.gov",
	 "&topicName=HR%20Benefits%20Support",
	 "&message=",
	 EncodeUrl(Topic.UserQuestion)
   )
   ```

**What each piece does:**

| Piece | Purpose |
|---|---|
| `Concatenate(...)` | Glues text fragments into one string |
| `EncodeUrl(...)` | Converts spaces and punctuation into URL-safe characters. **Do not omit this** |
| `Topic.UserQuestion` | The variable holding what the user asked |

⚠️ **`EncodeUrl` is not optional.** Without it, any question containing a space, `&`, `?`
or `#` produces a broken link — and it will *look* fine in testing until someone asks a
question with an apostrophe in it.

> ✅ **All three functions are confirmed supported in Copilot Studio.** `Concatenate`,
> `Char` and `EncodeUrl` all appear in the official
> [Power Fx formula reference for Copilot Studio](https://learn.microsoft.com/power-platform/power-fx/formula-reference-copilot-studio).

> **Finding the right variable name:** click the **{x}** icon in the formula bar to see
> every available variable. If your topic stores the question as `Topic.Question`, use that
> instead. The name must match exactly, including capitalisation.

✅ **Checkpoint:** the formula is accepted with no red error underline.

### Step A.6 — Show the link to the user

1. Under the Set-variable node, click **+ (Add node)** → **Send a message**.
2. Click the **fx** button to switch that message to a formula too.
3. Paste:

   ```powerfx
   Concatenate(
	 "No problem — I can connect you with someone from HR.",
	 Char(10), Char(10),
	 "[Start a chat with an HR representative](",
	 Topic.RepChatLink,
	 ")",
	 Char(10), Char(10),
	 "Your question is already filled in — just press Send."
   )
   ```

**What this produces:** a Markdown link. `[text](address)` renders in Teams as clickable
text. `Char(10)` inserts a line break (you cannot type Enter inside a formula).

> ✅ **Verified:** Teams supports **hyperlink with text** and **new line** in text-only bot
> messages. Not everything does — headers, lists, strikethrough and image links are **not**
> supported in text-only Teams messages, so avoid them in agent replies. See
> [Format your agent messages](https://learn.microsoft.com/microsoftteams/platform/bots/how-to/format-your-bot-messages#format-text-content).
>
> Note that Copilot Studio's own channel table rates Teams Markdown as *"partially
> supported"* — the link syntax used here is within the supported subset.

⚠️ **Tell the user they must press Send.** Without that sentence, people click the link,
see their question sitting in the box, assume it has been sent, and close the window. This
one sentence prevents the most common support complaint with this design.

✅ **Checkpoint:** the branch has two nodes — set the variable, then send the message.

### Step A.7 — Save, publish and test

1. Click **Save** (top right).
2. Click **Publish** → **Publish**. Wait for confirmation.
3. Open **Microsoft Teams** and start a chat with your agent.
4. Ask a question you know it cannot answer (for example: `What is the airspeed velocity of
   an unladen swallow?`).
5. The agent should offer both choices. Choose **Connect to a representative**.
6. Click the link.

✅ **Checkpoint — all four must be true:**
- Teams opens a chat containing you **and** the HR representatives.
- Your original question is pre-filled in the message box.
- The chat is titled `HR Benefits Support`.
- Pressing Send delivers the message to everyone in the chat.

> **Publishing lag:** Teams sometimes serves a cached version of the agent. If you do not
> see the new option after a few minutes, see [Troubleshooting](#troubleshooting).

### Step A.8 — Brief the HR representatives

Do not skip this. The reps will receive Teams messages from employees with no warning
about why.

Tell them:
- They will get **group chat messages**, not emails.
- Everyone on the list sees each message, so agree who answers — otherwise either everyone
  replies at once or nobody does.
- The question came from the benefits agent, which could not answer it.
- If the same employee asks again later, it lands in the **same** chat thread.

### Option A — pros and cons

**✅ Pros**

| Advantage | Detail |
|---|---|
| Zero cost | No licence, no Azure resource, no connector |
| Fastest to build | ~30 minutes, entirely in Copilot Studio |
| No code change | `function_app.py` untouched |
| Real Teams conversation | Full chat: threads, files, emoji, call escalation |
| Natural retention | The chat lives in the employee's own Teams history |
| Compliance-friendly | Normal Teams retention, eDiscovery and audit apply |
| Easy to reverse | Delete one topic branch |
| No new failure modes | No flow to time out, no card to expire |
| Follow-ups just work | The same chat thread is reused automatically |

**❌ Cons**

| Limitation | Consequence |
|---|---|
| **Rep identities fully exposed** | **Cannot be hidden. Disqualifies A when anonymity is required** |
| No routing | Every rep gets every request |
| No presence check | Requests go to people on leave |
| Fixed list | Changing reps means editing and republishing the agent |
| No SLA tracking | Nothing measures whether anyone replied |
| User must press Send | Some users will not |
| No transcript passed | Reps see only the question, not the conversation |
| Teams-only | Will not work if you later publish to a public website |
| Diffusion of responsibility | "Someone else will answer" — so nobody does |

**Choose A when:** identity is not sensitive, the rep list is small and stable, and you want
something working this afternoon.

**Avoid A when:** anonymity is required, volume is high enough to need routing, or you need
to measure response times.

---

## Part B — Copilot Studio handoff to Dynamics 365

**What you will build:** a genuine live handoff. The user stays in one conversation; a
human takes over from the bot. Full conversation history and context variables transfer
automatically.

**Time required:** days to weeks (this is a project, not a task).
**Cost:** Dynamics 365 Customer Service or Contact Center licences.
**Prerequisites:** significant — see below.

### ✅ Availability in GCC — verified

Good news, and worth confirming before anyone objects on compliance grounds:

| Product | GCC | GCC High | DoD |
|---|---|---|---|
| Dynamics 365 **Customer Service** (Enterprise & Professional) | ✅ | ✅ | ✅ |
| Dynamics 365 **Contact Center** | ✅ | ❌ | ❌ |
| **Omnichannel Engagement Hub** | ✅ | — | — |
| Contact Center **digital channels** (chat) in *GCC Moderate* | ✅ | ❌ | ❌ |
| Contact Center **voice** in *GCC Moderate* | ✅ ¹ | ❌ | ❌ |

¹ Microsoft notes that Azure Communication Services for the voice channel *"continue to run
in North America Commercial Cloud"* — relevant only if you later add voice, but a
compliance question worth raising early if so.

Purchasing in GCC is via **Volume Licensing or CSP**.

> So Option B is genuinely available to you. The blocker is **not** GCC availability — it is
> the Teams-channel fit question below and the authentication conflict in
> [Your scenario](#your-scenario--verified-facts-this-document-assumes).

### ⚠️ Read this caveat before you plan anything

Microsoft's documented handoff pattern is **"engagement hub at the front"**:

```
User ──► D365 chat widget (on a website) ──► adapter ──► Copilot Studio agent
					▲                                          |
					+──────── escalation event ◄───────────────+
```

The user chats in the **Dynamics chat widget on a web page** — *not* in Microsoft Teams.

**Your agent is published to Teams.** The documentation does not confirm that
`Transfer conversation` works cleanly for a Teams-channel conversation, and there are
signals suggesting caution:

- The docs warn that adding a `Transfer conversation` node causes a **"No renderer for this
  activity"** message on canvases that cannot render it, and say you must customise the
  chat canvas — something you cannot do inside the Teams client.
- For the Microsoft 365 Copilot channel, **"Hand-off to customer service representative" is
  explicitly listed as an unsupported node type.** Teams is a different channel, but this
  shows handoff is not universally supported across channels.
- In the classic Teams plan, triggering **Escalate ends the conversation.**

**Therefore: do not buy licences or plan a rollout until you have run Step B.1.**
> ### 🔧 Microsoft has an official sample that solves exactly this problem
>
> **[Copilot Studio Handover To Live Agent Sample](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/skill-handoff)**
> (in the official [microsoft/CopilotStudioSamples](https://github.com/microsoft/CopilotStudioSamples) repo)
>
> This sample **independently confirms the caveat above**. Its own README states that the
> traditional engagement-hub pattern has these limitations:
>
> - *"**Channel Restrictions**: It doesn't work well when customers want to use native
>   channels that Copilot Studio supports, such as Microsoft Teams or WebChat"*
> - *"**Orchestration Complexity**: Some CCaaS vendors require plugging the Copilot Studio
>   agent into their own virtual agent, creating a double layer of intent recognition"*
> - *"**Loss of Native Features**: Customers lose the benefits of Copilot Studio's native
>   channel integrations"*
>
> **What it does instead:** keeps the Copilot Studio agent **in control of the Teams
> channel** and uses an [Agents SDK skill](https://learn.microsoft.com/microsoft-copilot-studio/advanced-use-skills)
> to bridge to a live-chat API, with
> [Teams proactive messaging](https://learn.microsoft.com/microsoftteams/platform/bots/how-to/conversations/send-proactive-messages)
> carrying the human's replies back. That is the same proactive-message mechanism Option D
> uses in [Step D.6](#step-d6--deliver-the-answer-anonymously) — reached independently by
> Microsoft's own engineers, which is reassuring for the Option D design.
>
> **What ships in the sample:**
> - `ContosoLiveChatApp` — a stand-in live-chat system with an agent UI and REST APIs
>   (`/api/livechat/start`, `/send`, `/end`), *"meant to be replaced"* with ServiceNow,
>   Genesys, Salesforce Service Cloud, etc.
> - `HandoverToLiveAgentSample` — the skill that bridges Copilot Studio to that system.
>
> ⚠️ **Two caveats before you get excited.**
> 1. This is a **pro-code .NET solution**, not a low-code configuration. It is a
>    substantially bigger undertaking than Options A, C or D.
> 2. Microsoft flags the approach as transitional: *"Agents SDK Skills are currently
>    supported but not the recommended long-term pattern. For new implementations, consider
>    using [multi-agent orchestration](https://learn.microsoft.com/microsoft-copilot-studio/add-agent-microsoft-365-agents-sdk-agent)."*
>
> **Read it even if you do not build it.** It is the best available evidence about what does
> and does not work for live handoff on the Teams channel, and it will inform Step B.1.
>
> 📝 **Companion blog post:** the CAT team's
> [Handing Over to Live Agents Without Losing Control](https://microsoft.github.io/mcscatblog/posts/copilot-studio-handover-live-agent/)
> explains the same pattern in prose, and names a limitation not covered above — **No Return
> Path**: *"once the conversation is handed off to the engagement hub, there's no easy way to
> return it to your Copilot Studio agent. The user is stuck in the live chat experience, even
> for simple follow-up questions the agent could handle."*

### Step B.1 — Prove it works before you commit

**This is the most important step in Option B.** Do it before anything else.

1. Obtain a **trial** of Dynamics 365 Customer Service (do not purchase yet).
2. Connect it to a **test copy** of your agent — never the production agent.
3. Publish that test agent to Teams.
4. From the Teams client, trigger the escalation.
5. Observe carefully:

| Question | Why it matters |
|---|---|
| Does the conversation transfer at all? | The core question |
| Does the user see "No renderer for this activity"? | Means the Teams canvas cannot render the handoff |
| Does the agent conversation **end** instead of handing off? | Escalate ends conversations on some channels |
| Does the live agent see the full history? | The main advantage of B over A and C |
| Can the user reply and reach the human? | Confirms two-way flow, not just a one-way alert |

✅ **Checkpoint:** a real two-way conversation between a Teams user and a human in the
D365 agent console, with history visible.
❌ **If this fails, stop.** Option B does not fit your Teams-published architecture. Go to
Option A or C.

### Step B.2 — Understand what transfers automatically

If the POC succeeds, this is what makes B genuinely better. Copilot Studio sends these
context variables to the engagement hub automatically:

| Variable | What it carries | Example |
|---|---|---|
| `va_Scope` | Routing scope | `"agent"` |
| `va_LastTopic` | The last topic triggered | `"Dental coverage"` |
| `va_Topics` | All topics triggered by the user | `["Greeting", "Dental coverage"]` |
| `va_LastPhrases` | The user's most recent phrasing | `"Is a crown covered?"` |
| `va_Phrases` | Everything the user said | `["Hi", "Is a crown covered?"]` |
| `va_ConversationId` | Unique conversation ID | `6dba796e-...` |
| `va_AgentMessage` | Private note to the human | `"Could not answer benefits question"` |
| `va_BotId` | Which agent handed off | `6dba796e-...` |
| `va_Language` | User's language | `"en-us"` |
| *Your own topic variables* | Anything you defined | `@PlanType = "PPO"` |

Variables are gathered **across all topics** the user passed through and merged. If two
topics define the same variable name, the most recently set value wins.

> This is why B is the "real" answer: the human starts already knowing what was asked, what
> was tried, and what the bot failed at. In Options A and C, they get only the question text.

### Step B.3 — Connect the agent to Dynamics 365

Only after Step B.1 succeeded.

1. In Copilot Studio, open your agent → **Channels**.
2. Under **Customer engagement hub**, click the **Dynamics 365 Customer Service** tile.
3. Click **Enable**.
4. Under **See the environment this bot is connected to**, select the environment where
   D365 Customer Service is enabled.

   ⚠️ The agent and D365 **must be in the same environment**, or analytics will not work.

5. Click **See how to register a new Application ID** and follow the steps to create an app
   registration.
6. In the Azure Portal (`portal.azure.us`) → **App registrations** → **Overview**, copy the
   **Application (client) ID**.
7. Paste it into the **Application ID** box in Copilot Studio.

   ⚠️ **The Application ID must be unique to this agent.** D365 models agents as
   "application users." Reusing an ID across agents causes error `1004`
   (`DuplicateBotAppId`).

8. Click **Add your agent**.

> Copilot Studio uses a **Teams channel** internally to talk to D365. If one is not already
> enabled, this step enables it automatically.

✅ **Checkpoint:** the tile shows **Connected**, and **View details in Dynamics 365** is
available.

### Step B.4 — Add the Transfer conversation node

Agents created in Copilot Studio do **not** have this node by default (agents created from
D365 do).

1. In the left navigation, click **Topics** → **System** tab.
2. Open the **Escalate** topic.
3. At the bottom, click **+ (Add node)** → **Topic Management** → **Transfer conversation**.
4. In the **Private message to agent** box, type context for the human, e.g.
   `Benefits agent could not answer. See conversation history.`
5. **Save**.

**Two ways this now triggers:**

| Trigger type | When |
|---|---|
| **Implicit** | The user types "talk to agent", "escalate", "can I talk to a human" — or the Fallback topic gives up after two failed attempts |
| **Explicit** | You add a `Transfer conversation` node to a specific topic yourself |

To offer it as a choice next to "Email HR", add an option to your existing Question node
(as in [Step A.4](#step-a4--add-the-second-choice)) and, in that branch, add
**Topic Management** → **Go to another topic** → **Escalate**.

✅ **Checkpoint:** conversations reaching this node are marked **Escalated** in Copilot
Studio analytics.

### Step B.5 — Configure routing on the Dynamics side

This is Dynamics 365 configuration, not Copilot Studio, and is normally done by a D365
administrator. In outline:

1. Create a **workstream** for HR benefits.
2. Create a **queue** and add the HR representatives.
3. Add **routing rules** — you can route on the context variables from Step B.2.
4. Assign representatives to the queue.

⚠️ **Testing on a website:** you must use the **embed code from the D365 chat widget**. If
you use the embed code from Copilot Studio, handoff will not work.

### Step B.6 — Hide representative names (anonymity)

Dynamics 365 has a **built-in setting** for this. You do not need a workaround.

1. Open the **Copilot Service admin center**.
2. Go to the **workstream** that contains your chat widget.
3. Click **Edit** on the chat widget.
4. On the **Chat channel Settings** page, open the **Chat widget** tab.
5. Find the **Agent display name** field and choose one of:

| Setting | What the employee sees |
|---|---|
| **Full name** | `Jane Doe` — the default |
| **First name** | `Jane` |
| **Last name** | `Doe` |
| **Nick name** | `HR Specialist 1` — **choose this for anonymity** |

6. Click **Save**.

The nickname is read from the **Omnichannel user record** for each representative, so
somebody must populate it for every rep.

⚠️ **Two ways this leaks. Plan for both.**

1. **It fails open, not closed.** Microsoft's documentation states: *"If a nickname is not
   available in the user record, the full name is displayed to the customers."* Miss one
   representative during onboarding and their real name is shown. Make "set the Omnichannel
   nickname" a required step in your HR onboarding checklist, not an afterthought.

2. **Anonymity breaks on transfer.** *"The selected service representative's name is
   displayed in the chat widget only while chatting with a customer. For consultation or
   chat transfer, the full name of the representative is used."* So if a rep consults a
   colleague or transfers the chat, the real name appears. Brief representatives that
   transfers are not anonymous.

✅ **Checkpoint:** start a test chat, have a representative accept it, and confirm the
employee sees the nickname and not the real name. Then repeat for a **transferred** chat so
you see the leak for yourself and can decide whether it is acceptable.

### Option B — pros and cons

**✅ Pros**

| Advantage | Detail |
|---|---|
| Genuine live chat | The only option with a human responding in real time |
| Real routing and queues | Workstreams, skills-based routing, overflow rules |
| Presence-aware | Skips representatives who are away or at capacity |
| Full context transfer | All `va_*` variables plus your own topic variables |
| Built-in anonymity | The **Nick name** setting, no workaround needed |
| Purpose-built console | Agents handle several conversations with full history |
| SLA and analytics | Escalation-rate drivers, deflection reporting |
| Supervisor tooling | Monitoring, barge-in, sentiment |
| Scales | Designed for hundreds of concurrent conversations |

**❌ Cons**

| Limitation | Consequence |
|---|---|
| **Teams-channel fit unproven** | Documented pattern is hub-at-the-front; **needs a POC** ([Step B.1](#step-b1--prove-it-works-before-you-commit)) |
| **Authentication conflict** | "Authenticate with Microsoft" is unavailable with D365 — may break `send_hr_email` |
| Licence cost | Per-representative D365 Customer Service / Contact Center |
| Weeks, not hours | Workstreams, queues, routing, training |
| Needs a D365 administrator | Not a Copilot Studio maker task |
| Anonymity leaks on transfer | Consultation and transfer reveal the full name |
| Anonymity fails open | Missing nickname → real name displayed |
| Same-environment constraint | Agent and D365 must share an environment or analytics break |
| Staffing model required | Live chat implies someone is actually rostered |

**Choose B when:** you already own Dynamics 365, or live chat with routing and SLA is a
genuine business requirement with budget and staffing behind it.

**Avoid B when:** you want something working soon, cannot staff a live queue, or cannot
absorb the authentication rework.

### Option B — summary

**You get:** real live chat, routing, queueing, presence awareness, full history transfer,
agent console, SLA reporting, escalation-rate analytics.

**You pay with:** licence cost, a multi-week project, D365 administration skills, and the
architectural risk in Step B.1.

---

## Part C — Post to an HR Teams channel via Power Automate

**What you will build:** when the agent cannot answer, a message is posted into an HR Teams
**channel**. HR monitors the channel and follows up. This is the pattern used in
Microsoft's own HR agent tutorial.

**Time required:** about 45 minutes.
**Cost:** likely none — this uses the **standard** Teams connector, not the premium HTTP
action. See [A note on Power Automate licensing](#a-note-on-power-automate-licensing).

⚠️ **This is asynchronous.** The user is told "HR has been notified." Nobody is waiting on
the other end. Word the confirmation message honestly or you will create false
expectations.

### Step C.1 — Create the Teams channel

1. In Teams, go to the HR team (or create one).
2. Click **⋯** next to the team name → **Add channel**.
3. Name it, e.g. `Benefits Agent Escalations`.
4. Choose **Standard** (private channels behave differently with Power Automate).
5. Add the HR representatives as members.

✅ **Checkpoint:** you can see the channel and post in it manually.

### Step C.2 — Create the flow

1. In Copilot Studio, open your agent → **Topics** → open the topic with the `canAnswer`
   check.
2. Add an option to the Question node called `Connect to a representative`
   (as in [Step A.4](#step-a4--add-the-second-choice)).
3. In the new branch, click **+ (Add node)** → **Add a tool** → **Create a flow**.
   Power Automate opens in a new browser tab.

> **Pop-ups:** if nothing opens, your browser is blocking pop-ups for
> `gov.flow.microsoft.us`. Allow them and retry.

✅ **Checkpoint:** Power Automate is open with a template containing
**When an agent calls the flow**.

### Step C.3 — Define the inputs

1. Click the **When an agent calls the flow** trigger node.
2. Click **+ Add an input** → **Text** → name it `Question`.
3. Repeat for: `UserName`, `UserEmail`, `ConversationId`.

✅ **Checkpoint:** four text inputs, spelled exactly as above.

### Step C.4 — Add the Teams action

1. Click **+ New step**.
2. Search for and select **Post message in a chat or channel**.
3. Fill in:

| Field | Value |
|---|---|
| **Post as** | `Flow bot` |
| **Post in** | `Channel` |
| **Team** | your HR team |
| **Channel** | `Benefits Agent Escalations` |
| **Message** | see below |

4. For **Message**, type static text and insert the dynamic values from Step C.3 using the
   lightning-bolt icon:

   ```
   New escalation from the Benefits agent

   From:      <UserName> (<UserEmail>)
   Question:  <Question>

   Conversation ID: <ConversationId>
   ```

> **Post as `Flow bot` vs `User`:** `Flow bot` posts as an automation, which is clearer and
> avoids "why did Jane post this?" confusion. Microsoft's tutorial uses `User`; either
> works. `Flow bot` is the better default for an automated escalation.

5. Rename the flow (top of page) to `Post HR Escalation to Channel`.
6. Click **Save**.

✅ **Checkpoint:** the flow saves without validation errors.

### Step C.5 — Wire the flow into the topic

1. Return to the Copilot Studio browser tab.
2. **Reload the page** — new flows do not appear until you do.
3. In your new branch, click **+ (Add node)** → **Add a tool** → select
   **Post HR Escalation to Channel**.
4. Map each input to a variable:

| Flow input | Map to |
|---|---|
| `Question` | your question variable, e.g. `Topic.UserQuestion` |
| `UserName` | `System.User.DisplayName` |
| `UserEmail` | `System.User.PrincipalName` |
| `ConversationId` | `System.Conversation.Id` |

> **Why `PrincipalName` and not `Email`?** Both exist, but your other flows already use
> `System.User.PrincipalName` (see `EMAIL_HR_DEPLOYMENT_CHECKLIST.md`, Section 9). Staying
> consistent avoids a class of bug where one flow works and another silently receives a
> blank value. Both require the agent to be authenticated.

5. Add a **Send a message** node after it:

   > `I've passed your question to the HR team. Someone will follow up with you directly.`

⚠️ Do **not** write "connecting you now" or "please hold." Nobody is joining the
conversation. Set the expectation accurately.

✅ **Checkpoint:** the branch calls the flow, then confirms to the user.

### Step C.6 — Publish and test

1. **Save**, then **Publish**.
2. In Teams, ask the agent an unanswerable question.
3. Choose **Connect to a representative**.
4. Check the HR channel.

✅ **Checkpoint:** the message appears in the channel with the correct name, email and
question, and the user saw the confirmation.

### Option C — pros and cons

**✅ Pros**

| Advantage | Detail |
|---|---|
| Microsoft's own pattern | This is what the official Teams quickstart teaches |
| Likely no new licence | Uses the **standard** Teams connector, not the premium HTTP action |
| Anonymous by default | Posting as Flow bot names nobody |
| Visible shared queue | The whole team sees the backlog |
| Simple to reason about | One flow, one action, easy to debug |
| Searchable history | Channel messages are searchable and retained |
| Works with high volume | Nothing times out; messages just accumulate |
| Easy to extend | Add an approval, a SharePoint list, or a ticket later |

**❌ Cons**

| Limitation | Consequence |
|---|---|
| **One-way** | **No answer path back to the employee** — the biggest weakness |
| Async | Nobody is waiting; response time depends on HR habits |
| HR must switch tools | They reply by email or a new chat, losing the thread |
| No routing or assignment | Requests can be collectively ignored |
| Channel noise | High volume makes the channel unusable |
| Nothing tracks resolution | No SLA measurement |
| Reply de-anonymises | If HR replies personally, anonymity is lost anyway |

**Choose C when:** HR already lives in Teams channels, follow-up happens outside the agent,
and you want the simplest possible intake.

**Avoid C when:** the employee expects an answer in the agent, or you need a closed loop.

> **C and D are close relatives.** C posts a message; D posts a *card that can be answered*
> and relays the reply. If you are building C, consider building D instead — it is roughly
> an hour more work for a complete round trip.

---

## Part D — Anonymous relay (recommended for anonymity)

**What you will build:** the employee asks a question. It appears in an HR channel as a
card. A representative types an answer into the card. The **Flow bot** delivers that answer
back to the employee as a direct message. The employee never learns who wrote it.

**Time required:** about 2 hours.
**Cost:** likely none — the Teams connector actions used here are **standard**. See
[A note on Power Automate licensing](#a-note-on-power-automate-licensing).
**Prerequisites:** maker access to the agent, and permission to create a Teams channel.

> **This is the recommended option when anonymity is required.** It is the only approach
> that hides the representative's identity *and* returns a real human answer *and* needs no
> new licences.

### How the relay works

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

The employee sees a message from **the agent** (or a bot). The representative's name
appears nowhere in what the employee receives.

### ⚠️ The 100-second rule — read before building

This is the single most important constraint, and getting it wrong is the most likely way
to break this design.

- An agent flow must **respond to the agent within 100 seconds**, or it fails with
  `FlowActionTimedOut`.
- A human will not answer within 100 seconds.

> **Note on the number.** General Power Automate documentation cites a 120-second limit for
> synchronous requests, but the Copilot Studio agent-flow documentation is more specific and
> stricter: *"Respond to the agent within the 100 second action limit."* Design for **100
> seconds**.

**The resolution:** actions placed **after** the response action keep running. Microsoft's
agent-flow documentation is explicit:

> *"Actions in the flow that need to run longer can be placed after the **Respond to the
> agent** action to continue to run up to the flow run duration limit of 30 days."*

So the flow must be ordered like this:

| Order | Action | Why |
|---|---|---|
| 1 | **When an agent calls the flow** (trigger) | Receives the question |
| 2 | **Respond to the agent** — "Your question has been sent" | **Must happen inside 100 s** |
| 3 | Post the Adaptive Card and wait for a response | Runs *after* the response; can take hours |
| 4 | Flow bot DMs the answer to the employee | Runs whenever the rep replies |

⚠️ **If you put the waiting step before the response step, the flow times out and the
feature fails.** Order matters more than anything else in this Part.

**Maximum wait:** a flow run can last **30 days**; pending steps time out after that. Set a
shorter, explicit timeout — see [Step D.5](#step-d5--add-a-timeout-path).

> ### 💡 A newer, simpler alternative may be available to you
>
> Microsoft has since added **[asynchronous response support for agent
> flows](https://learn.microsoft.com/microsoft-copilot-studio/flow-asynchronous-response)**.
> Where supported, you turn **Asynchronous response** *On* in the **Respond to the agent**
> settings and the flow may run past two minutes while still calling back to the agent when
> it finishes.
>
> **Two things make this genuinely attractive here:**
> - The callback is *"fully supported in Microsoft Teams"* — your channel.
> - The answer could return **in the agent conversation** rather than in a separate Flow bot
>   chat, removing Option D's most awkward limitation.
>
> ⚠️ **But do not assume you have it.** It requires an environment on the
> [new Power Automate infrastructure](https://learn.microsoft.com/power-automate/environment-architecture).
> In an environment without it, *"the agent might receive a 'flow completed' response
> immediately while the flow continues to run in the background."*
>
> **Check first, then choose:** open any agent flow → **Respond to the agent** → **Settings**.
> If an **Asynchronous response** toggle exists, your environment supports it and you should
> evaluate this simpler design before building the respond-first pattern below. If the toggle
> is absent, follow the steps as written.
>
> The respond-first pattern documented here works in **both** cases, which is why it remains
> the default recommendation.

### Step D.1 — Create the HR intake channel

⚠️ **Prerequisite:** Microsoft's adaptive-card tutorial states you need **Microsoft Teams
with the Workflows app installed**. Workflows is available in **GCC** (but not GCC High or
DoD). If cards never appear, verify the Workflows app is enabled in your Teams admin center
before debugging the flow itself.

1. In Teams, go to the HR team.
2. Click **⋯** next to the team name → **Add channel**.
3. Name it, e.g. `Benefits Questions (Anonymous Relay)`.
4. Choose **Standard**.

⚠️ **Standard, not private.** Microsoft documents that posting as a Flow bot in **private
channels** is *"under development"*. Shared and standard channels are supported. Choosing
private here will cost you hours of debugging.

5. Add the HR representatives as members.

✅ **Checkpoint:** the channel exists, is standard, and you can post in it manually.

### Step D.2 — Create the flow and define its inputs

1. In Copilot Studio, open your agent → **Topics** → open the topic with the `canAnswer`
   check.
2. Add an option to the Question node called `Connect to a representative`
   (as in [Step A.4](#step-a4--add-the-second-choice)).
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
> flow** and **Respond to the agent**. Older documentation and blog posts say *"When Copilot
> Studio calls a flow"* and *"Respond to Copilot"*. If your tenant still shows the older
> labels, they are the same actions.

⚠️ **The flow must live in a solution.** Microsoft states: *"To be available to agents,
flows must be stored in a solution in the same Power Platform environment."* Creating the
flow from inside Copilot Studio (step 3) handles this for you. If you instead build it from
**My flows**, you must add it to a solution afterwards or the agent will not see it.

✅ **Checkpoint:** four text inputs, spelled exactly as above.

### Step D.3 — Respond to the agent FIRST

This is the step that satisfies the 100-second rule. Do it before adding anything else.

1. Click **+ New step**.
2. Search for the **Copilot** connector and select **Respond to the agent**.
3. Add one text output named `Status`.
4. Set its value to: `sent`

⚠️ **Check that Asynchronous response is Off.** Select the **Respond to the agent** action
→ **Settings** → under **Networking**, confirm **Asynchronous response** is **Off**. Flows
created from Copilot Studio default to Off, but verify it. With it On in an environment that
does not support the newer callback feature, the agent shows
*"Something unexpected happened. We're looking into it. Error code: 3000."*

✅ **Checkpoint:** the response action sits immediately after the trigger, before any
waiting step.

### Step D.4 — Post the card and wait for an answer

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
> This is the part beginners most often get stuck on, so it is worth stating explicitly.
>
> **The `id` of an `Input.Text` becomes the name of the dynamic-content token.** In the card
> above the input is `"id": "answer"`, so after the card action a dynamic value named
> **`answer`** appears in the lightning-bolt picker. That is what you insert in
> [Step D.6](#step-d6--deliver-the-answer-anonymously).
>
> Microsoft's [lead collection sample](https://learn.microsoft.com/power-automate/lead-collection-sample)
> shows the same mechanism: each `Input.Text` `id` (`acLeadFName`, `acLeadEmail`, …) becomes
> a "Response **output**" token. Use distinctive `id` values \u2014 a generic `answer` is fine
> here because there is only one input, but with several inputs, meaningful ids make the
> picker readable.
>
> \u26a0\ufe0f **`submitActionId` is different.** Microsoft's proactive-card documentation says *"To
> use the response from the recipient, select **submitActionId**… the value of this variable
> is the `title` of the action the user selected."* That tells you **which button** was
> pressed \u2014 not what was typed. For Option D you want the **`answer`** token, not
> `submitActionId`. You would only need `submitActionId` if you added multiple buttons (for
> example *Send answer* vs *Cannot answer*).

> ### ⚠️ Adaptive Card schema version — Teams caps at 1.5
>
> Microsoft's [Adaptive Cards overview](https://learn.microsoft.com/microsoft-copilot-studio/adaptive-cards-overview)
> documents host-specific limits:
>
> | Host | Max schema version |
> |---|---|
> | **Microsoft Teams** | **1.5** |
> | Live chat widget (Omnichannel) | 1.5 |
> | Bot Framework Web Chat | 1.6 (but no `Action.Execute`) |
>
> The card above specifies `"version": "1.4"`, safely inside the Teams limit — **leave it
> alone unless you have a reason to change it.**
>
> ⚠️ **The trap:** the [Adaptive Cards Designer](https://adaptivecards.io/designer/) will
> happily emit a **1.6** card. Paste that into a Teams-bound flow and elements may silently
> fail to render. If you edit the card visually, set the target version to **1.5 or lower**
> before copying the JSON back.
>
> Also note: *"Copilot Studio only renders version-1.6 cards in the test chat, not on the
> canvas"* — a card can look fine in one place and broken in another.

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
> This matters here because your HR channel will accumulate **many similar-looking cards**.
> Details: [Submit button behavior with consecutive cards](https://learn.microsoft.com/microsoft-copilot-studio/authoring-ask-with-adaptive-card#submit-button-behavior-for-agents-with-consecutive-cards).

5. Set **Update message** to: `Answer sent to the employee.`

⚠️ Configure the update message. Without it the card resets and looks unanswered, and a
second representative will answer the same question.

✅ **Checkpoint:** the card action is *below* the response action, and has a multiline text
input plus a submit button.

### Step D.5 — Add a timeout path

Without this, an unanswered question hangs for 30 days and the employee is never told.

1. Click the **…** menu on the card action → **Settings**.
2. Set **Timeout** to an ISO 8601 duration — `PT8H` means 8 hours.
3. Click **Done**.
4. Add a **Post message in a chat or channel** action.
5. Click its **…** menu → **Configure run after** → tick **has timed out** (and untick
   **is successful**).
6. Configure it as in Step D.6, with a message such as:

   > `HR did not respond to your question within 8 hours. Your question has been recorded and someone will follow up by email.`

✅ **Checkpoint:** a branch exists that runs only when the card times out.

### Step D.6 — Deliver the answer anonymously

This is the step that produces the anonymity. **There are two ways to do it, and the first
is better** — it is Microsoft's officially documented *proactive message* pattern.

#### Option 1 (recommended) — deliver as the agent itself

Microsoft documents this in
[Send proactive Microsoft Teams messages](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message).
The answer arrives from **your benefits agent**, in the same chat the employee was already
using — not from a separate bot.

1. Add a **Post message in a chat or channel** action after the card action.
2. Configure:

| Field | Value | Why |
|---|---|---|
| **Post as** | `Microsoft Copilot Studio agent` | **The anonymity control**, and the answer looks like it came from the agent |
| **Post in** | `Chat with agent` | The employee's existing agent chat |
| **Agent** | your HR Benefits agent | Which agent it appears to be from |
| **Recipient** | the `UserEmail` input | Who receives it |
| **Message** | see below | The answer |

✅ **Why this is better than the Flow bot:** the reply lands in the conversation the
employee already has open, rather than in a separate "Flow bot" chat they must go find. It
removes Option D's most awkward limitation.

⚠️ **Prerequisites Microsoft states explicitly.** An agent **cannot** deliver a proactive
message if the recipient:
- has not **installed** the agent in Teams,
- has **uninstalled** or **blocked** it, or
- lacks permission to chat with it (you must [share the agent](https://learn.microsoft.com/microsoft-copilot-studio/admin-share-bots)).

In your scenario the employee *just used the agent*, so it is installed. But if you ever
send proactively to people who have not used it, this bites.

⚠️ **Other documented limitations:**
- Proactive messages **can only go to a personal chat with the agent** — not to channels.
- The flow **must be in the same environment** as the agent.
- Proactive messages **do not appear in conversation transcripts or analytics session
  data.** This is why the telemetry event below matters: without it these interactions are
  invisible in reporting.
- If the agent is disconnected and reconnected to Teams, users must reinstall it before
  proactive messages resume.

> **Useful advanced options** (under **Show advanced options** on the action):
>
> | Option | What it does |
> |---|---|
> | **Label as notification** | Prefixes "Notification via" before the agent name |
> | **If the chat with the agent is active** | Send / Don't send and succeed (status `300`) / Don't send and fail |
> | **If the agent is not installed** | Fail / Succeed with status code (`100`) |
>
> Status codes: `200` delivered, `100` agent not installed, `300` recipient in an active
> conversation. Branch on these to log failures rather than losing answers silently.

#### Option 2 (fallback) — deliver as the Flow bot

Use this if **Post as → Microsoft Copilot Studio agent** is unavailable in your tenant, or
if the agent-installed prerequisite is a problem.

| Field | Value | Why |
|---|---|---|
| **Post as** | `Flow bot` | Sends as a generic bot, not a person |
| **Post in** | `Chat with Flow bot` | Direct message to one user |
| **Recipient** | the `UserEmail` input | Who receives it |
| **Message** | see below | The answer |

⚠️ **`Post as` must never be `User`.** That sends the message as *the account signed in to
the Teams connector* — usually the flow owner — and anonymity is lost immediately. This is
the single most likely configuration mistake in Option D.

#### The message body (either option)

3. For **Message**, use text plus the card's response:

   ```
   HR has answered your question:

   <insert the "answer" output from the adaptive card>

   If you need more help, just ask me again.
   ```

   Insert the answer using the lightning bolt → the `answer` field from the card action.

✅ **Checkpoint:** the message is addressed to `UserEmail` and posts as either
`Microsoft Copilot Studio agent` or `Flow bot` — **never** as `User`.

4. Rename the flow to `Anonymous HR Relay` and click **Save**.

### Step D.7 — Wire the flow into the topic

1. Return to Copilot Studio and **reload the page**.
2. In your branch: **+ (Add node)** → **Add a tool** → **Anonymous HR Relay**.
3. Map the inputs:

| Flow input | Map to |
|---|---|
| `Question` | your question variable, e.g. `Topic.UserQuestion` |
| `UserEmail` | `System.User.PrincipalName` |
| `UserName` | `System.User.DisplayName` |
| `ConversationId` | `System.Conversation.Id` |

⚠️ **`UserEmail` must not be blank.** It is the delivery address for the answer. If the
agent is not authenticated, `System.User.PrincipalName` is empty and the Flow bot has
nowhere to send the reply. This is the same dependency your `send_hr_email` feature already
has.

4. Add a **Send a message** node after it:

   > `I've sent your question to the HR team. You'll get an answer here, usually within a few hours.`

⚠️ **Match the wording to your delivery choice.** If you used **Post as → Microsoft Copilot
Studio agent** (recommended), the reply arrives in *this same chat* and the wording above is
correct. If you used the **Flow bot** fallback, change it to *"you'll get an answer as a
direct message from Flow bot"* — otherwise users will not know where to look.

✅ **Checkpoint:** the branch calls the flow, then confirms to the user.

### Step D.8 — Publish and test end to end

1. **Save**, then **Publish**.
2. In Teams, ask the agent an unanswerable question and choose
   **Connect to a representative**.
3. Confirm you get the "sent" confirmation **within a few seconds** — this proves the
   100-second rule is satisfied.
4. Check the HR channel for the card.
5. As a representative, type an answer and click **Send answer**.
6. As the employee, check for a Flow bot direct message.

✅ **Checkpoint — all five must be true:**
- The confirmation appeared immediately, not after a long pause.
- The card reached the HR channel with the question and the employee's name.
- The card updated to `Answer sent to the employee.` after submission.
- The employee received the answer **from the agent** (or Flow bot) — not from a named person.
- **Nowhere in the employee's Teams client does the representative's name appear.**

⚠️ Verify the last point deliberately. Click the sender, open the profile, and confirm it
resolves to the bot and not to a person.

### Step D.9 — Brief the representatives

Anonymity is a *convention* as much as a configuration. It survives only if the humans
cooperate.

Tell representatives:
- **Do not sign your answer.** Typing `— Jane` in the answer box defeats the entire design.
- **Do not follow up from your own mailbox or start a Teams chat** with the employee.
- Everything you type in the card goes verbatim to the employee.
- Agree who answers, so one person claims each card. Only the **first** submission counts.

### 🆕 Variant D2 — use the native "Request for information" action instead

Copilot Studio has a **built-in action** that does most of what Steps D.4–D.5 build by hand:
**[Request for information (RFI)](https://learn.microsoft.com/microsoft-copilot-studio/flows-request-for-information)**,
found under **Human review** in the agent-flow designer.

It pauses the flow, emails designated reviewers, collects structured input, and resumes with
their answers available as dynamic content. Configure a **Title**, **Message**, **Assigned
to**, and typed inputs (Text, Yes/No, Email, Number, Date — with optional fields, placeholder
text, and single- or multi-select dropdowns).

**How it compares to the Adaptive Card build:**

| | Card build (Steps D.4–D.5) | **RFI action (D2)** |
|---|---|---|
| Where HR responds | Teams channel card | **Outlook email** |
| Setup effort | Hand-written JSON, timeout branch | A few fields in the designer |
| Typed/validated inputs | Manual | ✅ Built in |
| Shared visible queue | ✅ Whole channel sees it | ❌ Individual emails |
| First response wins | ✅ | ✅ (*"the response from the first person to respond is used"*) |
| Anonymity to the employee | ✅ (delivery step is unchanged) | ✅ (delivery step is unchanged) |

⚠️ **Constraints Microsoft states explicitly:**
- *"All requests are currently sent via **Outlook only**."*
- *"Requests **can't be sent to users outside of your tenant**."*
- **Known issue:** outputs can come back wrapped in `{{ }}` — *"ensure that input names are
  configured without spaces."*

> **Which to choose?** If HR lives in Outlook and you want the simplest possible build, D2 is
> less work and gives you validated inputs for free. If you want a **visible shared queue**
> that the whole HR team can see and triage — the main reason this document recommends a
> channel — stay with the card build. The anonymous delivery step
> ([Step D.6](#step-d6--deliver-the-answer-anonymously)) is identical either way.
>
> Related: [Multistage and AI approvals](https://learn.microsoft.com/microsoft-copilot-studio/flows-advanced-approvals)
> (preview) if an answer ever needs sign-off before reaching the employee.

### Option D — pros and cons

**✅ Pros**

| Advantage | Detail |
|---|---|
| **Anonymous by design** | Anonymity comes from the transport, not a setting that can fail open |
| **Closes the loop** | Unlike C, the answer reaches the employee |
| **Answer can arrive from the agent** | Officially documented proactive-message pattern; lands in the same chat |
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
| **Invisible to Copilot Studio analytics** | Proactive messages do **not** appear in transcripts or session data — add the telemetry event |
| **Requires the agent to be installed** | Proactive delivery fails (status `100`) if the employee removed the agent |
| One round trip per card | No follow-up question in the same thread |
| First response wins | Later submissions ignored |
| Card submits once | A rep cannot revise an answer |
| No routing | Every rep sees every card |
| Channel noise at volume | Microsoft names this limitation directly — built-in connectors *"own the delivery channel."* See [the CAT post on custom human-in-the-loop](https://microsoft.github.io/mcscatblog/posts/human-in-the-loop-custom-connector/) for the scaling answer |
| 30-day ceiling | Mitigated by the timeout in [Step D.5](#step-d5--add-a-timeout-path) |
| Anonymity is conventional | One rep signing their name undoes it |
| Not in DoD | Adaptive cards unsupported there. **GCC is fine** |
| More moving parts than A | A flow, a card, a timeout branch — more to break |

**Choose D when:** anonymity matters and you want a complete question-and-answer loop
without buying Dynamics 365. **This is the recommended option for your scenario if
anonymity is required.**

**Avoid D when:** you need genuine back-and-forth conversation (that is Option B), or you
cannot brief representatives on not signing their answers.

> **Want back-and-forth conversation?** That is genuinely Option B's territory. Option D
> handles question-and-answer well; it is not a chat system.

---

## Anonymity — what it does and does not protect

Be precise with stakeholders about what "anonymous" means here, or you will over-promise.

### What is genuinely hidden

✅ The employee does not see the representative's name, photo, presence or contact details
in the conversation.
✅ There is no clickable profile leading back to the person.
✅ The employee cannot start a direct chat with whoever answered.

### What is NOT hidden

❌ **The employee's identity is fully visible to HR.** This is deliberate — HR needs to know
who is asking to answer benefits questions correctly. Anonymity here is **one-directional**.

❌ **Audit, compliance and eDiscovery still see everything.** Teams messages, channel posts
and flow run histories are retained and discoverable under your tenant's normal policies.
In a government tenant this is a **requirement**, not a leak.

❌ **Administrators can trace it.** Power Automate run history shows exactly which account
submitted which card.

❌ **Writing style is not anonymised.** In a small HR team, colleagues recognise each
other's phrasing.

> **State it accurately to employees.** Something like: *"Your question is answered by a
> member of the HR benefits team. Individual responders are not identified."* That is true.
> *"Completely anonymous"* is not.

> ⚠️ **Microsoft's Responsible AI guidance makes this a requirement, not a preference.**
> The [onboarding-agent architecture](https://learn.microsoft.com/power-platform/architecture/solution-ideas/onboarding-agent)
> states that agents *"should make clear when the user is interacting with an agent and when
> they're receiving a response from a human."*
>
> Anonymising **who** answered is fine. Obscuring **that a human answered** is not. This
> matters most in Option D, where the reply can arrive styled as the agent — the message
> text must still say a person wrote it.

### The human factor

Every technical control here can be undone by one person signing their name. Whichever
option you choose, [Step D.9](#step-d9--brief-the-representatives)-style briefing is not
optional — it is load-bearing.

---

## Official Microsoft tutorials and quickstarts

Where Microsoft publishes a step-by-step walkthrough for something close to each option.

### Option A — deep links

| Resource | What it covers | Closeness |
|---|---|---|
| [Deep link to Teams chat](https://learn.microsoft.com/microsoftteams/platform/concepts/build-and-test/deep-link-teams) | Exact URL format, `users` / `topicName` / `message` | **Reference, not a tutorial** |
| [Deep link to a workflow in Teams](https://learn.microsoft.com/microsoftteams/platform/concepts/build-and-test/deep-link-workflow) | Starting a chat from a card button (`openUrl`) | Close |
| [Deep link consuming Subentity ID (GitHub sample)](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/Archived/tab-deeplink/csharp) | Runnable sample: calls, chats, tab navigation | Sample code |
| [Format your agent messages](https://learn.microsoft.com/microsoftteams/platform/bots/how-to/format-your-bot-messages#format-text-content) | **Which Markdown Teams actually renders** — confirms hyperlinks work, headers/lists do not | **Reference for Step A.6** |
| 🔧 [OfficeDev/Microsoft-Teams-Samples](https://github.com/OfficeDev/Microsoft-Teams-Samples) | Microsoft's full Teams sample catalogue, including deep-link samples | Working code |

⚠️ **There is no official end-to-end tutorial for "Copilot Studio topic → Teams deep link."**
The URL format is documented; wiring it into a Power Fx formula is not. That combination is
this document's own construction, which is why [Step A.2](#step-a2--build-and-test-the-link-by-hand)
tells you to test the raw URL first.

### Option B — Dynamics 365 handoff

| Resource | What it covers | Closeness |
|---|---|---|
| [Hand off to a live agent](https://learn.microsoft.com/microsoft-copilot-studio/advanced-hand-off) | Escalate topic, Transfer conversation node, context variables | **Primary walkthrough** |
| [Configure handoff to Dynamics 365 Customer Service](https://learn.microsoft.com/microsoft-copilot-studio/configuration-hand-off-omnichannel) | Numbered connection steps, App ID registration | **Step-by-step** |
| [Configure agent display name](https://learn.microsoft.com/dynamics365/customer-service/administer/agent-display-name) | The nickname anonymity setting | **Step-by-step** |
| [Configure Omnichannel with Power Pages site agent](https://learn.microsoft.com/power-pages/configure/omnichannel) | End-to-end handoff config, click by click | Very close (Power Pages, not Teams) |
| [Hand off to ServiceNow](https://learn.microsoft.com/microsoft-copilot-studio/customer-copilot-servicenow) | Includes a **full Escalate topic YAML** you can import | Useful pattern |
| [Customer support assistance agent](https://learn.microsoft.com/power-platform/architecture/solution-ideas/customer-support-agent) | Reference architecture, escalation analytics | Architecture |
| [Dynamics 365 US Government](https://learn.microsoft.com/power-platform/admin/microsoft-dynamics-365-government) | **Which D365 products exist in GCC / GCC High / DoD** | **Availability check** |
| [International availability of Dynamics 365 Contact Center](https://learn.microsoft.com/dynamics365/contact-center/implement/international-availability) | **GCC Moderate supported; GCC High not** | **Availability check** |
| 🔧 [**Skill Handoff sample**](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/skill-handoff) | **Working code that keeps Teams as the channel during live handoff** | **Closest reference implementation** |
| 🔧 [ServiceNow handoff sample](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/servicenow) | DirectLine relay + importable Escalate topic YAML | Adaptable pattern |
| 🔧 [Salesforce handoff sample](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/salesforce) | Einstein Bot integration via DirectLine | Adaptable pattern |
| 🎓 [**Training: Enhance Copilot Studio agents**](https://learn.microsoft.com/training/modules/enhance-power-virtual-agents-bots/) — unit [*Transfer conversations by using Omnichannel*](https://learn.microsoft.com/training/modules/enhance-power-virtual-agents-bots/3-agent-handoff) | **Guided, assessed module covering handoff configuration** | **Free hands-on training** |
| 🎓 [Training: Solution architect series — Copilot Studio in Teams](https://learn.microsoft.com/training/modules/architect-power-virtual-agents/6-pva-teams) | Architectural guidance for Teams-published agents | Design-level context |

### Option C — post to a Teams channel

| Resource | What it covers | Closeness |
|---|---|---|
| [Quickstart: create an agent and publish it to Teams](https://learn.microsoft.com/microsoft-copilot-studio/fundamentals-get-started-teams) | **"Escalate to HR experts" — builds this exact feature**, including the Power Automate flow | **Direct match** |
| [Send a message in Teams using Power Automate](https://learn.microsoft.com/power-automate/teams/send-a-message-in-teams) | Every Post as / Post in combination | **Step-by-step** |
| 🎓 [**Training: Build Power Automate flows for your agent**](https://learn.microsoft.com/training/modules/build-flows-chatbot-online-workshop/) | **Guided workshop: calling flows from topics, passing variables** | **Free hands-on training** |

> 💡 The Teams quickstart is an HR scenario that escalates to a channel — the closest
> official tutorial to anything in this document. Read it before building C or D.

### Option D — anonymous relay

| Resource | What it covers | Closeness |
|---|---|---|
| [**Send proactive Microsoft Teams messages**](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message) | **Post as agent / Chat with agent, proactive Adaptive Cards, wait-for-response, status codes** | **Closest official match — read this first** |
| [Send a message in Teams using Power Automate](https://learn.microsoft.com/power-automate/teams/send-a-message-in-teams) | Every Post as / Post in combination, incl. Flow bot | **Step-by-step** |
| [Create your first adaptive card](https://learn.microsoft.com/power-automate/create-adaptive-cards) | **Full walkthrough of post-card-and-wait, with JSON and dynamic content** | **Direct tutorial for Step D.4** |
| [Overview of adaptive cards for Power Automate](https://learn.microsoft.com/power-automate/overview-adaptive-cards) | Wait-for-response actions, update messages, known issues | **Reference + guidance** |
| [Use your prompt in Power Automate — incorporate human review](https://learn.microsoft.com/ai-builder/use-a-custom-prompt-in-flow#incorporate-human-review) | Human-in-the-loop then notify via Flow bot | Close analogue |
| [Lead collection sample](https://learn.microsoft.com/power-automate/lead-collection-sample) | **Working card with `Input.Text` fields and the resulting output tokens** | **Shows how card input reaches the flow** |
| [Differences between flow approval actions](https://learn.microsoft.com/troubleshoot/power-platform/power-automate/approvals/differences-between-flow-approval-actions#usage-examples) | Approval cards posted to Teams via the Flow bot | Alternative shape for the same idea |
| 🔧 [**Adaptive Cards Designer**](https://adaptivecards.io/designer/) | **Drag-and-drop card builder; paste the JSON from Step D.4 to edit visually** | **Use this to modify the card** |
| [**Adaptive Cards overview (Copilot Studio)**](https://learn.microsoft.com/microsoft-copilot-studio/adaptive-cards-overview) | **Host-specific schema limits — Teams caps at 1.5** — plus submit-button best practice | **Read before editing the card** |
| [Ask with Adaptive Cards](https://learn.microsoft.com/microsoft-copilot-studio/authoring-ask-with-adaptive-card) | Using an interactive card directly in a Copilot Studio topic | Alternative to the flow-based card |
| [**Request for information (RFI) action**](https://learn.microsoft.com/microsoft-copilot-studio/flows-request-for-information) | **Native pause-and-ask-a-human action with typed inputs, via Outlook** | **See [Variant D2](#-variant-d2--use-the-native-request-for-information-action-instead)** |
| [Multistage and AI approvals](https://learn.microsoft.com/microsoft-copilot-studio/flows-advanced-approvals) (preview) | Staged approval gates in agent flows | If answers ever need sign-off |
| 🔧 [Metadata update card sample](https://learn.microsoft.com/power-automate/metadata-update-sample) | Card layout for notifying a channel about a record | Layout inspiration |
| 🔧 [**Teams sample: bot-proactive-message**](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/bot-proactive-message) | **Working code for proactively messaging a Teams user** | Shows the mechanism behind Step D.6 |
| 🔧 [Teams sample: bot-cards](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/bot-cards) | Card types and actions rendered in Teams | Card behaviour reference |
| 🎓 [Training: Build Power Automate flows for your agent](https://learn.microsoft.com/training/modules/build-flows-chatbot-online-workshop/) | Guided workshop on topic → flow integration | **Free hands-on training** |
| [Trigger a cloud flow from any message in Teams](https://learn.microsoft.com/power-automate/trigger-flow-teams-message) | Recommends Flow bot for user confirmations | Supporting pattern |

✅ **Correction from an earlier draft of this document:** Microsoft *does* publish an
official guide covering most of Option D —
[Send proactive Microsoft Teams messages](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message).
It documents delivering messages and interactive Adaptive Cards **as the agent**, which is
better than the Flow bot approach. What remains uniquely this document's own is the
*composition*: using a channel card as an anonymous intake queue and relaying the human's
answer back to the original asker.

### General Copilot Studio + Power Automate

| Resource | What it covers |
|---|---|
| [Add a flow to an agent](https://learn.microsoft.com/microsoft-copilot-studio/advanced-flow) | Calling flows from topics |
| [Modify an existing flow to use with an agent](https://learn.microsoft.com/microsoft-copilot-studio/flow-modify-use-with-agent) | Required trigger/response actions; **asynchronous response must be Off** |
| [Agent flows FAQ](https://learn.microsoft.com/microsoft-copilot-studio/flows-faqs) | Confirms agent flows work in **GCC and GCC High** |
| [Variables overview](https://learn.microsoft.com/microsoft-copilot-studio/authoring-variables-about) | System variables including `User.PrincipalName` |
| [Configure user authentication](https://learn.microsoft.com/microsoft-copilot-studio/configuration-end-user-authentication) | The D365 / Authenticate-with-Microsoft conflict |

### Your own repository

| Document | Why it is relevant |
|---|---|
| `COPILOT_STUDIO_SETUP_GUIDE.md` | The click-by-click guide for the existing "Email HR" flow. **Every option here reuses the same patterns** |
| `EMAIL_HR_DEPLOYMENT_CHECKLIST.md` | Section 5 documents the authentication dependency; Section 9 shows the variable mappings |
| `CUSTOM_FEEDBACK_SETUP_GUIDE.md` | A second worked example of a Copilot Studio → flow → Function call |

> **Best preparation:** build nothing new until you have re-read
> `COPILOT_STUDIO_SETUP_GUIDE.md`. Options C and D are structurally the same as the flow you
> already have working.

### Reference implementations (working code you can read)

Documentation tells you what the buttons do. These show working solutions. All links
verified to resolve.

#### Microsoft's official Copilot Studio samples

**[microsoft/CopilotStudioSamples](https://github.com/microsoft/CopilotStudioSamples)** —
the official sample repository. The directories that matter for this document:

| Sample | What it demonstrates | Relevance |
|---|---|---|
| [**contact-center/skill-handoff**](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/skill-handoff) | Live-agent handoff **that keeps Teams as the channel**, using an Agents SDK skill + Teams proactive messaging | ⭐ **Most relevant sample in existence for your scenario** |
| [contact-center/servicenow](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/servicenow) | DirectLine relay, Azure Function bridge, importable Escalate topic YAML | Adaptable to any live-chat backend |
| [contact-center/salesforce](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/salesforce) | Einstein Bot integration via DirectLine | Adaptable pattern |
| [contact-center/genesys-handoff](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/genesys-handoff) | Live handoff to Genesys (.NET) | Adaptable pattern |
| [EmployeeSelfServiceAgent](https://github.com/microsoft/CopilotStudioSamples/tree/main/EmployeeSelfServiceAgent) | HR/employee self-service topics (Workday, Facilities) + evaluation test sets | Closest to your *agent's* subject matter |

⚠️ **Two caveats, both stated by Microsoft in the samples themselves:**
- The **skill-handoff** sample is **pro-code .NET**, and Agents SDK Skills are *"not the
  recommended long-term pattern"* — Microsoft points toward
  [multi-agent orchestration](https://learn.microsoft.com/microsoft-copilot-studio/add-agent-microsoft-365-agents-sdk-agent)
  for new work.
- **EmployeeSelfServiceAgent** is marked *"pending reorganization and will be deprecated
  from the top level in a future update."* Read it for patterns, do not depend on the path.

#### Why the skill-handoff sample matters even if you never build it

It is written by the Copilot Studio team and **independently reaches the same two
conclusions this document reached from the docs**:

1. The engagement-hub-at-the-front pattern *"doesn't work well"* with Teams — validating the
   Option B caveat in [Part B](#part-b--copilot-studio-handoff-to-dynamics-365).
2. **Teams proactive messaging** is the right way to get a human's reply back to a user in
   Teams — the same mechanism Option D uses in
   [Step D.6](#step-d6--deliver-the-answer-anonymously).

That convergence is the strongest available evidence that Option D's architecture is sound.

#### Other useful repositories and tools

| Resource | What it is | Use it for |
|---|---|---|
| [**Adaptive Cards Designer**](https://adaptivecards.io/designer/) | Live drag-and-drop card editor | Paste the [Step D.4](#step-d4--post-the-card-and-wait-for-an-answer) JSON and edit it visually |
| [Adaptive Cards schema explorer](https://adaptivecards.io/explorer/) | Every element and property | Adding fields to the card |
| [OfficeDev/Microsoft-Teams-Samples](https://github.com/OfficeDev/Microsoft-Teams-Samples) | Microsoft's Teams sample catalogue | Deep links, proactive messaging, card actions |
| [→ bot-proactive-message](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/bot-proactive-message) | Runnable proactive-messaging bot | The mechanism Option D relies on |
| [→ bot-cards](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/bot-cards) | Card types and actions in Teams | How cards actually render |
| [microsoft/Agents](https://github.com/microsoft/Agents) | Microsoft 365 Agents SDK | Only if you pursue the skill-handoff route |
| [microsoft/AdaptiveCards](https://github.com/microsoft/AdaptiveCards) | The Adaptive Cards project — schema, renderers, samples | Deeper card work than the Designer covers |
| [Copilot Studio Learning Hub](https://github.com/krazykap/copilot-studio-learning-hub) | Community-curated learning resources | Broader Copilot Studio grounding |

⚠️ **The last one is community-maintained, not Microsoft-official.** Treat it as a starting
point for further reading, not as authoritative guidance — and note the general caution in
Copilot Studio's GCC documentation about third-party content and services falling outside
the GCC compliance boundary.

#### Power CAT Copilot Agent Kit — for measuring whether this feature works

**[microsoft/Power-CAT-Copilot-Studio-Kit](https://github.com/microsoft/Power-CAT-Copilot-Studio-Kit)**
— an official Microsoft (Power CAT team) toolkit that augments Copilot Studio with testing,
governance and analytics capabilities.

| Component | What it does | Why it matters here |
|---|---|---|
| [**Agent Insights Hub**](https://github.com/microsoft/Power-CAT-Copilot-Studio-Kit/blob/main/AGENT_INSIGHTS_HUB.md) (preview) | **Aggregates telemetry from Azure Application Insights** plus conversation transcripts — KPIs, topic/tool analytics, error tracking, CSAT, Excel export | **Your Function already writes to App Insights.** A possible complement to the Power BI dashboard |
| [Testing capabilities](https://github.com/microsoft/Power-CAT-Copilot-Studio-Kit/blob/main/TESTING_CAPABILITIES.md) | Batch-test agents against test sets: response match, topic match, multi-turn, generative-answer scoring | Regression-test the new escalation topic before publishing |
| Agent Debugger | Replays a recorded conversation showing every decision, timing, tokens, knowledge sources | Diagnosing *why* the agent could not answer — the upstream cause of escalation |
| [Prerequisites](https://github.com/microsoft/Power-CAT-Copilot-Studio-Kit/blob/main/PREREQUISITES.md) · [Installation](https://github.com/microsoft/Power-CAT-Copilot-Studio-Kit/blob/main/INSTALLATION_INSTRUCTIONS.md) | Licensing, Dataverse and AI Builder credit consumption | Read before installing |

⚠️ **GCC support is not stated either way.** I checked the README and PREREQUISITES and
found **no mention of GCC, government or sovereign clouds** — that means *unverified*, not
*supported*. It is a Power Platform solution with Dataverse and AI Builder dependencies, so
confirm availability in your environment before planning around it. Treat this as a lead to
investigate, not a recommendation.

> **Why it is worth a look regardless:** this feature is only as useful as your ability to
> see whether it is working. Agent Insights Hub reads the same App Insights data your
> Function already writes, and the Agent Debugger addresses the question that matters
> long-term — *why can't the agent answer these questions in the first place?*

#### Microsoft CAT team blog — "The Custom Engine"

**[microsoft.github.io/mcscatblog](https://microsoft.github.io/mcscatblog/)** — *"Technical
examples and best practices from the Microsoft Copilot Studio CAT team."* Microsoft-authored,
more current and more candid than the formal documentation.

| Post | Why it matters | Relevance |
|---|---|---|
| [**Handing Over to Live Agents Without Losing Control**](https://microsoft.github.io/mcscatblog/posts/copilot-studio-handover-live-agent/) | The narrative companion to the skill-handoff sample. Names the failure modes of the traditional pattern: **Lost Native Channels**, **No Return Path**, **Redundant Orchestration** | ⭐ **Read before Step B.1** |
| [**Best Practices for Deploying Copilot Studio Agents in Microsoft Teams**](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment-ux/) | Teams sessions *"persist indefinitely"*, Conversation Start does not fire, and **updates can be cached so users may not get the latest version** | ⭐ **Explains the publishing lag in [Troubleshooting](#troubleshooting)** |
| [**Design Copilot Studio Agents for Teams**](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-agent-patterns/) | **Eight production patterns with ready-to-import YAML and a downloadable solution file** — re-installs, stale context, clearing history after inactivity, and improving the **On Error** topic | ⭐ **Most immediately actionable post on this list** |
| [**Building a Custom Human-in-the-Loop Experience**](https://microsoft.github.io/mcscatblog/posts/human-in-the-loop-custom-connector/) | A custom-connector sample that decouples "pause and wait for a human" from the delivery channel — see the note below | **Directly relevant to Option D at scale** |
| [Building a Live Agent Handoff Widget for ServiceNow](https://microsoft.github.io/mcscatblog/posts/servicenow-copilot-studio-widget/) | Handoff implementation for ServiceNow | If your service desk is ServiceNow |
| [Salesforce ↔ Copilot Studio handoff](https://microsoft.github.io/mcscatblog/posts/salesforce-copilot-studio-handoff/) | Handoff implementation for Salesforce | If your service desk is Salesforce |
| [From DEV to PROD: Deploying Agents to Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment/) | Environments, solutions and promotion | Moving your change to production safely |
| [Open the Hood: What Your Agent Is Really Doing](https://microsoft.github.io/mcscatblog/posts/open-the-hood-copilot-studio-transcripts/) | Reading conversation transcripts | Diagnosing why the agent could not answer |
| [The One Card: Build Once, Speak All Languages](https://microsoft.github.io/mcscatblog/posts/localize-adaptive-cards/) | Localising Adaptive Cards | Only if HR ever needs multilingual cards |

> ### ⚠️ Option D's scaling weakness, named by Microsoft
>
> The human-in-the-loop post identifies the exact limitation of the Step D.4 approach:
>
> > *"The out-of-the-box connectors that support 'pause and wait for a human' each have the
> > same limitation: **they own the delivery channel**… Dozens of requests a day across
> > multiple workflows, all landing in the same inbox or chat, with no way to prioritize or
> > batch them."*
>
> That is precisely the "channel noise" risk flagged in
> [Option D's cons](#option-d--pros-and-cons). At low volume — a handful of escalations a
> day — a Teams channel of cards is fine. If volume grows, the post's custom-connector
> pattern (any UI that can call a REST endpoint, with a prioritised queue) is the
> Microsoft-sanctioned next step. **Do not build that first**; build Option D, measure, and
> escalate the design only if the noise becomes real.

> **On "No Return Path" — a limitation this document had not named.** The CAT post points out
> that once an engagement hub takes over, *"there's no easy way to return it to your Copilot
> Studio agent. The user is stuck in the live chat experience, even for simple follow-up
> questions the agent could handle."*
>
> That is a genuine argument for Options C and D over B in your setting: the employee stays
> in the agent conversation throughout, so the next question still goes to the bot.

#### Alternate escalation paths — Microsoft's own guidance

[**Alternate escalation paths**](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-alternate-escalation-paths)
is the official guidance page closest to this document's subject. It recommends exactly the
kind of alternatives described here:

- **Check operating hours and queue size before transferring** — and if outside hours or the
  queue is full, *"redirect the user to email support or schedule a callback."*
- **Offer to create a support ticket** instead of transferring.

> Two things follow for your design:
>
> 1. Your existing **"Email HR"** option is a Microsoft-recommended escalation path, not a
>    stopgap. Keeping it alongside the new option is the documented pattern.
> 2. **Consider an operating-hours check.** Options A, C and D all silently assume someone
>    is available. A simple business-hours condition ahead of the choice — offering only
>    "Email HR" out of hours — would prevent the worst failure mode: an employee asking at
>    22:00 and hearing nothing until morning.

#### Community blog posts (not Microsoft-authored)

Useful for the fiddly mechanics of Adaptive Card responses, which the official docs cover
only briefly.

| Post | Author | Covers |
|---|---|---|
| [Register response from custom Adaptive Cards sent from Power Automate to Teams](https://poszytek.eu/en/microsoft-en/office-365-en/powerautomate-en/register-response-from-custom-adaptive-cards-sent-from-power-automate-to-teams/) | Tomasz Poszytek, **Business Applications MVP** | Capturing submitted card values — the mechanism behind [Step D.4](#step-d4--post-the-card-and-wait-for-an-answer) |
| [Copilot Studio: Create an Agent and Use Adaptive Cards](https://rajeevpentyala.com/2025/07/15/copilot-studio-create-an-agent-and-use-adaptive-cards/) | Rajeev Pentyala (Power Platform blogger) | End-to-end walkthrough of adding cards to an agent |
| [Dynamic Adaptive Cards with Copilot Studio](https://reshmeeauckloo.com/posts/copilotstudio-dynamic-adaptivecard/) | Reshmee Auckloo | Building cards whose content varies at run time |
| [jameswh3/copilot-studio-adaptive-cards](https://github.com/jameswh3/copilot-studio-adaptive-cards) | Community (GitHub) | Card samples and a guide, incl. charts |
| [Capturing Adaptive Card Responses in Teams Workflows Without a Bot](https://devopsaitoolkit.com/blog/teams-workflows-card-response-no-bot/) | Community | Card responses via Workflows rather than a custom bot |
| [Power Automate Adaptive Cards: Teams Approval Flow Guide](https://alphavima.com/blog/power-automate-teams-adaptive-card-approval/) | AlphaVima (vendor blog) | Approval-shaped card flow walkthrough |

⚠️ **These are third-party and unversioned.** They can go stale without notice, and none
address GCC. Use them to understand *mechanics*, then confirm behaviour against the official
docs cited above before relying on anything.

#### Case studies and adoption material

For building the business case rather than the feature. Useful when someone asks *"has
anyone actually done this?"*

| Resource | What it gives you |
|---|---|
| [**Deflection overview**](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-overview) | **Precise definitions of Resolution / Escalation / Abandon rate and CSAT**, plus the cost argument — see below |
| [Copilot Studio real-world transformation stories](https://learn.microsoft.com/microsoft-copilot-studio/guidance/adoption-case-studies) | Fifteen customer case studies with measurable outcomes |
| [City of Montréal enhances citizen engagement](https://learn.microsoft.com/power-platform/guidance/case-studies/city-montreal-citizen-engagement) | **Public-sector** conversational agent — closest sector match to a port authority |
| [Singapore Civil Defence Force digital solutions](https://learn.microsoft.com/power-platform/guidance/case-studies/scdf-implements-digital-solutions) | **Government agency** automating manual processes |
| [Nexi Group revolutionizes customer support](https://learn.microsoft.com/power-platform/guidance/case-studies/nexi-revolutionizes-customer-support) | Reducing contact-centre workload through deflection |
| [Copilot Agent Kit real-world examples](https://learn.microsoft.com/power-platform/guidance/case-studies/copilot-agent-kit-examples) | How organisations use the kit to monitor and refine agents |
| [HR scenario: Automate benefits query management](https://adoption.microsoft.com/en-us/scenario-library/human-resources/automate-benefits-query-management/) | Microsoft's adoption scenario for **exactly your use case** — framing and value messaging, not build steps |

> ### 📊 Numbers worth having in your back pocket
>
> The [Deflection overview](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-overview)
> defines the metrics precisely — worth adopting rather than inventing your own:
>
> | Metric | Definition |
> |---|---|
> | **Engagement Rate** | % of sessions where a custom topic triggered **or the session ended in escalation** |
> | **Resolution Rate** | % of engaged sessions where the user confirmed (or didn't dispute) the answer |
> | **Escalation Rate** | % of engaged sessions escalated to a human |
> | **Abandon Rate** | % of engaged sessions neither resolved nor escalated **after one hour** |
>
> And the cost framing:
>
> > *"Human representative call support typically costs around **$5 to $10**… while an agent
> > session that resolves a customer request costs about **50 cents**."*
>
> ⚠️ **Use that comparison carefully in your context.** Those are contact-centre industry
> figures, and your agent deflects *internal HR questions*, not external support calls. The
> shape of the argument holds; the specific numbers are not yours. Also note that **abandon
> rate is a one-hour measure** — which is a fair yardstick for Options A and D, and clearly
> unfair to Option C, where nobody claims to respond within the hour.

#### Free hands-on training (Microsoft Learn)

These are guided, assessed modules — closer to a workshop than documentation. All free.

| Module | Covers | Relevant to |
|---|---|---|
| [**Enhance Copilot Studio agents**](https://learn.microsoft.com/training/modules/enhance-power-virtual-agents-bots/) | Calling Power Automate from topics; **[transferring conversations to Omnichannel](https://learn.microsoft.com/training/modules/enhance-power-virtual-agents-bots/3-agent-handoff)**; analysing agent performance | **Options B, C, D** |
| [**Build Power Automate flows for your agent**](https://learn.microsoft.com/training/modules/build-flows-chatbot-online-workshop/) | Topic → flow integration, passing variables, HTTP nodes | **Options C and D** |
| [Solution architect series: Explore Copilot Studio](https://learn.microsoft.com/training/modules/architect-power-virtual-agents/) — incl. [Copilot Studio in Teams](https://learn.microsoft.com/training/modules/architect-power-virtual-agents/6-pva-teams) | Design-level guidance for Teams-published agents | Deciding between options |
| [Build an autonomous agent in Copilot Studio](https://learn.microsoft.com/training/modules/autonomous-agent/) | Triggers, actions, publishing to Teams | Background, not directly used here |

> **If you only do one:** the *Transfer conversations by using Omnichannel* unit in
> **Enhance Copilot Studio agents**. It is the only guided, assessed walkthrough of handoff
> configuration Microsoft publishes, and it will materially de-risk
> [Step B.1](#step-b1--prove-it-works-before-you-commit).

⚠️ **Training modules assume a commercial tenant.** Exercises reference
`copilotstudio.microsoft.com` and `make.powerautomate.com`. Substitute your GCC addresses
(`gcc.powerva.microsoft.us`, `gov.flow.microsoft.us`) throughout, and expect some
screenshots not to match.

#### Architecture guidance and reference solutions

Design-level material. Useful for justifying the decision to stakeholders, not for
click-by-click build steps.

| Resource | What it gives you |
|---|---|
| [**Improve the new hire experience with a smart onboarding agent**](https://learn.microsoft.com/power-platform/architecture/solution-ideas/onboarding-agent) | **An HR-agent reference architecture** with an explicit Responsible AI section — see the quote below |
| [**Pattern: Workplace and IT services**](https://learn.microsoft.com/agents/adoption-patterns/pattern-workplace-it-services) | Adoption pattern for HR/IT service agents; a *"Keep a human in control"* section naming escalation and handoff as first-class capabilities |
| [Customer support assistance agent](https://learn.microsoft.com/power-platform/architecture/solution-ideas/customer-support-agent) | Reference architecture for deflection + escalation, incl. analytics |
| [Escalation and handoff overview](https://learn.microsoft.com/microsoft-copilot-studio/customer-copilot-overview) | Microsoft's umbrella page for the whole escalation capability area |
| [Copilot Studio guidance hub](https://learn.microsoft.com/microsoft-copilot-studio/guidance) | Entry point for all official design guidance |
| [Power Platform Well-Architected](https://learn.microsoft.com/power-platform/well-architected) | Reliability, security and operational-excellence framing |
| [**Deflection and escalation analysis**](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-topic-escalation-analysis) | **How to measure whether this feature is working** — pairs with the telemetry section below |
| [Human-in-the-loop approvals in flows](https://learn.microsoft.com/microsoft-copilot-studio/flows-request-for-information) | The supported pattern for pausing a flow for human input |

> ### 📌 Two points from the onboarding-agent architecture worth quoting
>
> Microsoft's HR-agent reference architecture makes two statements that bear directly on
> every option in this document:
>
> **On escalation being mandatory, not optional:**
> > *"**Human-in-the-loop**: Onboarding can often involve sensitive questions. Review
> > onboarding solutions to ensure that adequate escalation to a human is implemented."*
>
> Benefits questions are at least as sensitive as onboarding questions. This is Microsoft
> treating the feature you are building as a **requirement** of a responsible HR agent —
> useful if anyone frames it as a nice-to-have.
>
> **On disclosing who is answering:**
> > *"Agents should make clear when the user is interacting with an agent and when they're
> > receiving a response from a human."*
>
> ⚠️ **This has a direct bearing on the anonymity design.** Hiding the *identity* of the
> responder is legitimate; hiding the *fact that a human answered* is not. If you use
> **Post as → Microsoft Copilot Studio agent** in
> [Step D.6](#step-d6--deliver-the-answer-anonymously), the reply looks like it came from
> the bot — so the message text **must** say a person wrote it. The wording already
> recommended (*"HR has answered your question:"*) satisfies this. Do not soften it.

---

## Questions you are likely to be asked

Collected from the concerns that typically surface when this feature is proposed.

### Cost and licensing

**Q: Which options cost money?**
Only B is certain to. B needs a Dynamics 365 Customer Service or Contact Center licence
*per representative*. A needs nothing. C and D use the **standard** Teams connector and may
need no new licence — see [A note on Power Automate licensing](#a-note-on-power-automate-licensing)
and verify rather than assume.

**Q: Do we need Power Automate Premium for C and D?**
**Probably not — but verify rather than assume.** The distinction is which *connector* an
action belongs to:

| Feature | Action used | Connector tier |
|---|---|---|
| `send_hr_email` (existing) | **HTTP** | **Premium** |
| Option C | Post message in a chat or channel | **Standard** (Teams) |
| Option D | Post adaptive card + wait; Post message | **Standard** (Teams) |
| Variant D2 | Request for information | Part of agent flows — see below |

So C and D may need **no new licence at all**, which is a better position than this document
originally implied.

⚠️ **Two things to check before relying on that:**

1. **Does the flow-running account already have Premium?** `COPILOT_STUDIO_SETUP_GUIDE.md`
   lists it as a *prerequisite to obtain* for the email feature — it does not confirm it was
   granted. If the email feature works today, someone has it; confirm who.
2. **Agent flows bill differently.** Microsoft's
   [Agent flows FAQ](https://learn.microsoft.com/microsoft-copilot-studio/flows-faqs) states
   agent flows are *"billed in Copilot Studio based on usage"* and are *"not included
   entitlements in Power Automate"* — a separate consideration from connector tiers.

**How to check in 30 seconds:** open the flow designer and look for a **Premium** badge on
the actions you plan to use. No badge means no premium licence needed for that action.

**Q: Is there a per-message cost?**
Copilot Studio bills by message/session depending on your plan. Options C and D add *flow
runs*, not agent messages. Volume is bounded by how often the agent fails to answer —
today, a small fraction of conversations.

### Security and compliance

**Q: Does this send data outside our tenant?**
No. All four options stay inside Microsoft 365/Power Platform in your GCC tenant. No
third-party service is introduced.

⚠️ One caveat worth reading: the Copilot Studio GCC documentation notes that Power Automate
connectors *can* reach third-party services outside the GCC compliance boundary. The Teams
and Office 365 connectors used here do not, but your Power Platform DLP policy should
enforce that generally.

**Q: Is this FedRAMP compliant?**
Copilot Studio GCC complies with FedRAMP High. Options A, C and D add no new service.
Option B adds Dynamics 365 — confirm its authorisation separately with your compliance
team.

**Q: Is Dynamics 365 Contact Center even available in GCC?**
Yes — verified. **Dynamics 365 Contact Center** and **Customer Service** are both listed as
available in GCC, and Contact Center digital channels are supported in **GCC Moderate**
(they are *not* available in GCC High or DoD). Purchase via Volume Licensing or CSP. One
caveat: if you later add the **voice** channel, Azure Communication Services for voice
*"continue to run in North America Commercial Cloud"* — raise that with compliance before
committing to voice.

**Q: Can we audit who answered what?**
Yes. Teams messages are retained and discoverable; Power Automate run history shows which
account submitted each card. **Anonymity is from the employee, not from compliance.**

**Q: What about eDiscovery and retention?**
Normal Teams and Exchange policies apply. Option A's chats live in personal chat history;
C and D live in the HR channel, plus the employee's agent chat (or Flow bot chat, depending
on the [Step D.6](#step-d6--deliver-the-answer-anonymously) delivery method). Variant D2
adds Outlook, since RFI requests are emailed.

**Q: Could an employee accidentally send PII to the wrong place?**
The question text goes only where you configure. Note the question is *already* being sent
to HR by email today, so this introduces no new exposure.

### Anonymity

**Q: How anonymous is "anonymous"?**
See [Anonymity — what it does and does not protect](#anonymity--what-it-does-and-does-not-protect).
Short version: hidden from the employee, fully visible to administrators and compliance.

**Q: Can a rep be identified from writing style?**
In a small team, yes. Anonymity here prevents casual identification, not determined
analysis.

**Q: What if a rep signs their name?**
Anonymity is lost for that exchange. This is the single most likely failure mode, which is
why [Step D.9](#step-d9--brief-the-representatives) exists.

**Q: Should employees be told answers come from a real person?**
Yes. Say *"answered by a member of the HR benefits team; individual responders are not
identified."* Implying a bot wrote it would be misleading.

### Operations and staffing

**Q: How fast will employees get an answer?**

| Option | Realistic |
|---|---|
| A | Minutes to hours, depending on who is online |
| B | Seconds — if staffed |
| C | Hours to days — no closed loop |
| D | Minutes to hours, with an explicit timeout |

**Q: What if nobody answers?**
A and C: nothing happens; the request is silently dropped. **D handles this explicitly** via
the timeout branch. B has SLA and overflow rules. This is a genuine advantage of D over A
and C.

**Q: Do we need dedicated staff?**
Only B implies a rostered queue. A, C and D fit existing HR workload.

**Q: What if volume is much higher than expected?**
Watch the `canAnswer = false` rate in Power BI *before* building. If escalations are more
than a handful a day, A and C will overwhelm a shared inbox and you should look at B.

**Q: Can we start small and change later?**
Yes, and you should. All options attach to the same decision point in one topic. Swapping A
for D later is an afternoon's work.

### Technical

**Q: Does this require changing the Azure Function?**
No. All four options are configuration-only. The optional telemetry event is the only code
change, and it is not required for the feature to work.

**Q: Will this break the existing "Email HR" feature?**
Not for A, C or D — they add a branch beside it. **Option B might**, because of the
authentication conflict described in
[Your scenario](#your-scenario--verified-facts-this-document-assumes).

**Q: What happens if the flow fails?**
The user sees a generic Copilot Studio error. Add a fallback message so they are told to
use "Email HR" instead.

**Q: Why respond to the agent before doing the work? That seems backwards.**
Because an agent flow must answer within **100 seconds** or fail with `FlowActionTimedOut`,
and a human will not answer that fast. Microsoft explicitly supports this pattern: actions
placed after **Respond to the agent** keep running for up to 30 days. You are acknowledging
receipt, not reporting completion.

**Q: I heard flows can now run asynchronously — is the respond-first pattern obsolete?**
Possibly, for you. Microsoft added
[asynchronous response support for agent flows](https://learn.microsoft.com/microsoft-copilot-studio/flow-asynchronous-response),
and the callback is *fully supported in Teams*. It would let the flow return its result as a
normal agent response instead of a separate proactive message. But it requires an environment
on the new Power Automate infrastructure. Check for the **Asynchronous response** toggle
before relying on it. The respond-first pattern works either way.

> Note that you do **not** need async to get the answer into the agent chat — **Post as →
> Microsoft Copilot Studio agent** already achieves that
> ([Step D.6](#step-d6--deliver-the-answer-anonymously)). Async would simply remove the need
> for the separate proactive-message step.

**Q: Can we offer several options at once?**
Yes — add more choices to the same Question node. But every extra choice is a decision the
user must make while already frustrated. Two is usually right.

**Q: How do we test without bothering HR?**
Point the reps list (A), the channel (C/D), or the queue (B) at yourself and a colleague
first. Only switch to real HR addresses after the end-to-end test passes.

**Q: Will this work on Teams mobile?**
Yes for all four. Deep links, Adaptive Cards and Flow bot messages all render on mobile.
Test it anyway — long answers in cards are cramped on a phone.

**Q: Can the answer come back from the agent instead of some other bot?**
Yes, and it should. Use **Post as → Microsoft Copilot Studio agent** with
**Post in → Chat with agent**. This is Microsoft's documented
[proactive message](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message)
pattern. The reply lands in the chat the employee already has open. The one prerequisite is
that the employee has the agent installed — true by definition here, since they just used it.

**Q: Why do escalations not show up in Copilot Studio analytics?**
Because *"proactive messages don't appear in conversation transcripts or analytics session
data."* This is documented behaviour, not a bug — and it is the main reason to add the
telemetry event below, so escalations remain visible in your Power BI dashboard.

### Measurement

**Q: How do we know if it is being used?**
Add the `RepresentativeRequested` event
([Optional — telemetry](#optional--add-telemetry-so-power-bi-stays-complete)) so escalations
appear in the same Power BI dashboard as `EmailSent` and `AgentInteractionFailed`.

**Q: How do we know it is working *well*?**
Track: escalations per week, **Escalation Rate** (% of *engaged sessions* escalated — use
[Microsoft's definitions](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-overview)
rather than inventing your own), time to answer (Option D, from flow run history), and
timeout rate. A rising escalation rate usually means the knowledge base needs updating —
which is more valuable than any of these options.

> Microsoft publishes guidance on exactly this measurement problem:
> [Deflection and escalation analysis](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-topic-escalation-analysis).
> It explains the built-in **Escalation Rate Drivers** view, which shows *which topics*
> escalate most and why — the fastest route from "people keep escalating" to "here is the
> knowledge gap to fix."
>
> ⚠️ Remember that **Options A and D are partly invisible to those built-in analytics** — a
> deep link is just a message, and proactive messages are excluded from session data. Your
> own telemetry event is what keeps the picture complete.

---

## Optional — Add telemetry so Power BI stays complete

Whichever option you pick, consider recording that a representative was requested. Without
it, your Power BI dashboard shows failed answers and emails sent — but escalations become
invisible, and the deflection analysis silently understates demand.

⚠️ **For Option D this is close to mandatory.** Microsoft documents that *"proactive
messages don't appear in conversation transcripts or analytics session data."* So the
answer delivered back to the employee leaves **no trace** in Copilot Studio analytics. If
you do not emit your own event, the entire escalation path is invisible to reporting.

> **Alternative worth evaluating:** the
> [Power CAT Agent Insights Hub](https://github.com/microsoft/Power-CAT-Copilot-Studio-Kit/blob/main/AGENT_INSIGHTS_HUB.md)
> aggregates App Insights telemetry and conversation transcripts into a prebuilt dashboard.
> Since your Function already writes to App Insights, it may give you much of the Power BI
> dashboard's value without building one — **if** it is available in GCC, which is
> unverified. See
> [Power CAT Copilot Agent Kit](#power-cat-copilot-agent-kit--for-measuring-whether-this-feature-works).

### Two ways to do it

| Approach | Effort | Where it lands |
|---|---|---|
| **From Power Automate** | Low — no code change | Only works if a flow is involved (Options C and D) |
| **From the Function** | Small code change | Consistent with the five existing events |

Since Option A involves **no flow at all**, only the Function approach covers every option
consistently.

### What the event should look like

The Function already has a `track_event()` helper. A new event would follow the existing
pattern of the other five:

| Dimension | Value |
|---|---|
| `agentLabel` | The caller-supplied display name |
| `question` | The question that could not be answered (truncated) |
| `conversationId` | Join key to `AgentInteraction` |
| `userId`, `userName` | Who asked |
| `method` | `deeplink`, `d365`, `channel`, or `relay` |

⚠️ **Two behaviours of the existing telemetry code to be aware of:**

1. `track_event()` **merges measurements into `customDimensions`**, so `customMeasurements`
   is always empty. Every KQL query must read from `customDimensions`.
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

> This is deliberately **not implemented yet** — it is a separate decision. Say the word and
> it can be added to `function_app.py` along with the matching documentation updates.

---

## Troubleshooting

### Option A

| Symptom | Cause | Fix |
|---|---|---|
| Link does nothing | Teams not installed, or browser blocked the protocol | Test in Teams web; allow the site to open Teams |
| "We couldn't find that person" | Wrong address, or not a real user account | Use individual UPNs — not distribution lists or shared mailboxes |
| Chat opens but is empty | Missing `message` parameter | Check `EncodeUrl(...)` is present in the formula |
| Question is cut off at the first space | `EncodeUrl` omitted | Add `EncodeUrl(...)` around the question variable |
| Chat has no title | Fewer than 3 participants | Expected — `topicName` needs 3+ people. Add another rep |
| Message never arrives | User did not press Send | Add the "just press Send" instruction ([Step A.6](#step-a6--show-the-link-to-the-user)) |
| Opens an old chat | A chat with those exact people exists | Expected behaviour |
| Link broken by an apostrophe | `EncodeUrl` omitted | Same fix — this is why it is mandatory |

### Option B

| Symptom | Cause | Fix |
|---|---|---|
| "No renderer for this activity" | Canvas cannot render handoff | Confirms the Step B.1 risk — the channel does not support it |
| Error `1004 DuplicateBotAppId` | Application ID reused | Create a new, unique app registration |
| Handoff works in test, not on a website | Wrong embed code | Use the D365 chat widget embed code, not Copilot Studio's |
| Analytics missing | Agent and D365 in different environments | Move them into the same environment |
| Conversation ends instead of transferring | Escalate ends conversations on some channels | Re-run Step B.1 and reconsider |

### Option C

| Symptom | Cause | Fix |
|---|---|---|
| Flow not listed in Copilot Studio | Page not reloaded | Reload the Copilot Studio tab |
| Flow shows a **Premium** badge | Missing licence | Request Power Automate Premium |
| Flow fails with 401/403 | Teams connection not authorised | Re-authenticate the Teams connector |
| Posts to the wrong channel | Team/Channel misselected | Recheck the action's fields |
| Blank name or email | Wrong system variables, or agent not authenticated | Use `System.User.DisplayName` / `System.User.PrincipalName`; confirm **Authenticate with Microsoft** is on |

### Option D

| Symptom | Cause | Fix |
|---|---|---|
| Agent shows an error, or hangs, then fails | The waiting step runs **before** the response | Move **Respond to the agent** directly after the trigger ([Step D.3](#step-d3--respond-to-the-agent-first)) |
| `FlowActionTimedOut` | Flow took over 100 seconds to respond | Same fix — respond first, wait afterwards |
| Card posts, but buttons error | Used the plain "post" action | Use **"...and wait for a response"** |
| Employee sees a person's name as sender | **Post as** set to `User` | Set **Post as** to `Microsoft Copilot Studio agent` or `Flow bot` ([Step D.6](#step-d6--deliver-the-answer-anonymously)) |
| Answer never arrives; status `100` | Employee has not installed / has removed the agent | Use the Flow bot fallback, or ensure the agent is installed and shared |
| Answer never arrives; status `300` | Employee is in an active chat with the agent | Set **If the chat with the agent is active** to **Send** |
| Escalations missing from analytics | Proactive messages are excluded from transcripts and session data | Expected — add the telemetry event below |
| Card never appears | Private channel | Use a **standard** channel ([Step D.1](#step-d1--create-the-hr-intake-channel)) |
| Card looks unanswered after submitting | **Update message** not configured | Set **Update message** ([Step D.4](#step-d4--post-the-card-and-wait-for-an-answer)) |
| Two reps answer the same question | First response wins; card reset | Configure the update message; brief the team |
| Employee never receives the answer | Looking in the wrong chat | Depends on your [Step D.6](#step-d6--deliver-the-answer-anonymously) choice: **Post as agent** → the reply is in the **agent chat**; **Flow bot** fallback → it is in a separate **Flow bot** chat. Make the topic's confirmation message say which |
| `OperationTimedOut` | Nobody answered | Expected — add the timeout branch ([Step D.5](#step-d5--add-a-timeout-path)) |
| Question text empty on the card | Hand-typed `triggerBody()` | Re-insert via the lightning bolt icon |
| Rep's name appears in the answer | The rep signed it | Brief them ([Step D.9](#step-d9--brief-the-representatives)) |
| `FlowActionBadRequest` in Teams | Flow inputs/outputs changed without refreshing | Reload Copilot Studio, re-map the inputs, republish the agent |
| `Error code: 3000` | Asynchronous response is On | Response action → **Settings** → **Asynchronous response** → **Off** |

### All options

| Symptom | Cause | Fix |
|---|---|---|
| New option not visible in Teams | Teams cached the old agent | Republish; or in Teams admin center disable and re-enable the app; or toggle the Teams channel off and on in Copilot Studio |
| Users still on an old version after publishing | **Teams caches agent updates**, and sessions *"persist indefinitely"* | Documented by the Copilot Studio CAT team in [Best Practices for Deploying Agents in Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment-ux/) — read it before blaming your topic |
| `SystemError` in Teams | Teams using a stale published version | Same as above |
| Changes not appearing | Saved but not published | Click **Publish**, not just **Save** |
| Users confused by stale context or empty chat after reinstall | Teams conversations persist for months; Conversation Start does not re-fire | **Ready-to-import fixes:** [Design Copilot Studio Agents for Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-agent-patterns/) ships eight patterns with YAML and a downloadable solution |

---

## Glossary

| Term | Meaning |
|---|---|
| **Adaptive Card** | A JSON-defined interactive block that renders natively in Teams |
| **Agent** | Two meanings. *AI agent* = the bot. *Live agent* = a human. Microsoft's docs use both |
| **Canvas** | The visual chat window. Teams, a website widget, and the test pane are different canvases |
| **Channel** (Copilot Studio) | Where an agent is published — Teams, a website, etc. |
| **Channel** (Teams) | A named section inside a team |
| **Deep link** | A URL that makes Teams perform an action instead of opening a web page |
| **Deflection** | The agent answering without escalating. Higher is better |
| **Engagement hub** | A contact-centre product (e.g. Dynamics 365) where humans handle conversations |
| **Environment** | A Power Platform container. Agents and flows must be in the same one to see each other |
| **Escalate** | The system topic that runs when a user asks for a human |
| **Fallback** | The system topic when the agent cannot match a question. Redirects to Escalate after two attempts |
| **Flow bot** | The generic bot identity Power Automate uses to post messages not tied to any person |
| **GCC** | Government Community Cloud. **Not** the same as GCC High |
| **ISO 8601 duration** | A timeout format. `PT8H` = 8 hours, `PT5M` = 5 minutes |
| **Maker** | Someone permitted to build agents and flows |
| **Nickname** | The Omnichannel user-record field D365 shows instead of a real name when anonymising |
| **Power Fx** | The formula language in Copilot Studio (similar to Excel formulas) |
| **System topic** | A built-in topic like Escalate, Fallback or Greeting. Can be edited, not deleted |
| **Topic** | A conversation script |
| **UPN** | User Principal Name — usually the sign-in email address |
| **URL encoding** | Replacing unsafe characters (space → `%20`) so they survive in a web address |

---

## Sources

Verified against Microsoft Learn:

- [Hand off to a live agent](https://learn.microsoft.com/microsoft-copilot-studio/advanced-hand-off) — Escalate topic, Transfer conversation node, `va_*` context variables
- [Copilot Studio for US Government customers](https://learn.microsoft.com/microsoft-copilot-studio/requirements-licensing-gcc) — GCC vs GCC High feature matrix
- [Publish agents to channels and clients](https://learn.microsoft.com/microsoft-copilot-studio/guidance/channels) — Bot-as-Agent vs Bot-in-the-Loop patterns
- [Configure handoff to Dynamics 365 Customer Service](https://learn.microsoft.com/microsoft-copilot-studio/configuration-hand-off-omnichannel) — connection steps, `DuplicateBotAppId`
- [Deep link to Teams chat](https://learn.microsoft.com/microsoftteams/platform/concepts/build-and-test/deep-link-teams) — deep link format and behaviour
- [Plan for sovereign clouds](https://learn.microsoft.com/microsoftteams/platform/concepts/sovereign-cloud) — GCC uses `teams.microsoft.com`
- [Plan for government clouds](https://learn.microsoft.com/microsoftteams/platform/concepts/cloud-overview) — Teams capabilities by government cloud
- [Use system topics](https://learn.microsoft.com/microsoft-copilot-studio/authoring-system-topics) — Escalate and Fallback behaviour
- [Connect and configure an agent for Teams](https://learn.microsoft.com/microsoft-copilot-studio/publication-add-bot-to-microsoft-teams) — known limitations, `SystemError` workaround
- [Create chat](https://learn.microsoft.com/graph/api/chat-post) / [Send message in a chat](https://learn.microsoft.com/graph/api/chat-post-messages) — app-only permission limits
- [ACS support for government clouds](https://learn.microsoft.com/azure/communication-services/concepts/interop/teams-user/government-cloud) — GCC interop unsupported
- [Quickstart: classic agent published to Teams](https://learn.microsoft.com/microsoft-copilot-studio/fundamentals-get-started-teams) — the channel-post escalation pattern
- [Configure agent display name](https://learn.microsoft.com/dynamics365/customer-service/administer/agent-display-name) — D365 nickname anonymisation and its two leaks
- [Send a message in Teams using Power Automate](https://learn.microsoft.com/power-automate/teams/send-a-message-in-teams) — Post as Flow bot / Copilot Studio agent; Chat with Flow bot
- [Overview of adaptive cards for Microsoft Teams](https://learn.microsoft.com/power-automate/overview-adaptive-cards) — wait-for-response actions, single-submit limit, DoD exclusion
- [Limits of automated, scheduled, and instant flows](https://learn.microsoft.com/power-automate/limits-and-config) — general 120-second synchronous limit, 30-day run duration
- [Create an agent flow as a tool](https://learn.microsoft.com/microsoft-copilot-studio/advanced-flow-create) — **100-second agent-flow limit**; actions after the response run up to 30 days
- [Asynchronous response support for agent flows](https://learn.microsoft.com/microsoft-copilot-studio/flow-asynchronous-response) — newer callback capability; Teams supported; needs new infrastructure
- [Understand error codes](https://learn.microsoft.com/troubleshoot/power-platform/copilot-studio/authoring/error-codes) — `FlowActionTimedOut`, `3000`, `3002`, `SystemError`
- [Send proactive Microsoft Teams messages](https://learn.microsoft.com/microsoft-copilot-studio/advanced-proactive-message) — **Post as agent / Chat with agent**; prerequisites; status codes `200`/`100`/`300`; proactive messages excluded from transcripts and analytics
- [Create your first adaptive card](https://learn.microsoft.com/power-automate/create-adaptive-cards) — end-to-end post-card-and-wait tutorial
- [Create expressions using Power Fx](https://learn.microsoft.com/microsoft-copilot-studio/advanced-power-fx) — `System.` / `Topic.` / `Global.` prefixes; comma parameter separators
- [Format your agent messages](https://learn.microsoft.com/microsoftteams/platform/bots/how-to/format-your-bot-messages#format-text-content) — Teams Markdown subset; hyperlinks supported, headers and lists not
- [Lead collection sample](https://learn.microsoft.com/power-automate/lead-collection-sample) — `Input.Text` `id` becomes the dynamic-content output token
- [Publish agents to channels and clients — channel experience table](https://learn.microsoft.com/microsoft-copilot-studio/publication-fundamentals-publish-channels#channel-experience-reference-table) — Teams Markdown "partially supported"; multiple-choice limited to six options
- [Copilot Studio US Government service URLs](https://learn.microsoft.com/microsoft-copilot-studio/requirements-licensing-gcc#microsoft-copilot-studio-us-government-service-urls) — **authoritative GCC portal addresses** (`gcc.powerva.microsoft.us`, `gov.flow.microsoft.us`)
- [Dynamics 365 US Government](https://learn.microsoft.com/power-platform/admin/microsoft-dynamics-365-government) — Customer Service and Contact Center availability by government cloud
- [International availability of Dynamics 365 Contact Center](https://learn.microsoft.com/dynamics365/contact-center/implement/international-availability) — GCC Moderate digital + voice supported; GCC High unsupported

**Reference implementations (verified to resolve):**

- [microsoft/CopilotStudioSamples](https://github.com/microsoft/CopilotStudioSamples) — official Copilot Studio sample repository
- [contact-center/skill-handoff](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/skill-handoff) — **live handoff that keeps Teams as the channel**; confirms the engagement-hub pattern *"doesn't work well"* with Teams; uses Teams proactive messaging for agent replies
- [contact-center/servicenow](https://github.com/microsoft/CopilotStudioSamples/tree/main/contact-center/servicenow) — DirectLine relay and importable Escalate topic YAML
- [EmployeeSelfServiceAgent](https://github.com/microsoft/CopilotStudioSamples/tree/main/EmployeeSelfServiceAgent) — HR self-service topics (marked pending deprecation)
- [Adaptive Cards Designer](https://adaptivecards.io/designer/) — visual editor for the Step D.4 card
- [OfficeDev/Microsoft-Teams-Samples](https://github.com/OfficeDev/Microsoft-Teams-Samples) — Teams sample catalogue
- [Teams sample: bot-proactive-message](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/bot-proactive-message) — runnable proactive-messaging bot
- [Teams sample: bot-cards](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/bot-cards) — card types and actions in Teams
- [microsoft/Power-CAT-Copilot-Studio-Kit](https://github.com/microsoft/Power-CAT-Copilot-Studio-Kit) — official Power CAT toolkit: Agent Insights Hub (App Insights analytics), batch testing, Agent Debugger. **GCC support unverified**
- [microsoft/AdaptiveCards](https://github.com/microsoft/AdaptiveCards) — Adaptive Cards schema, renderers and samples

**Free hands-on training (verified to resolve):**

- [Enhance Copilot Studio agents](https://learn.microsoft.com/training/modules/enhance-power-virtual-agents-bots/) — includes [Transfer conversations by using Omnichannel](https://learn.microsoft.com/training/modules/enhance-power-virtual-agents-bots/3-agent-handoff)
- [Build Power Automate flows for your agent](https://learn.microsoft.com/training/modules/build-flows-chatbot-online-workshop/) — topic → flow integration workshop
- [Solution architect series: Explore Copilot Studio](https://learn.microsoft.com/training/modules/architect-power-virtual-agents/) — design-level guidance incl. Teams channel
- [Build an autonomous agent in Copilot Studio](https://learn.microsoft.com/training/modules/autonomous-agent/) — triggers, actions, publishing to Teams

**Architecture guidance (verified to resolve):**

- [Improve the new hire experience with a smart onboarding agent](https://learn.microsoft.com/power-platform/architecture/solution-ideas/onboarding-agent) — **HR agent reference architecture; Responsible AI section requiring escalation and human-vs-agent disclosure**
- [Pattern: Workplace and IT services](https://learn.microsoft.com/agents/adoption-patterns/pattern-workplace-it-services) — adoption pattern with a "Keep a human in control" section
- [Escalation and handoff overview](https://learn.microsoft.com/microsoft-copilot-studio/customer-copilot-overview) — umbrella page for the escalation capability area
- [Deflection and escalation analysis](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-topic-escalation-analysis) — Escalation Rate Drivers; measuring whether the feature works
- [Copilot Studio guidance hub](https://learn.microsoft.com/microsoft-copilot-studio/guidance) — entry point for official design guidance
- [Power Platform Well-Architected](https://learn.microsoft.com/power-platform/well-architected) — reliability and operational-excellence framing
- [Human-in-the-loop approvals in flows](https://learn.microsoft.com/microsoft-copilot-studio/flows-request-for-information) — **Request for information action: pauses a flow, emails reviewers via Outlook only, first response wins, cannot reach users outside the tenant**
- [Multistage and AI approvals in agent flows](https://learn.microsoft.com/microsoft-copilot-studio/flows-advanced-approvals) — staged approval gates (preview)
- [Agent flows overview](https://learn.microsoft.com/microsoft-copilot-studio/flows-overview) — agent flows vs workflows
- [Alternate escalation paths](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-alternate-escalation-paths) — **operating-hours and queue-size checks; email and ticket fallbacks**
- [Deflection overview](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-overview) — **official definitions of Engagement / Resolution / Escalation / Abandon rate; agent-vs-human cost comparison**
- [Copilot Studio real-world transformation stories](https://learn.microsoft.com/microsoft-copilot-studio/guidance/adoption-case-studies) — fifteen customer case studies
- [City of Montréal citizen engagement](https://learn.microsoft.com/power-platform/guidance/case-studies/city-montreal-citizen-engagement) — public-sector conversational agent
- [Singapore Civil Defence Force](https://learn.microsoft.com/power-platform/guidance/case-studies/scdf-implements-digital-solutions) — government agency automation
- [HR scenario: Automate benefits query management](https://adoption.microsoft.com/en-us/scenario-library/human-resources/automate-benefits-query-management/) — Microsoft adoption scenario for this exact use case
- [Ask with Adaptive Cards](https://learn.microsoft.com/microsoft-copilot-studio/authoring-ask-with-adaptive-card) — using Adaptive Cards directly in a Copilot Studio topic
- [Adaptive Cards overview (Copilot Studio)](https://learn.microsoft.com/microsoft-copilot-studio/adaptive-cards-overview) — **Teams caps schema at 1.5**; unique submit-action data for consecutive cards
- [adaptivecards.microsoft.com](https://adaptivecards.microsoft.com/) — schema documentation and samples

**Blog posts:**

- [The Custom Engine](https://microsoft.github.io/mcscatblog/) — Microsoft Copilot Studio **CAT team** blog
- [Handing Over to Live Agents Without Losing Control](https://microsoft.github.io/mcscatblog/posts/copilot-studio-handover-live-agent/) — Lost Native Channels, **No Return Path**, Redundant Orchestration
- [Best Practices for Deploying Copilot Studio Agents in Microsoft Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment-ux/) — session persistence, update caching
- [Design Copilot Studio Agents for Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-agent-patterns/) — **eight production patterns with importable YAML and a solution file**
- [Building a Custom Human-in-the-Loop Experience](https://microsoft.github.io/mcscatblog/posts/human-in-the-loop-custom-connector/) — **built-in connectors "own the delivery channel"; custom-connector alternative at scale**
- [Building a Live Agent Handoff Widget for ServiceNow](https://microsoft.github.io/mcscatblog/posts/servicenow-copilot-studio-widget/) — ServiceNow handoff implementation
- [Salesforce ↔ Copilot Studio handoff](https://microsoft.github.io/mcscatblog/posts/salesforce-copilot-studio-handoff/) — Salesforce handoff implementation
- [From DEV to PROD: Deploying Agents to Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment/) — environments, solutions, promotion
- [Open the Hood: What Your Agent Is Really Doing](https://microsoft.github.io/mcscatblog/posts/open-the-hood-copilot-studio-transcripts/) — reading conversation transcripts
- [The One Card: Build Once, Speak All Languages](https://microsoft.github.io/mcscatblog/posts/localize-adaptive-cards/) — localising Adaptive Cards
- [Register response from custom Adaptive Cards (Tomasz Poszytek, MVP)](https://poszytek.eu/en/microsoft-en/office-365-en/powerautomate-en/register-response-from-custom-adaptive-cards-sent-from-power-automate-to-teams/) — community; capturing card submissions
- [Capturing Adaptive Card Responses in Teams Workflows Without a Bot](https://devopsaitoolkit.com/blog/teams-workflows-card-response-no-bot/) — community
- [Power Automate Adaptive Cards: Teams Approval Flow Guide](https://alphavima.com/blog/power-automate-teams-adaptive-card-approval/) — vendor blog
- [Cloud flow error code reference](https://learn.microsoft.com/power-automate/error-reference) — `ActionTimedOut`, `OperationTimedOut`, timeout branches
- [Create a shared mailbox](https://learn.microsoft.com/microsoft-365/admin/email/create-a-shared-mailbox) — Send As vs Send on Behalf for anonymised email replies
- [Create and send messages (Teams webhooks)](https://learn.microsoft.com/microsoftteams/platform/webhooks-and-connectors/how-to/connectors-using) — Flow bot unsupported in private channels
- [Configure user authentication in Copilot Studio](https://learn.microsoft.com/microsoft-copilot-studio/configuration-end-user-authentication) — **"Authenticate with Microsoft" unavailable with Dynamics 365 Customer Service**
- [Variables overview](https://learn.microsoft.com/microsoft-copilot-studio/authoring-variables-about) — `User.PrincipalName`, `User.Email` and system variables
- [Add user authentication to topics](https://learn.microsoft.com/microsoft-copilot-studio/advanced-end-user-authentication) — auth variables are unavailable without authentication
- [Modify an existing flow to use with an agent](https://learn.microsoft.com/microsoft-copilot-studio/flow-modify-use-with-agent) — asynchronous response must be **Off**
- [Agent flows FAQ](https://learn.microsoft.com/microsoft-copilot-studio/flows-faqs) — agent flows are available in GCC and GCC High
- [FlowActionBadRequest error in channels](https://learn.microsoft.com/troubleshoot/power-platform/copilot-studio/channels/agent-flow-action-bad-request) — schema mismatch after editing a flow
- [EncodeUrl / EncodeHTML / PlainText](https://learn.microsoft.com/power-platform/power-fx/reference/function-encode-decode) — `EncodeUrl` is supported in Copilot Studio
- [Power Fx formula reference for Copilot Studio](https://learn.microsoft.com/power-platform/power-fx/formula-reference-copilot-studio) — confirms `Concatenate`, `Char`, `EncodeUrl`
