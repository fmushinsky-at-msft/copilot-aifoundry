# Option A — Connect to a Representative via Teams Deep Link

**What this document is:** a beginner's guide to adding a **"Connect to a representative"**
choice to the HR Benefits agent using a **Microsoft Teams deep link**. When the agent cannot
answer, the user gets a link that opens a Teams group chat with HR, their question already
typed in.

**Who this is for:** someone who has never configured Copilot Studio. Every step says where
to click and what you should see afterwards.

**Time required:** about 30 minutes.
**Cost:** none. No licence, no Azure resource, no code change.

> ## 🔒 Read this before anything else
>
> **This option cannot hide the identity of the HR representatives.** A Teams group chat
> shows every participant's real name, profile photo and presence status to everyone in it.
> This is core Teams behaviour — there is no setting, policy or workaround that masks it.
>
> If your requirement is that the employee must **not** see who answered, **stop here** and
> use the anonymous relay approach instead (`CONNECT_REP_OPTION_D_ANONYMOUS_RELAY.md`).
>
> If identity exposure is fine — HR reps are known colleagues, and a named conversation is
> actually desirable — this is the fastest and cheapest option available.

---

## Table of contents

- [How to use this document](#how-to-use-this-document)
- [Your scenario — verified facts](#your-scenario--verified-facts)
- [Background — how the current feature works](#background--how-the-current-feature-works)
- [How deep links work](#how-deep-links-work)
- [Step A.1 — Decide who the representatives are](#step-a1--decide-who-the-representatives-are)
- [Step A.2 — Build and test the link by hand](#step-a2--build-and-test-the-link-by-hand)
- [Step A.3 — Open the topic in Copilot Studio](#step-a3--open-the-topic-in-copilot-studio)
- [Step A.4 — Add the second choice](#step-a4--add-the-second-choice)
- [Step A.5 — Build the link with a formula](#step-a5--build-the-link-with-a-formula)
- [Step A.6 — Show the link to the user](#step-a6--show-the-link-to-the-user)
- [Step A.7 — Save, publish and test](#step-a7--save-publish-and-test)
- [Step A.8 — Brief the HR representatives](#step-a8--brief-the-hr-representatives)
- [Pros and cons](#pros-and-cons)
- [Optional — Add telemetry so Power BI stays complete](#optional--add-telemetry-so-power-bi-stays-complete)
- [Troubleshooting](#troubleshooting)
- [Technical questions you are likely to be asked](#technical-questions-you-are-likely-to-be-asked)
- [Reference material](#reference-material)
- [Glossary](#glossary)
- [Sources](#sources)

---

## How to use this document

### If you have 5 minutes

1. Confirm anonymity is **not** required (see the banner above).
2. Collect 2–5 HR email addresses ([Step A.1](#step-a1--decide-who-the-representatives-are)).
3. Test the raw URL in a browser ([Step A.2](#step-a2--build-and-test-the-link-by-hand)) —
   this proves the whole concept in two minutes.
4. Build the rest.

### What to skip on a first read

- **[Reference material](#reference-material)** — a library, not reading material. Come back
  when something breaks.
- **[Technical questions](#technical-questions-you-are-likely-to-be-asked)** — for when you
  present this to others.
- **[Sources](#sources)** — provenance for every claim, for auditing rather than learning.

> ⚠️ **Build it against your own account first.** Point the representative list at yourself
> and one colleague, prove the flow end to end, then switch to real HR addresses.

---

## Your scenario — verified facts

Everything below was checked against this repository and against Microsoft Learn. If any of
it changes, revisit the approach.

| Fact | Value | Why it matters |
|---|---|---|
| Cloud | **GCC** (not GCC High, not DoD) | Decides which options exist at all |
| Agent channel | **Microsoft Teams** | Deep links open natively here |
| Copilot Studio auth | **Authenticate with Microsoft** | Required today by `send_hr_email` |
| User identity variable | **`System.User.PrincipalName`** | What your existing flows pass as `user_email` |
| Function App | `func-hrbenefit-dev003` (Flex Consumption, Python) | Three routes; **no change needed for this option** |
| Existing escalation | "Email HR" via `send_hr_email` | You are adding a *second* choice beside it |

### GCC portal addresses

These come from Microsoft's
[Copilot Studio US Government service URLs](https://learn.microsoft.com/microsoft-copilot-studio/requirements-licensing-gcc#microsoft-copilot-studio-us-government-service-urls)
table — they are **not** simple `.com` → `.us` swaps, so do not guess them.

| Purpose | Commercial | **Your GCC address** |
|---|---|---|
| Copilot Studio | `copilotstudio.microsoft.com` | **`gcc.powerva.microsoft.us`** |
| Power Automate | `flow.microsoft.com` | **`gov.flow.microsoft.us`** |
| Azure Portal | `portal.azure.com` | `portal.azure.us` |
| Teams (deep links) | `teams.microsoft.com` | `teams.microsoft.com` (**unchanged** — GCC is not a sovereign endpoint) |

✅ **That last row is why this option works unmodified.** Only GCC High
(`gov.teams.microsoft.us`) and DoD (`dod.teams.microsoft.us`) use special Teams addresses.

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

✅ **This option requires no change to `function_app.py`.** The only optional code change is
telemetry, covered at the end.

---

## How deep links work

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

---

## Step A.1 — Decide who the representatives are

Write down the **email addresses** of the HR people who should receive these requests.

| Consideration | Guidance |
|---|---|
| How many? | 2–5 works well. More than ~8 makes a noisy chat |
| Use a distribution list? | ❌ **No.** Deep links need individual user addresses, not group addresses |
| Shared mailbox? | ❌ **No.** Must be real user accounts that can sign in to Teams |
| Who? | People who actually monitor Teams during business hours |

Example: `jane.doe@panynj.gov,john.smith@panynj.gov`

⚠️ **Everyone listed sees every request, and they all see each other.** If HR needs requests
split by topic, or kept private between rep and employee, this option is the wrong choice.

✅ **Checkpoint:** you have a comma-separated list of 2–5 real user email addresses, with
**no spaces** around the commas.

---

## Step A.2 — Build and test the link by hand

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
> written as `%20`. This is called *URL encoding*. In the next step Copilot Studio does this
> for you automatically.

---

## Step A.3 — Open the topic in Copilot Studio

1. Go to `https://gcc.powerva.microsoft.us` and sign in with your work account.
2. In the left navigation, click **Agents**.
3. Click your HR Benefits agent to open it.
4. Click **Topics** in the agent's left navigation.
5. Open the topic that currently offers the "Email HR" choice — the one that checks
   `canAnswer`.

✅ **Checkpoint:** you can see the existing Question node offering the email option.

---

## Step A.4 — Add the second choice

1. Find the **Question** node where the user is asked whether to email HR.
2. Click into the node's list of options.
3. Click **+ New option**.
4. Type: `Connect to a representative`

You now have two options where before there was one. Copilot Studio automatically adds a new
empty branch under the Question node for the new choice.

> ⚠️ **Teams caps multiple-choice options at six.** Copilot Studio's channel reference table
> notes that in Teams, multiple-choice options are *"supported up to six (as hero card)."*
> You are going from one option to two, so this is not a problem now — but it is a hard
> ceiling if you later add more escalation paths.

> 💡 **Just because you can add six does not mean you should.** Every extra choice is a
> decision the user has to make while already frustrated. Two is usually right.

✅ **Checkpoint:** the Question node shows both `Email HR` (or your existing wording) and
`Connect to a representative`, and there is an empty branch for the new option.

---

## Step A.5 — Build the link with a formula

The link must contain the user's actual question, so it has to be assembled at run time.

1. In the new branch, click **+ (Add node)** → **Variable management** → **Set a variable
   value**.
2. For **Set variable**, click the dropdown and choose **Create a new variable**. Name it
   `RepChatLink`.
3. For **To value**, click the **fx** button to switch to a formula.
4. Paste this, replacing the email addresses with yours, and replacing `Topic.UserQuestion`
   with whatever your topic actually calls the user's question:

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

⚠️ **`EncodeUrl` is not optional.** Without it, any question containing a space, `&`, `?` or
`#` produces a broken link — and it will *look* fine in testing until someone asks a question
with an apostrophe in it.

> ✅ **All three functions are confirmed supported in Copilot Studio.** `Concatenate`, `Char`
> and `EncodeUrl` all appear in the official
> [Power Fx formula reference for Copilot Studio](https://learn.microsoft.com/power-platform/power-fx/formula-reference-copilot-studio).

> **Finding the right variable name:** click the **{x}** icon in the formula bar to see every
> available variable. If your topic stores the question as `Topic.Question`, use that
> instead. The name must match exactly, including capitalisation.

✅ **Checkpoint:** the formula is accepted with no red error underline.

---

## Step A.6 — Show the link to the user

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
> Copilot Studio's own channel table rates Teams Markdown as *"partially supported"* — the
> link syntax used here is within the supported subset.

⚠️ **Tell the user they must press Send.** Without that sentence, people click the link, see
their question sitting in the box, assume it has been sent, and close the window. This one
sentence prevents the most common support complaint with this design.

✅ **Checkpoint:** the branch has two nodes — set the variable, then send the message.

---

## Step A.7 — Save, publish and test

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

> **Publishing lag:** Teams sometimes serves a cached version of the agent. If you do not see
> the new option after a few minutes, see [Troubleshooting](#troubleshooting).

---

## Step A.8 — Brief the HR representatives

Do not skip this. The reps will receive Teams messages from employees with no warning about
why.

Tell them:
- They will get **group chat messages**, not emails.
- Everyone on the list sees each message, so agree who answers — otherwise either everyone
  replies at once or nobody does.
- The question came from the benefits agent, which could not answer it.
- If the same employee asks again later, it lands in the **same** chat thread.

---

## Pros and cons

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
| **Rep identities fully exposed** | **Cannot be hidden under any configuration** |
| No routing | Every rep gets every request |
| No presence check | Requests go to people on leave |
| Fixed list | Changing reps means editing and republishing the agent |
| No SLA tracking | Nothing measures whether anyone replied |
| User must press Send | Some users will not |
| No transcript passed | Reps see only the question, not the conversation |
| Teams-only | Will not work if you later publish to a public website |
| Diffusion of responsibility | "Someone else will answer" — so nobody does |

**Choose this when:** identity is not sensitive, the rep list is small and stable, and you
want something working this afternoon.

**Avoid it when:** anonymity is required, volume is high enough to need routing, or you need
to measure response times.

> ⏰ **Consider an operating-hours check.** Microsoft's
> [Alternate escalation paths](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-alternate-escalation-paths)
> guidance recommends checking availability *before* offering escalation, and redirecting to
> email when nobody is available. This option silently assumes someone is on the other end.
> A business-hours condition ahead of the choice — offering only "Email HR" outside working
> hours — prevents an employee asking at 22:00 and hearing nothing until morning. Your
> existing "Email HR" option is itself a Microsoft-recommended escalation path, so keeping
> both is the documented pattern.

---

## Optional — Add telemetry so Power BI stays complete

Consider recording that a representative was requested. Without it, your Power BI dashboard
shows failed answers and emails sent — but escalations become invisible, and the deflection
analysis silently understates demand.

⚠️ **This option is invisible to Copilot Studio's built-in analytics.** A deep link is just a
message; nothing marks the session as escalated. Your own telemetry event is the only way to
see usage.

### Two ways to do it

| Approach | Effort | Where it lands |
|---|---|---|
| **From Power Automate** | Low — no code change | ❌ Not applicable — this option involves **no flow at all** |
| **From the Function** | Small code change | Consistent with the five existing events |

Since this option calls no flow, the Function approach is the only one available.

### What the event should look like

The Function already has a `track_event()` helper. A new event would follow the existing
pattern of the other five:

| Dimension | Value |
|---|---|
| `agentLabel` | The caller-supplied display name |
| `question` | The question that could not be answered (truncated) |
| `conversationId` | Join key to `AgentInteraction` |
| `userId`, `userName` | Who asked |
| `method` | `deeplink` |

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

> This is deliberately **not implemented yet** — it is a separate decision.

---

## Troubleshooting

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
| New option not visible in Teams | Teams cached the old agent | Republish; or in Teams admin center disable and re-enable the app; or toggle the Teams channel off and on in Copilot Studio |
| Users still on an old version after publishing | **Teams caches agent updates**, and sessions *"persist indefinitely"* | Documented by the Copilot Studio CAT team in [Best Practices for Deploying Agents in Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment-ux/) |
| `SystemError` in Teams | Teams using a stale published version | Same fix as above — republish, or disable/re-enable the app in Teams admin center. See [known limitations](https://learn.microsoft.com/microsoft-copilot-studio/publication-add-bot-to-microsoft-teams#known-limitations) |
| Users confused by stale context or empty chat after reinstall | Teams conversations persist for months; Conversation Start does not re-fire | **Ready-to-import fixes:** [Design Copilot Studio Agents for Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-agent-patterns/) ships eight patterns with YAML and a downloadable solution |
| Changes not appearing | Saved but not published | Click **Publish**, not just **Save** |

---

## Technical questions you are likely to be asked

**Q: Does this require changing the Azure Function?**
No. This option is configuration-only. The optional telemetry event is the only code change,
and it is not required for the feature to work.

**Q: Will this break the existing "Email HR" feature?**
No. It adds a branch beside it on the same Question node. The email path is untouched.

**Q: Does this send data outside our tenant?**
No. The deep link opens a Teams chat inside your GCC tenant. No third-party service is
introduced, and no data leaves Microsoft 365.

**Q: Can we audit who asked what?**
Yes. The chat is a normal Teams conversation — retained, discoverable and auditable under
your existing policies. It lives in the employee's own chat history.

**Q: Why does the message not send automatically?**
Teams deliberately only *drafts* the message. This is a security behaviour and cannot be
turned off. Treat it as a feature: the user can edit or cancel before sending.

**Q: What if the employee edits the question before sending?**
They can, and that is usually good — they often add context. Your telemetry records the
original question; the chat records what was actually sent.

**Q: Will this work on Teams mobile?**
Yes. Deep links open the Teams mobile app. Test it anyway.

**Q: What happens if an HR rep leaves the organisation?**
The link will fail for that address. Rep changes require editing the formula and
republishing the agent — there is no dynamic list.

**Q: Can we route different questions to different reps?**
Not within one link. You would need multiple branches with different `users` lists, each
triggered by a condition. That complexity is usually the signal to move to a queue-based
approach instead.

**Q: How do we test without bothering HR?**
Point the `users` list at yourself and one colleague. Only switch to real HR addresses after
the end-to-end test passes.

**Q: How do we know if it is being used?**
Add the `RepresentativeRequested` event
([Optional — telemetry](#optional--add-telemetry-so-power-bi-stays-complete)). Nothing else
will show you — deep links leave no trace in Copilot Studio analytics.

---

## Reference material

### Deep links — official documentation

| Resource | What it covers | Closeness |
|---|---|---|
| [Deep link to Teams chat](https://learn.microsoft.com/microsoftteams/platform/concepts/build-and-test/deep-link-teams) | Exact URL format, `users` / `topicName` / `message` | **Primary reference** |
| [Deep link to a workflow in Teams](https://learn.microsoft.com/microsoftteams/platform/concepts/build-and-test/deep-link-workflow) | Starting a chat from a card button (`openUrl`) | Close |
| [Format your agent messages](https://learn.microsoft.com/microsoftteams/platform/bots/how-to/format-your-bot-messages#format-text-content) | **Which Markdown Teams actually renders** — hyperlinks work, headers/lists do not | **Reference for Step A.6** |
| [Plan for sovereign clouds](https://learn.microsoft.com/microsoftteams/platform/concepts/sovereign-cloud) | Confirms GCC uses `teams.microsoft.com` | Why this works unmodified |

⚠️ **There is no official end-to-end tutorial for "Copilot Studio topic → Teams deep link."**
The URL format is documented; wiring it into a Power Fx formula is not. That combination is
this document's own construction — which is why
[Step A.2](#step-a2--build-and-test-the-link-by-hand) tells you to test the raw URL first.

### Working code you can read

| Resource | What it is |
|---|---|
| [OfficeDev/Microsoft-Teams-Samples](https://github.com/OfficeDev/Microsoft-Teams-Samples) | Microsoft's Teams sample catalogue |
| [Deep link consuming Subentity ID (sample)](https://github.com/OfficeDev/Microsoft-Teams-Samples/tree/main/samples/TeamsSDK/Archived/tab-deeplink/csharp) | Runnable sample: calls, chats, tab navigation |

### Copilot Studio authoring

| Resource | What it covers |
|---|---|
| [Create expressions using Power Fx](https://learn.microsoft.com/microsoft-copilot-studio/advanced-power-fx) | `System.` / `Topic.` / `Global.` prefixes; comma separators |
| [Power Fx formula reference for Copilot Studio](https://learn.microsoft.com/power-platform/power-fx/formula-reference-copilot-studio) | Confirms `Concatenate`, `Char`, `EncodeUrl` |
| [EncodeUrl / EncodeHTML / PlainText](https://learn.microsoft.com/power-platform/power-fx/reference/function-encode-decode) | What `EncodeUrl` actually does |
| [Send a message node](https://learn.microsoft.com/microsoft-copilot-studio/authoring-send-message) | Message node capabilities |
| [Variables overview](https://learn.microsoft.com/microsoft-copilot-studio/authoring-variables-about) | System variables |
| [Channel experience reference table](https://learn.microsoft.com/microsoft-copilot-studio/publication-fundamentals-publish-channels#channel-experience-reference-table) | Teams Markdown support; **six-option cap** |

### Microsoft CAT team blog — "The Custom Engine"

[microsoft.github.io/mcscatblog](https://microsoft.github.io/mcscatblog/) — *"Technical
examples and best practices from the Microsoft Copilot Studio CAT team."*

| Post | Why it matters |
|---|---|
| [**Design Copilot Studio Agents for Teams**](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-agent-patterns/) | **Eight production patterns with ready-to-import YAML** — re-installs, stale context, improving the On Error topic |
| [**Best Practices for Deploying Agents in Teams**](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment-ux/) | Teams sessions *"persist indefinitely"*; **updates can be cached** |
| [From DEV to PROD: Deploying Agents to Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment/) | Environments, solutions, promotion |

### Free hands-on training

| Module | Covers |
|---|---|
| [Solution architect series: Copilot Studio in Teams](https://learn.microsoft.com/training/modules/architect-power-virtual-agents/6-pva-teams) | Design guidance for Teams-published agents |

### Escalation design guidance

| Resource | What it gives you |
|---|---|
| [Alternate escalation paths](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-alternate-escalation-paths) | Operating-hours checks; email fallback as a recommended path |
| [Deflection overview](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-overview) | Official definitions of Escalation / Resolution / Abandon rate |
| [Escalation and handoff overview](https://learn.microsoft.com/microsoft-copilot-studio/customer-copilot-overview) | Umbrella page for the escalation capability area |

### Your own repository

| Document | Why it is relevant |
|---|---|
| `COPILOT_STUDIO_SETUP_GUIDE.md` | Click-by-click guide for the existing "Email HR" flow — same Question node |
| `EMAIL_HR_DEPLOYMENT_CHECKLIST.md` | Section 5 documents the authentication dependency |
| `ANALYTICS_KQL_QUERIES.md` | Existing event schema, for the optional telemetry event |

---

## Glossary

| Term | Meaning |
|---|---|
| **Agent** | Two meanings. *AI agent* = the bot. *Live agent* = a human |
| **Channel** (Copilot Studio) | Where an agent is published — Teams, a website, etc. |
| **Deep link** | A URL that makes Teams perform an action instead of opening a web page |
| **Deflection** | The agent answering without escalating. Higher is better |
| **Environment** | A Power Platform container |
| **GCC** | Government Community Cloud. **Not** the same as GCC High |
| **Maker** | Someone permitted to build agents and flows |
| **Power Fx** | The formula language in Copilot Studio (similar to Excel formulas) |
| **System topic** | A built-in topic like Escalate or Fallback |
| **Topic** | A conversation script |
| **UPN** | User Principal Name — usually the sign-in email address |
| **URL encoding** | Replacing unsafe characters (space → `%20`) so they survive in a web address |

---

## Sources

Every non-obvious claim in this document traces to one of these. All verified to resolve.

**Teams deep links:**

- [Deep link to Teams chat](https://learn.microsoft.com/microsoftteams/platform/concepts/build-and-test/deep-link-teams) — URL format; participant, title and message behaviour; existing-chat reuse
- [Deep link to a workflow in Teams](https://learn.microsoft.com/microsoftteams/platform/concepts/build-and-test/deep-link-workflow) — using deep links from card buttons
- [Plan for sovereign clouds](https://learn.microsoft.com/microsoftteams/platform/concepts/sovereign-cloud) — **GCC uses `teams.microsoft.com`**; only GCC High and DoD differ
- [Format your agent messages](https://learn.microsoft.com/microsoftteams/platform/bots/how-to/format-your-bot-messages#format-text-content) — Teams Markdown subset; hyperlinks supported, headers and lists not
- [OfficeDev/Microsoft-Teams-Samples](https://github.com/OfficeDev/Microsoft-Teams-Samples) — Teams sample catalogue

**Copilot Studio authoring:**

- [Create expressions using Power Fx](https://learn.microsoft.com/microsoft-copilot-studio/advanced-power-fx) — variable prefixes and separators
- [Power Fx formula reference for Copilot Studio](https://learn.microsoft.com/power-platform/power-fx/formula-reference-copilot-studio) — confirms `Concatenate`, `Char`, `EncodeUrl`
- [EncodeUrl / EncodeHTML / PlainText](https://learn.microsoft.com/power-platform/power-fx/reference/function-encode-decode) — `EncodeUrl` is supported in Copilot Studio
- [Send a message node](https://learn.microsoft.com/microsoft-copilot-studio/authoring-send-message) — message node capabilities
- [Variables overview](https://learn.microsoft.com/microsoft-copilot-studio/authoring-variables-about) — `User.PrincipalName` and system variables
- [Channel experience reference table](https://learn.microsoft.com/microsoft-copilot-studio/publication-fundamentals-publish-channels#channel-experience-reference-table) — **multiple-choice limited to six options** in Teams
- [Connect and configure an agent for Teams](https://learn.microsoft.com/microsoft-copilot-studio/publication-add-bot-to-microsoft-teams) — known limitations; `SystemError` workaround

**GCC:**

- [Copilot Studio US Government service URLs](https://learn.microsoft.com/microsoft-copilot-studio/requirements-licensing-gcc#microsoft-copilot-studio-us-government-service-urls) — **authoritative GCC portal addresses**
- [Plan for government clouds](https://learn.microsoft.com/microsoftteams/platform/concepts/cloud-overview) — Teams capabilities by government cloud

**Escalation design and measurement:**

- [Alternate escalation paths](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-alternate-escalation-paths) — operating-hours checks; email fallback
- [Deflection overview](https://learn.microsoft.com/microsoft-copilot-studio/guidance/deflection-overview) — official metric definitions
- [Escalation and handoff overview](https://learn.microsoft.com/microsoft-copilot-studio/customer-copilot-overview) — escalation capability area

**Blog posts (Microsoft CAT team):**

- [Design Copilot Studio Agents for Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-agent-patterns/) — eight production patterns with importable YAML
- [Best Practices for Deploying Copilot Studio Agents in Microsoft Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment-ux/) — session persistence, update caching
- [From DEV to PROD: Deploying Agents to Teams](https://microsoft.github.io/mcscatblog/posts/copilot-studio-teams-deployment/) — environments and promotion

**Training:**

- [Solution architect series: Explore Copilot Studio](https://learn.microsoft.com/training/modules/architect-power-virtual-agents/) — includes Copilot Studio in Teams
