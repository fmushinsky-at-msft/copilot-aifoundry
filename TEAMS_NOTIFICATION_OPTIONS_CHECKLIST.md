# Verifying Teams Notification Options in Your Environment

Step-by-step checks to determine whether **Option A** (Workflows webhook) and **Option D**
(channel email address) are usable in your GCC tenant.

Work through this at your own pace. Record answers in the
[Findings template](#findings-template) at the end — that captures everything needed to decide
which option to build.

**Time required:** 20–30 minutes for both options.

**No changes are made to production.** Every step is read-only except two optional end-to-end
tests, which post a clearly-labelled test message you can delete.

---

## Table of contents
- [Before you start](#before-you-start)
- [What each option is](#what-each-option-is)
- [Part 1 — Option D: channel email address](#part-1--option-d-channel-email-address)
- [Part 2 — Option A: Workflows webhook](#part-2--option-a-workflows-webhook)
- [Part 3 — Interpreting your results](#part-3--interpreting-your-results)
- [Part 4 — Wording for admin requests](#part-4--wording-for-admin-requests)
- [Findings template](#findings-template)
- [Troubleshooting](#troubleshooting)

---

## Before you start

### Decide which channel you're targeting

Pick the exact team and channel where HR escalations should land. Write both names down — you
will need them repeatedly, and "the HR channel" is ambiguous once you're clicking through menus.

- Team name: ______________________
- Channel name: ______________________

### Access you'll need

| Check | Who can do it |
|---|---|
| D2, D3, D4 (channel email) | Any **team owner** of that team |
| D1 (tenant email setting) | **Teams administrator** |
| A1, A3, A5, A6 (Workflows) | Any user with Teams + Power Automate access |
| A2 (app permission policy) | **Teams administrator** |
| A4 (DLP policy) | **Power Platform administrator** |

You can complete most checks yourself. The admin-only ones (D1, A2, A4) have a fallback: if the
user-level check succeeds, the admin setting is already permissive and you can skip it.

**Do the user-level checks first.** If D2 returns an email address, D1 is already enabled — no
need to ask anyone.

### Finding the admin centres

⚠️ **Don't type admin URLs directly.** Government cloud addresses differ from commercial
(`.us` vs `.com`), and guessing wastes time. Navigate instead:

1. Sign in to **portal.office.com** (or your organisation's Microsoft 365 sign-in page)
2. Select the **app launcher** (the grid icon, top-left)
3. Select **Admin** → then **Show all** in the left nav
4. Pick **Teams** or **Power Platform** from the admin centre list

That reaches the correct endpoint for your cloud automatically.

---

## What each option is

Brief context so the checks make sense.

**Option D — channel email address.** Every Teams channel can be given an email address. Send
an email to it and the message appears as a post in the channel. Your existing `send_hr_email`
function already sends email — you'd just add the channel address as a recipient. **No new code.**

**Option A — Workflows webhook.** You create a Power Automate flow in Teams that listens on an
HTTPS URL. The function POSTs JSON to that URL; the flow posts to the channel. **Requires a new
function** (`post_teams_message`) and an app setting holding the webhook URL.

---

## Part 1 — Option D: channel email address

Check this first. If it works, you're done without writing code.

### Check D2 — Can you get an email address for the channel?

*(Numbered D2 deliberately — this also answers D1. Start here.)*

1. Open **Microsoft Teams**
2. In the left rail, select **Teams**
3. Find your target team, then hover over the **channel name**
4. Select **More options** — the **…** that appears to the right of the channel name

   > Make sure you're on the **channel**, not the team. Hovering the *team* name gives a
   > different menu without email options.

5. Look for **Get email address** in the menu

**What you might see:**

| Result | Meaning | Next step |
|---|---|---|
| **Get email address** appears, and clicking it shows an address | ✅ Email integration is **enabled** | Record the address, go to D3 |
| **Get email address** appears but errors on click | ⚠️ Partially configured | Note the exact error, go to D1 |
| **Get email address** is **absent** from the menu | ❌ Likely disabled tenant-wide | Go to D1 |

The address looks similar to:
```
HR Escalations - Benefits <a1b2c3d4.yourtenant.onmicrosoft.com@amer.teams.ms>
```

**Record just the part between `<` and `>`** — that's the actual address. Ignore the display
name in front of it.

⚠️ **Treat this address as sensitive.** Depending on D3 settings, anyone who has it may be able
to post into the channel.

---

### Check D3 — What are the channel's email restrictions?

**This is the most important check in the document.** It determines whether Option D works with
how your function actually sends mail.

1. In the same **Get email address** dialog, select **Advanced settings**
   *(may appear as a link or a small gear icon)*
2. Note which option is selected:

| Setting | Works with `send_hr_email`? |
|---|---|
| **Anyone can send emails to this address** | ✅ Yes |
| **Only members of this team** | ⚠️ **Only if every employee is a team member** |
| **Only email sent from these domains** | ✅ Yes, if your email domain is listed |

**Why this matters:** your `send_hr_email` function sends **as the employee**, from their own
mailbox — that was a deliberate design decision so HR replies go back to the person who asked.
So the "From" address is `employee@yourdomain`, not a service account.

If the channel is set to **Only members of this team** and the HR channel contains only HR
staff, employee escalations will be **silently rejected**. The function will report success —
Graph accepted the message — but nothing appears in the channel.

**If you find "Only members of this team":** switch it to **Only email sent from these domains**
and add your organisation's email domain. That accepts all employees while still blocking
external senders. This is the recommended configuration.

Record: current setting = ______________________

---

### Check D1 — Is email integration enabled tenant-wide?

**Skip this if D2 succeeded.** Only needed if **Get email address** was missing or errored.

*Requires Teams administrator.*

1. Open the **Teams admin centre** (see [Finding the admin centres](#finding-the-admin-centres))
2. Left nav → **Teams** → **Teams settings**
3. Scroll to the **Email integration** section
4. Check: **Users can send emails to a channel email address**

| State | Meaning |
|---|---|
| **On** | Enabled — if D2 still failed, see [Troubleshooting](#troubleshooting) |
| **Off** | Disabled tenant-wide. Option D unavailable until an admin enables it |

There may also be an **Accepted domains** setting here restricting which sending domains are
allowed org-wide. Note its value if present.

⚠️ This is an **organisation-wide** setting. Enabling it affects every team, not just yours.
Your admin may reasonably want to discuss scope — see
[Part 4](#part-4--wording-for-admin-requests) for suggested wording.

Record: setting = ☐ On ☐ Off ☐ Couldn't check (no admin access)

---

### Check D4 — End-to-end test

Only if D2 returned an address. This confirms the whole path actually works.

1. Open **Outlook** (web or desktop), signed in as **yourself** — not a shared mailbox
2. New email:
   - **To:** the channel address from D2
   - **Subject:** `TEST - please ignore - checking channel email`
   - **Body:** `Test message, safe to delete.`
3. **Send**
4. Wait **1–2 minutes**, then check the Teams channel

| Result | Meaning |
|---|---|
| Message appears as a post | ✅ **Option D fully works** |
| Nothing appears, no bounce | ⚠️ Likely blocked by D3 restrictions — recheck |
| You receive a bounce (NDR) | ❌ Read the bounce text — it usually names the cause |

**Common bounce:** *"integration is not enabled for the tenant"* → the D1 setting is off.

Delete the test post afterwards (hover the message → **…** → **Delete**).

Record: test result = ☐ Appeared ☐ Nothing ☐ Bounced (text: ______________)

---

## Part 2 — Option A: Workflows webhook

Do these even if Option D worked — knowing both are available is useful, and Option A gives
nicer formatting if you later want Adaptive Cards.

### Check A1 — Is the Workflows app visible in Teams?

1. In Teams, hover your target **channel** name → **More options (…)**
2. Look for **Workflows** in the menu

| Result | Meaning |
|---|---|
| **Workflows** appears | ✅ App is available — go to A3 |
| Not in the menu | Try the alternate path below |

**Alternate path:**
1. Teams left rail → **Apps** (grid icon, may be under **…**)
2. Search for `Workflows`
3. If found, it's available — the channel menu may just be laid out differently in your
   Teams version

| Result | Next step |
|---|---|
| Found via either path | ✅ Go to A3 |
| Not found at all | ❌ Go to A2 |

Record: Workflows app visible = ☐ Yes ☐ No

---

### Check A2 — Is the Workflows app allowed by policy?

**Skip if A1 succeeded.**

*Requires Teams administrator.*

1. **Teams admin centre** → **Teams apps** → **Manage apps**
2. Search for `Workflows`
3. Check the **Status** column

| Status | Meaning |
|---|---|
| **Allowed** | Permitted org-wide — if A1 still failed, check app permission policies |
| **Blocked** | An admin has blocked it. Option A unavailable until unblocked |

If Allowed but still not visible: **Teams apps** → **Permission policies** → check whether the
policy assigned to your account excludes Microsoft apps.

Record: app status = ☐ Allowed ☐ Blocked ☐ Couldn't check

---

### Check A3 — Do you have a usable Power Automate licence?

1. Microsoft 365 **app launcher** (grid icon) → **Power Automate**
   *(if not listed, select **All apps** and search)*
2. If it opens, you have at least a seeded licence
3. Top-right **gear icon** → **View my licenses** (or **Plan**)

For this scenario you need the **Microsoft Teams connector**, which is a **standard** connector —
included with Microsoft 365 seeded licences. You do **not** need Power Automate Premium.

| Result | Meaning |
|---|---|
| Power Automate opens | ✅ Go to A4 |
| Not available / access denied | ❌ Licence or policy issue — note the message |

Record: Power Automate accessible = ☐ Yes ☐ No

---

### Check A4 — Is the Teams connector blocked by DLP?

**Optional.** If A5 succeeds, DLP isn't blocking you — skip this.

*Requires Power Platform administrator.*

1. **Power Platform admin centre** → **Policies** → **Data policies**
2. Open the policy applying to your environment
3. Find **Microsoft Teams** in the connector list
4. Note its group: **Business**, **Non-Business**, or **Blocked**

If **Blocked**, flows can't use the Teams connector. If Business/Non-Business, note which —
a flow can't mix connectors across groups, though that only matters for multi-connector flows.

Record: Teams connector group = ______________________

---

### Check A5 — Can you create the flow?

The real test. This **does create a flow**, but nothing posts until you send a request.

1. In Teams, hover your target **channel** → **More options (…)** → **Workflows**
2. In the template search, look for **Send webhook alerts to a channel**

   > If that exact template is missing, look for anything with "webhook" in the name.
   > Template availability varies between clouds — record what you actually see.

3. Select the template
4. **Connection screen:** confirm the Teams connection shows a green tick. If prompted, sign in.
5. **Next**
6. **Configure:**
   - **Team:** your target team
   - **Channel:** your target channel
7. **Create flow**
8. On the confirmation screen, **copy the webhook URL**

**What the URL looks like:**
```
https://prod-XX.<region>.logic.azure.us:443/workflows/<guid>/triggers/manual/paths/invoke?...&sig=<signature>
```

⚠️ **Note the domain.** Government tenants use **`logic.azure.us`**; commercial uses
`logic.azure.com`. Record which you got — it confirms you're on the Gov endpoint.

⚠️ **The URL is a credential.** That `sig=` parameter grants posting rights to anyone holding
it. Store it in a password manager for now, not a text file or chat message.

| Result | Next step |
|---|---|
| Flow created, URL copied | ✅ Go to A6 |
| Template not listed | ❌ Record which templates *were* offered |
| Error during creation | ❌ Record the exact error text |

Record:
- Template found = ☐ Yes ☐ No (available templates: ______________)
- Flow created = ☐ Yes ☐ No
- URL domain = ☐ `logic.azure.us` ☐ `logic.azure.com` ☐ other: __________

---

### Check A6 — End-to-end test

Confirms the URL actually delivers.

In **PowerShell** (`pwsh`):

```powershell
$url  = "PASTE_YOUR_WEBHOOK_URL_HERE"
$body = @{ text = "TEST from checklist - please ignore" } | ConvertTo-Json

Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json"
```

| Result | Meaning |
|---|---|
| No error, message appears in channel within ~30s | ✅ **Option A fully works** |
| No error, but nothing appears | ⚠️ Flow ran but failed — check run history below |
| `400 Bad Request` | Payload shape doesn't match the trigger schema — see below |
| `401` / `403` | URL incomplete when pasted, or auth required |

**If it failed, read the flow's run history** — this is Workflows' big advantage over the old
connectors, which gave you nothing:

1. **Power Automate** (via app launcher) → **My flows**
2. Open the flow you just created
3. **Run history** → click the most recent run
4. Any failed step shows its exact input and error

**If you got `400`:** the template expects a specific JSON shape. In the flow designer, open the
trigger step and look at **Request Body JSON Schema** — that tells you what to send. Record it;
the function needs to match.

Record:
- Test result = ☐ Posted ☐ Failed (error: ______________)
- Required JSON schema = ______________________

**Clean up:** delete the test post from the channel. **Keep the flow** if you're likely to use
Option A — deleting and recreating generates a different URL.

---

### Check A7 — Add a co-owner

**Do this immediately if you're keeping the flow.**

Workflows belong to **a person**, not a channel. If your account is disabled or you change
roles, the flow becomes orphaned and escalations **silently stop**. The old connectors didn't
have this failure mode.

1. **Power Automate** → **My flows** → your flow
2. **Edit** next to **Owners** (right-hand panel)
3. Add at least one colleague, ideally a **team or service account**

Record: co-owner added = ☐ Yes ☐ No (who: ______________)

---

## Part 3 — Interpreting your results

| D works | A works | Recommendation |
|---|---|---|
| ✅ | ✅ | **Take D.** No code, no secret, reuses existing `EmailSent` telemetry. Keep A documented as a fallback. |
| ✅ | ❌ | **Take D.** Nothing further needed. |
| ❌ | ✅ | **Take A.** Requires the new `post_teams_message` function — ask and I'll write it. |
| ❌ | ❌ | Escalate to admins using [Part 4](#part-4--wording-for-admin-requests). Interim fallback: keep emailing an HR distribution list. |

### Why D is preferred when both work

| | Option D | Option A |
|---|---|---|
| New code | None | New function + deployment |
| Secret to manage | None | Webhook URL (a credential) |
| Owner dependency | None — belongs to channel | **Flow owner; orphans if they leave** |
| Auto-disable risk | None | Off after 14 days of errors, or 90 days idle |
| Power BI dashboard | Works unchanged | Needs new queries + measures |
| Message format | Email-style post | Adaptive Card (nicer) |

The only real argument for A is card formatting. Weigh that against a permanent operational
dependency on a user-owned flow.

---

## Part 4 — Wording for admin requests

Copy-paste as needed.

**If D1 is off (Teams admin):**

> Could you enable **Teams admin centre → Teams → Teams settings → Email integration →
> "Users can send emails to a channel email address"**?
>
> We're routing unanswered HR benefits questions from an internal assistant into a Teams
> channel. The alternative requires a user-owned Power Automate flow that stops working if the
> owner leaves, so the channel email route is more robust.
>
> I understand this is org-wide. Per-channel access is still controlled by each channel's
> **Advanced settings**, and we'd restrict ours to our own email domain.

**If A2 shows Workflows blocked (Teams admin):**

> Could you allow the Microsoft **Workflows** app in **Teams admin centre → Teams apps →
> Manage apps**? It's a first-party Microsoft app and the supported replacement for the retired
> Office 365 Connectors. We need it to post automated notifications into a Teams channel.

**If A4 shows Teams connector blocked (Power Platform admin):**

> The **Microsoft Teams** connector is currently in the **Blocked** group in our DLP data
> policy. Could it move to **Business**? We need a flow that posts notifications to a Teams
> channel — Teams is the only connector involved.

---

## Findings template

Fill this in and send it back — it's everything needed to decide and, if required, write the code.

```
TARGET
  Team:                        ______________________
  Channel:                     ______________________

OPTION D - CHANNEL EMAIL
  D2  Get email address shown:  Yes / No
  D2  Address obtained:         ______________________
  D3  Restriction setting:      Anyone / Team members only / Specific domains
  D3  Domains listed:           ______________________
  D1  Tenant setting:           On / Off / Not checked
  D4  Test email result:        Appeared / Nothing / Bounced
  D4  Bounce text (if any):     ______________________
  => OPTION D WORKS:            Yes / No

OPTION A - WORKFLOWS WEBHOOK
  A1  Workflows app visible:    Yes / No
  A2  App status in admin:      Allowed / Blocked / Not checked
  A3  Power Automate opens:     Yes / No
  A4  Teams connector group:    Business / Non-Business / Blocked / Not checked
  A5  Template found:           Yes / No
  A5  Templates offered:        ______________________
  A5  Flow created:             Yes / No
  A5  URL domain:               logic.azure.us / logic.azure.com / other
  A6  Test POST result:         Posted / Failed
  A6  Error (if any):           ______________________
  A6  Required JSON schema:     ______________________
  A7  Co-owner added:           Yes / No
  => OPTION A WORKS:            Yes / No

NOTES / ANYTHING UNEXPECTED
  ______________________________________________
```

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| **Get email address** missing from menu | Email integration off tenant-wide | Check D1 |
| Menu looks different from this guide | Teams version differences | Try the team **…** menu, or **Manage channel** |
| Test email vanishes silently | Channel restricted to team members | Check D3; switch to domain restriction |
| Bounce: *"integration is not enabled"* | D1 setting is off | Ask admin (Part 4) |
| Bounce: *"recipient not found"* | Address mistyped | Re-copy — take only the part inside `<...>` |
| **Workflows** missing everywhere | App blocked, or not available in your cloud | Check A2 |
| Webhook template list is empty/short | Template availability varies by cloud | Record what *is* offered |
| POST returns `400` | Payload doesn't match trigger schema | Check the trigger's Request Body JSON Schema |
| POST returns `401`/`403` | URL truncated when pasted | Re-copy the whole URL, including `sig=` |
| Flow runs but nothing posts | Action failed inside the flow | Power Automate → run history → open failed step |
| Everything worked, stopped weeks later | Flow auto-disabled (14d errors / 90d idle) | Re-enable in Power Automate; add co-owners |

### Where to find more detail

- Flow failures: **Power Automate → My flows → [flow] → Run history**
- Email delivery failures: the bounce message in your own inbox
- Function-side behaviour: `traces` and `customEvents` in Application Insights

---

## After you've finished

Send back the filled-in [findings template](#findings-template). Depending on results:

- **Option D works** → I'll show the `HR_ALLOWED_RECIPIENTS` change and how to pass the channel
  address as `to_address`. No deployment beyond an app setting.
- **Only Option A works** → I'll write `post_teams_message` matching the JSON schema you
  recorded, with `TeamsMessageSent` / `TeamsMessageFailed` telemetry consistent with the
  existing email events.
- **Neither works** → we'll plan around the admin requests in Part 4.
