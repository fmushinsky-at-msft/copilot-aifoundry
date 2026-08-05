# Verifying Built-In Conversational Feedback Availability

A step-by-step procedure to determine whether Copilot Studio's **built-in** thumbs up/down
feedback (and the free-text comment on negative ratings) is **available, enabled, and
queryable** in your environment.

**Why this guide exists:** feature parity differs between Commercial and US Government clouds
(GCC / GCC High / DoD). Rather than assume, this walks you through checking each layer so you
end with a definitive answer — and a decision on whether to use the custom feedback approach
instead.

**Time required:** about 30–45 minutes.

> **Scope note:** this verifies the **built-in** feedback feature. If you have already
> implemented the custom route, see
> [CUSTOM_FEEDBACK_SETUP_GUIDE.md](./CUSTOM_FEEDBACK_SETUP_GUIDE.md).

---

## Table of contents
- [Understand the layers](#understand-the-layers)
- [Record your environment details](#record-your-environment-details)
- [Check 1 — Is the feedback UI shown to users?](#check-1--is-the-feedback-ui-shown-to-users)
- [Check 2 — Agent settings](#check-2--agent-settings)
- [Check 3 — Copilot Studio Analytics](#check-3--copilot-studio-analytics)
- [Check 4 — Dataverse ConversationTranscript](#check-4--dataverse-conversationtranscript)
- [Check 5 — Application Insights](#check-5--application-insights)
- [Check 6 — Official documentation](#check-6--official-documentation)
- [Controlled end-to-end test](#controlled-end-to-end-test)
- [Interpreting your results](#interpreting-your-results)
- [Escalating to Microsoft Support](#escalating-to-microsoft-support)

---

## Understand the layers

Feedback can fail at any of four independent layers. Checking them in order tells you *where*
the gap is, not just *that* there is one.

| Layer | Question | If broken here |
|---|---|---|
| **1. UI** | Do users even see 👍/👎 in Teams? | Feature not enabled or not available in this cloud |
| **2. Capture** | Does clicking it get recorded at all? | Transcript/analytics logging disabled |
| **3. Storage** | Does it land in Dataverse? | Table absent, or feedback not persisted in this cloud |
| **4. Access** | Can you read/query it? | Permissions, or no supported query surface |

> A very common false alarm: **transcript logging is turned off**, so there is nothing to find
> even in Commercial. Check 2 covers this.

---

## Record your environment details

Fill this in first — you will need it for every check and for any support ticket.

| Item | Value | Where to find it |
|---|---|---|
| Cloud type | GCC / GCC High / DoD / Commercial | Ask your tenant admin |
| Copilot Studio URL | | The URL you actually use |
| Power Platform environment name | | Copilot Studio top-right picker |
| Environment ID | | Power Platform Admin Center → Environments → your env → Details |
| Dataverse URL | | Admin Center → environment → **Environment URL** |
| Agent name / ID | | Copilot Studio → agent → **Settings → Details** |
| Region | | Admin Center → environment → Details |

> Government portals use different hostnames (e.g. `*.microsoft.us`, `*.powerapps.us`).
> Use whichever your tenant already uses rather than the commercial addresses.

---

## Check 1 — Is the feedback UI shown to users?

The fastest signal. Do this in **Teams**, not the Copilot Studio test panel.

1. Open your agent in **Teams**.
2. Ask any question and let it answer.
3. Look immediately beneath the agent's reply.

| What you see | Meaning |
|---|---|
| 👍 and 👎 icons | Built-in feedback UI **is** present → continue to Check 2 |
| Nothing | Either disabled (Check 2) or unavailable in this cloud (Check 6) |

4. If icons are present, click 👎 — a **"What went wrong?"** box with a Submit button should
   appear.
5. Enter a **unique, searchable marker** so you can find this record later, e.g.:
   ```
   VERIFYTEST-2026-08-04-ALPHA
   ```
6. Submit it, and note the **exact time** (with timezone).

✅ **Record:** icons present? comment box appeared? submission accepted? timestamp?

> Keep that marker string — every later check searches for it.

---

## Check 2 — Agent settings

Confirm the feature and its prerequisite (transcript logging) are enabled.

1. Copilot Studio → open your agent → **Settings** (gear icon).
2. Look through these sections — exact labels vary by release:
   - **General** / **Details**
   - **Security** / **Privacy**
   - **Advanced**
3. Look for toggles similar to:
   - *Collect user feedback* / *Conversational feedback*
   - *Log conversation transcripts* / *Store conversation transcripts*
   - *Share data with Microsoft* / *Analytics*

| Finding | Action |
|---|---|
| Feedback toggle exists and is **off** | Turn it on → **Save** → **Publish** → redo Check 1 |
| Transcript logging is **off** | Turn it on (feedback is stored with transcripts) → Save → Publish |
| Neither toggle exists anywhere | Strong signal the feature is not surfaced in this cloud → Check 6 |

⚠️ **Publish after any settings change** — Teams keeps serving the old version otherwise.

✅ **Record:** which toggles exist, and their state.

---

## Check 3 — Copilot Studio Analytics

1. Copilot Studio → your agent → **Analytics**.
2. Review the available tabs (commonly *Summary*, *Engagement*, *Sessions*, *Billing*).
3. Look for any customer-satisfaction / feedback metric — often labelled **CSAT**,
   *Customer satisfaction*, or *Feedback*.

| Finding | Meaning |
|---|---|
| A CSAT/feedback chart with data | Feedback is being collected ✅ |
| A CSAT/feedback chart that is empty | Collected but no data yet, or not persisted — continue |
| No such view at all | Analytics surface for feedback is unavailable in this cloud |

> Analytics can lag **24–48 hours**. An empty chart shortly after your test is not conclusive.

✅ **Record:** does a feedback view exist? does it show any data?

---

## Check 4 — Dataverse ConversationTranscript

This is where built-in feedback is stored, so it is the most decisive check.

### 4a — Does the table exist?
1. Go to **Power Apps** (your cloud's URL, e.g. `make.gov.powerapps.us`).
2. Confirm the **environment picker** (top-right) matches your agent's environment.
3. Left navigation → **Tables** → switch the filter to **All**.
4. Search for `Conversation Transcript`.

| Finding | Meaning |
|---|---|
| Table exists | Continue to 4b |
| Table missing | Transcripts are not stored in this environment → jump to [Interpreting](#interpreting-your-results) |

### 4b — Does it contain rows?
1. Open the table → **Data** tab.
2. Look for recent rows around your Check 1 timestamp.
3. If rows exist, open one and inspect the **Content** column — it holds a large JSON
   transcript.

### 4c — Search for your marker
The feedback rating and comment are embedded inside that JSON.

**Option A — Advanced Find / table view**
Filter `Content` **contains** `VERIFYTEST-2026-08-04-ALPHA`.

**Option B — Web API in a browser**
Signed in to the same tenant, open:
```
https://<your-dataverse-url>/api/data/v9.2/conversationtranscripts?$select=conversationtranscriptid,createdon&$top=20&$orderby=createdon desc
```
Then open a recent record and search its `content` for your marker.

**Option C — Power Automate (most reliable)**
1. Create a flow with a manual trigger.
2. Add **Dataverse → List rows**:
   - **Table name:** `Conversation Transcripts`
   - **Filter Query:** `createdon gt 2026-08-04T00:00:00Z` (use your test date)
   - **Row count:** 50
3. Add **Compose** → `@{outputs('List_rows')?['body/value']}`
4. Run it and inspect the output for your marker and for feedback-related keys such as
   `feedback`, `rating`, `thumbs`, `Positive`, `Negative`.

| Finding | Meaning |
|---|---|
| Marker found with rating/comment | ✅ **Feedback is captured and queryable** |
| Transcripts present, marker absent | Conversations logged, but feedback is **not** persisted |
| No transcripts at all | Transcript logging is off, or unsupported here |

✅ **Record:** table exists? rows exist? marker found? feedback fields present?

---

## Check 5 — Application Insights

Only relevant if the **agent** (not just your Function) is connected to Application Insights.

1. Copilot Studio → agent → **Settings** → look for **Application Insights** / **Diagnostics**
   / **Telemetry**.
2. If a connection string is configured, note which App Insights resource it targets.
3. Open that resource → **Logs** and run:

```kql
union customEvents, traces, pageViews
| where timestamp > ago(1d)
| where tostring(customDimensions) has_any ("feedback","Feedback","rating","thumbs","csat")
| project timestamp, itemType, name, customDimensions
| order by timestamp desc
```

Search specifically for your marker:
```kql
union customEvents, traces
| where timestamp > ago(1d)
| where tostring(customDimensions) contains "VERIFYTEST-2026-08-04-ALPHA"
   or message contains "VERIFYTEST-2026-08-04-ALPHA"
| project timestamp, itemType, name, customDimensions, message
```

| Finding | Meaning |
|---|---|
| Feedback events found | ✅ Available via App Insights |
| Agent telemetry present, no feedback events | Feedback not emitted to telemetry |
| No agent telemetry at all | Agent is not connected to App Insights |

> ⚠️ Do not confuse this with **your Function's** App Insights resource. They may be
> different resources; confirm which connection string the agent uses.

✅ **Record:** agent connected? feedback events present?

---

## Check 6 — Official documentation

1. Search Microsoft Learn for:
   - `Copilot Studio US Government feature parity`
   - `Microsoft Copilot Studio GCC limitations`
   - `Copilot Studio conversational feedback`
2. Compare the documented feature list against your cloud type.
3. Also check the **Power Platform / Copilot Studio release notes** for whether the feature is
   listed as planned for government clouds.

✅ **Record:** what the parity documentation states for your cloud, with the date checked.

---

## Controlled end-to-end test

Run this once, cleanly, after completing Checks 1–2 (so settings are correct).

1. **Choose a fresh marker:** `VERIFYTEST-<date>-<random>`.
2. **Note the start time** (UTC).
3. In **Teams**, ask a question and let the agent answer.
4. Click **👎** and submit a comment containing the marker.
5. **Wait 30 minutes** (Dataverse writes are usually fast; analytics is slower).
6. Re-run **Check 4c** and **Check 5**.
7. **Wait 24–48 hours**, then re-run **Check 3** (Analytics can lag substantially).

Record results in this table:

| Layer | Checked at | Result |
|---|---|---|
| UI icons shown | | |
| Comment box appeared | | |
| Dataverse transcript row created | | |
| Marker found in transcript | | |
| Rating/comment fields present | | |
| App Insights event | | |
| Analytics CSAT view populated | | |

---

## Interpreting your results

| Pattern | Conclusion | Recommended action |
|---|---|---|
| Icons shown, marker found in Dataverse | **Fully available** ✅ | Build reporting on `ConversationTranscript` |
| Icons shown, transcripts exist, marker **not** found | Captured in UI but **not persisted** | Treat as unavailable → use custom feedback |
| Icons shown, **no** transcripts | Transcript logging off/unsupported | Enable it (Check 2); if no toggle exists → custom feedback |
| **No icons** in Teams, no settings toggle | **Not available in this cloud** | Use custom feedback |
| Icons shown but nothing anywhere after 48h | Collected but not exposed to you | Open a support ticket; use custom feedback meanwhile |

### If the built-in feedback is unavailable
Use the custom implementation, which works in any cloud and additionally lets you **join
feedback to the original question and its `canAnswer` flag**:

👉 **[CUSTOM_FEEDBACK_SETUP_GUIDE.md](./CUSTOM_FEEDBACK_SETUP_GUIDE.md)**

Queries: **[ANALYTICS_KQL_QUERIES.md](./ANALYTICS_KQL_QUERIES.md)** → *User feedback*.

---

## Escalating to Microsoft Support

For government clouds, a support ticket is often the fastest definitive answer.

**Ask these specific questions:**
1. Is conversational feedback (thumbs up/down with comments) **supported** for Copilot Studio
   agents in **\<your cloud\>**?
2. If supported, **where is it stored** and how can a tenant admin query it?
3. Is feedback written to the **`ConversationTranscript`** table in this cloud? If not, which
   store is used?
4. Are there **prerequisite settings** (transcript logging, analytics, data sharing) that must
   be enabled?
5. If not currently supported, is it on the **roadmap**, and when?

**Include in the ticket:**
- Cloud type, environment name and ID, region
- Agent name/ID
- Your completed results table from the controlled test
- The marker string and exact test timestamp
- Screenshots: Teams reply (with/without icons), agent settings, Analytics view

---

## Quick reference — decision flow

```
Are 👍/👎 icons visible in Teams?
		|
   No --+-- Yes
   |         |
   |         v
   |    Submit test feedback with a unique marker
   |         |
   |         v
   |    Does ConversationTranscript contain the marker?
   |         |
   |    No --+-- Yes
   |    |         |
   v    v         v
Check settings   Built-in feedback WORKS
(Check 2)        -> build reporting on Dataverse
   |
   v
Toggle exists? -- No --> Not available in this cloud
   |                     -> use CUSTOM_FEEDBACK_SETUP_GUIDE.md
  Yes
   |
   v
Enable, publish, retest
```
