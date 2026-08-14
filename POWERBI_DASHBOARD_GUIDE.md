# Power BI Dashboard Guide (Application Insights custom events)

How to build a Power BI dashboard over the custom events emitted by the Azure Function —
agent interactions, user feedback, HR email escalations, and token cost.

**Prerequisites:** telemetry is flowing (see
[ANALYTICS_KQL_QUERIES.md](./ANALYTICS_KQL_QUERIES.md)) and `customEvents` returns rows.

**Time required:** 90–120 minutes for the full dashboard.

---

## Quick start

The detailed sections below carry a lot of caveats — most exist to prevent one specific class
of bug (see [Desktop vs service traps](#things-that-work-in-desktop-but-break-after-publishing)).
If you just want the shortest correct path:

1. **Verify data exists** — Portal → App Insights → Logs → run
   `customEvents | where timestamp > ago(7d) | summarize count() by name`
   ([Step 1.1](#step-11--verify-data-exists-first))
2. **Confirm sampling is off** — `Events` must equal `SumItemCount`
   ([sampling check](#confirm-sampling-is-disabled)) — otherwise every count is wrong
3. **Build 4 queries** via Portal **Export → Power BI (M query)**, one per event type
   ([Part 2](#part-2--build-the-source-tables))
4. **In Power Query:** set data types, add `EventDate` — *not* as a DAX column
   ([Step 2.5](#25--set-data-types-and-add-eventdate))
5. **Date table + relationships** ([Part 3](#part-3--create-the-data-model))
6. **Add measures** — start with the Volume block only ([Part 4](#part-4--add-dax-measures))
7. **One page of cards** to prove it works, then expand ([Part 5](#part-5--build-the-report-pages))
8. **Publish, run a *scheduled* refresh, and reconcile against KQL** — Desktop alone will not
   surface the traps ([Part 6](#part-6--publish-and-schedule-refresh))

**Three things that will cost you the most time if skipped:** the sampling check (step 2),
building `EventDate` in Power Query rather than DAX (step 4), and validating after a scheduled
refresh rather than in Desktop (step 8).

---

## Table of contents
- [Quick start](#quick-start)
- [Before you begin](#before-you-begin)
  - [Permissions required](#permissions-required)
  - [Government cloud (GCC) note](#government-cloud-gcc-note)
  - [Desktop vs service traps](#things-that-work-in-desktop-but-break-after-publishing)
- [Part 1 — Connect Power BI to Application Insights](#part-1--connect-power-bi-to-application-insights)
  - [Method A — Export the M query (recommended)](#method-a--export-the-m-query-recommended)
  - [Method B — Azure Data Explorer (Kusto) connector](#method-b--azure-data-explorer-kusto-connector)
  - [Method C — Power BI (new Dataset)](#method-c--power-bi-new-dataset-from-the-portal)
- [Part 2 — Build the source tables](#part-2--build-the-source-tables)
- [Part 3 — Create the data model](#part-3--create-the-data-model)
- [Part 4 — Add DAX measures](#part-4--add-dax-measures)
- [Part 5 — Build the report pages](#part-5--build-the-report-pages)
- [Part 6 — Publish and schedule refresh](#part-6--publish-and-schedule-refresh)
- [Part 7 — Troubleshooting](#part-7--troubleshooting)
- [Appendix — event reference](#appendix--event-reference)

---

## Before you begin

### What you need
| Item | Notes |
|---|---|
| **Power BI Desktop** | Latest version, installed locally (64-bit) |
| **Power BI licence** | Pro (or PPU/Premium) to publish and share |
| **Reader access** to the Application Insights resource | See permissions below |
| Application Insights **resource name**, **subscription ID**, **resource group** | From the Azure Portal → your App Insights → Overview / Properties |

### Permissions required
The account you sign in with from Power BI needs **read access to the underlying workspace**,
not just the App Insights blade:

| Permission | Granted by |
|---|---|
| `Microsoft.OperationalInsights/workspaces/query/*/read` | **Log Analytics Reader** built-in role |
| `Microsoft.Insights/components/read` | **Monitoring Reader** built-in role |

Your App Insights resource is almost certainly **workspace-based** (the default since 2020),
which means data physically lives in a Log Analytics workspace. Granting *Reader* on the
App Insights resource alone is a common cause of "query returns no rows" — you also need read
access on the **linked workspace**.

**To find the linked workspace:** Azure Portal → your Application Insights → **Overview** →
look for the **Workspace** field in the top-right properties panel. Click through and confirm
your account has Log Analytics Reader there.

> **Note on TLS:** since July 2025, the Log Analytics and App Insights query APIs require
> **TLS 1.2 or higher**. Current Power BI Desktop uses TLS 1.2 by default; very old builds or
> locked-down machines with TLS 1.2 disabled will fail to connect. Update Power BI Desktop if
> you hit unexplained SSL errors.

### Government cloud (GCC) note
Your tenant is GCC, so the service endpoints differ from commercial. The correct values:

| Purpose | Commercial | US Government |
|---|---|---|
| Power BI service | `app.powerbi.com` | `app.powerbigov.us` |
| Azure Portal | `portal.azure.com` | `portal.azure.us` |
| Query REST API (M query) | `api.applicationinsights.io` | `api.applicationinsights.us` |
| ADX proxy (Kusto connector) | `ade.applicationinsights.io` | `adx.monitor.azure.us` |

⚠️ Note the ADX proxy is **not** a simple `.io` → `.us` swap — the Government host is
`adx.monitor.azure.us`, a completely different name. (Azure operated by 21Vianet uses
`adx.monitor.azure.cn`.)

**Do not hand-type endpoints.** Use the *"Export → Power BI (M query)"* method in
[Step 1.2](#step-12--export-the-m-query) — Azure generates the correct URL for **your** cloud
automatically. This avoids the single most common category of connection failure.

### Data considerations
- **Retention:** Application Insights defaults to **90 days**, but this is **configurable** —
  30, 60, 90, 120, 180, 270, 365, 550 or 730 days. Set it on the linked Log Analytics workspace
  (**Settings → Usage and estimated costs → Data Retention**, or per-table). App Insights tables
  are free for the first 90 days; beyond that, retention incurs a charge. **Increase it before
  you need the history** — data already aged out cannot be recovered.
- **Row limits:** the Log Analytics Query API returns at most **500,000 rows** and ~**64 MB of
  compressed data** (~100 MB raw) per query. Exceeding either fails the query rather than
  silently truncating. Aggregate in KQL rather than importing raw rows where possible.
- **Privacy:** these tables contain `question` text plus `userId` / `userName` / `userEmail`.
  Benefits questions can reveal medical or family circumstances. Restrict access — see
  [Privacy and access control](#privacy-and-access-control).

### Things that work in Desktop but break after publishing

Power BI Desktop runs on your machine; scheduled refresh runs on a Microsoft cloud VM set to
UTC, under a stored credential, with different rules. Several natural-looking choices silently
change behaviour when published — **no error, just wrong data**.

| Trap | Desktop | Service | Covered in |
|---|---|---|---|
| `DateTimeZone.ToLocal` (Transform → Time zone → Local time) | Converts to your local time | Returns **UTC** — conversion does nothing | [Step 2.5](#25--set-data-types-and-add-eventdate) |
| Concatenating a parameter into the `Web.Contents` URL | Works | **Refresh fails** — dynamic data source | [Step 1.7](#step-17--parameterise-the-endpoint-optional) |
| `USERNAME()` in RLS | Returns `DOMAIN\User` | Returns UPN | [Privacy and access control](#privacy-and-access-control) |
| RLS roles | "View as" uses *your* identity | Bypassed entirely for workspace Members/Admins | [Privacy and access control](#privacy-and-access-control) |
| `Date.From` on a `datetimezone` | Uses machine-local date | Uses UTC date | [Step 2.5](#25--set-data-types-and-add-eventdate) |

**Verify after your first scheduled refresh**, not just in Desktop. Compare a KQL count in the
Azure Portal against the same figure in the published report for a fixed date range. If they
disagree, one of the above is the likely cause.

### Confirm sampling is disabled

**This is the single most important prerequisite.** If Application Insights sampling is on,
it stores a *fraction* of events and sets `itemCount` to the sampling multiplier. Every
`COUNTROWS` in this guide would then undercount actual traffic, and no error would surface.

This repository's `host.json` already disables it:

```json
{
  "logging": {
    "applicationInsights": {
      "samplingSettings": { "isEnabled": false, "excludedTypes": "Request" }
    }
  }
}
```

Verify it is actually in effect in the deployed app:

```kql
customEvents
| where timestamp > ago(7d)
| summarize Events = count(), SumItemCount = sum(itemCount) by name
```

✅ **`Events` must equal `SumItemCount`** for every row. If they differ, sampling is active —
either re-deploy with sampling disabled, or use `sum(itemCount)` instead of `count()` in every
KQL query and weight the Power BI measures accordingly.

> **Do not skip this check.** Sampling is enabled by default in Azure Functions, and a
> `host.json` change only takes effect after a successful deployment.

---

## Part 1 — Connect Power BI to Application Insights

There are three ways to connect. **Method A is strongly recommended** and is documented in
full detail; Methods B and C are covered afterwards for specific situations.

| Method | When to use | Mode |
|---|---|---|
| **A — Export M query** (recommended) | Default choice. Endpoint is auto-generated for your cloud. | Import |
| **B — ADX / Kusto connector** | You need DirectQuery / near real-time. | Import or DirectQuery |
| **C — Power BI (new Dataset)** | Quick one-off dataset built in the service. | Import |

---

### Method A — Export the M query (recommended)

#### Step 1.1 — Verify data exists first

**Do this before touching Power BI.** Connecting to an empty query wastes a lot of time.

1. Sign in to the Azure Portal (`portal.azure.us` for GCC).
2. Navigate to your Application Insights resource.
   - Search "Application Insights" in the top bar, or go to
     **Resource groups → TEC-AGENTIC-AI-RG →** your App Insights resource.
   - It's the resource linked to `func-hrbenefit-dev003` via `APPLICATIONINSIGHTS_CONNECTION_STRING`.
3. Left nav → **Monitoring** → **Logs**.
4. Dismiss the "Queries" sample dialog if it opens.
5. Set the time range picker (above the query editor) to **Last 7 days**.
6. Paste and **Run**:

```kql
customEvents
| where timestamp > ago(7d)
| summarize Events = count() by name
| order by Events desc
```

✅ **Expected result:** a table listing `AgentInteraction`, and likely `UserFeedback`,
`EmailSent`, `AgentInteractionFailed`.

❌ **If you get zero rows**, stop and fix ingestion before continuing:

| Cause | Check |
|---|---|
| No traffic yet | Send a test question through the agent, wait 3–5 min |
| Wrong App Insights resource | Compare the connection string in Function App → Settings → Environment variables |
| Ingestion delay | Normal latency is 2–5 minutes; occasionally longer |
| Exporter not initialised | See [Exporter health](#exporter-health) in Part 7 |

> ✅ **`customEvents` ingestion is confirmed working in this environment.** `customEvents` is
> the **only** supported data source for this dashboard. Do not build Power BI queries against
> the `traces` table.

#### Step 1.2 — Export the M query

1. Still in **Logs**, replace the query with the real first table query:

```kql
customEvents
| where timestamp > ago(90d)
| where name == "AgentInteraction"
| extend
    Question          = tostring(customDimensions.question),
    CanAnswer         = tostring(customDimensions.canAnswer),
    AgentName         = tostring(customDimensions.agentName),
    ConversationId    = tostring(customDimensions.conversationId),
    UserId            = tostring(customDimensions.userId),
    UserName          = tostring(customDimensions.userName),
    IsNewConversation = tostring(customDimensions.isNewConversation),
    DurationMs        = todouble(customDimensions.durationMs),
    InputTokens       = todouble(customDimensions.inputTokens),
    OutputTokens      = todouble(customDimensions.outputTokens),
    TotalTokens       = todouble(customDimensions.totalTokens),
    ReasoningTokens   = todouble(customDimensions.reasoningTokens)
| project timestamp, Question, CanAnswer, AgentName, ConversationId, UserId, UserName,
          IsNewConversation, DurationMs, InputTokens, OutputTokens, TotalTokens, ReasoningTokens
```

2. **Run** it and confirm the columns are populated (not all `null`).
3. ⚠️ **Add an explicit time filter to the query text.** The exported M **bakes in** whatever
   the portal time picker was set to, which is invisible once you're in Power BI. Make it
   explicit instead — insert this as the second line, right after `customEvents`:

   ```kql
   | where timestamp > ago(90d)
   ```

   90 days matches the *default* Application Insights retention. If you raise retention, raise
   this filter to match — but keep an explicit bound so the query stays predictable. Without
   it, your dataset silently depends on a UI setting you'll have forgotten about in a month.
4. Toolbar → **Export** ▾ → **Export to Power BI (M query)**.

> **Can't find Export?** It sits in the toolbar above the query editor, next to *Share* and
> *New alert rule*. If the window is narrow it collapses under a **…** overflow menu. It's
> disabled until a query has successfully run.

#### Why numbers are in `customDimensions`

Standard App Insights SDKs split telemetry into two columns: `customDimensions` (strings) and
`customMeasurements` (numbers). **This application does not.**

`track_event()` in `function_app.py` merges measurements into the dimensions dictionary before
sending:

```python
dims = _clean_dimensions(properties)
if measurements:
    dims.update({k: v for k, v in measurements.items() if isinstance(v, (int, float))})
lg.info(name, extra={"custom_dimensions": dims})
```

**Consequences for every query in this guide:**

| | Behaviour |
|---|---|
| `customMeasurements` column | **Always empty.** Never query it. |
| `durationMs`, `*Tokens`, `recipientCount`, `isNegative` | All live in `customDimensions` |
| Extraction | `todouble(customDimensions.<name>)` — no `coalesce` needed |

⚠️ **Do not use `coalesce(customMeasurements.x, customDimensions.x)`.** Both operands are
`dynamic`, and `coalesce` requires compatible scalar types — this can raise a semantic error
rather than gracefully falling back.

> **If you later switch to `azure-monitor-opentelemetry`**, measurements *will* populate
> properly and you'll need to revisit these extractions. The `todouble()` calls would return
> `null` against the new shape.

5. A file named something like `PowerBIQuery.txt` downloads.

#### Step 1.3 — Understand what was exported

Open the `.txt` in Notepad. It looks like this:

```
/*  The exported Power Query Formula Language (M Language) can be used with Power Query in
    Excel and the Power BI Desktop.
    ...
*/

let AnalyticsQuery =
let Source = Json.Document(Web.Contents(
  "https://api.applicationinsights.io/v1/apps/00000000-1111-2222-3333-444444444444/query",
  [Query=[#"query"="customEvents
| where name == ""AgentInteraction""
| project timestamp, Question
",#"x-ms-app"="AAPBI",#"prefer"="ai.response-thinning=true"],Timeout=#duration(0,0,4,0)])),
TypeMap = #table(
  { "AnalyticsTypes", "Type" },
  {
    { "?",       Text.Type },
    { "datetime", DateTimeZone.Type },
    ...
  }),
DataTable = Source[tables]{0},
Columns = Table.FromRecords(DataTable[columns]),
ColumnsWithType = Table.Join(Columns, {"type"}, TypeMap , {"AnalyticsTypes"}),
Rows = Table.FromRows(DataTable[rows], Columns[name]),
Table = Table.TransformColumnTypes(Rows, Table.ToList(ColumnsWithType, (c) => { c{0}, c{3}}))
in
Table
in AnalyticsQuery
```

Key things to note:

| Element | Meaning |
|---|---|
| `https://api.applicationinsights.io/...` | Query endpoint — **already correct for your cloud** |
| `/v1/apps/<GUID>/query` | The GUID is your **Application ID** (App Insights → API Access) |
| `#"query"="..."` | Your KQL. Double quotes are **escaped by doubling** (`""`) |
| `Timeout=#duration(0,0,4,0)` | Client-side timeout: 4 minutes. Raise if needed — the API itself allows up to 10 |
| `TypeMap` / `TransformColumnTypes` | Auto-maps Kusto types to Power BI types |

The `/*  ... */` comment block at the top is **not valid M** — you must exclude it when pasting.

#### Step 1.4 — Paste into Power BI Desktop

1. Open **Power BI Desktop** → close the splash screen.
2. **Home** ribbon → **Get data** ▾ → **Blank query**.
   - The Power Query Editor opens with an empty query named `Query1`.
3. **Home** → **Advanced Editor**.
4. Select all existing text (`Ctrl+A`) and delete it.
5. From the `.txt`, copy **everything starting at `let AnalyticsQuery =`** to the end
   (`in AnalyticsQuery`). **Do not include the `/* ... */` header comment.**
6. Paste into the Advanced Editor.
7. Confirm **"No syntax errors have been detected"** appears at the bottom.
8. Click **Done**.

#### Step 1.5 — Authenticate

Power BI now prompts for credentials (a yellow bar reading *"Please specify how to connect"*).

1. Click **Edit Credentials**.
2. In the left list, select **Organizational account** — ⚠️ **not** Anonymous, not Basic,
   not API key.
3. Click **Sign in** → complete Microsoft Entra sign-in (including MFA).
4. **Important:** in the *"Select which level to apply these settings to"* dropdown, choose the
   **base URL** — `https://api.applicationinsights.io` — rather than the full query URL. This
   makes one credential serve **all** your queries. Choosing the full URL forces you to
   re-authenticate for every table.
5. Click **Connect**.

✅ **Checkpoint:** a data preview appears with `timestamp`, `Question`, `CanAnswer`, etc.

#### Step 1.6 — Name and verify

1. Right pane → **Properties** → **Name** → set it to `AgentInteractions`.
   > Use this exact name. All DAX in [Part 4](#part-4--add-dax-measures) references it, and
   > renaming later silently breaks every measure.
2. Check the column headers show the correct type icons:
   - `timestamp` → 📅 calendar (`DateTimeZone`)
   - `DurationMs`, `*Tokens` → `1.2` (decimal)
   - Text columns → `ABC`
3. Scan the preview for columns that are **entirely `null`** — that means a dimension name
   mismatch. Verify against the [appendix](#appendix--event-reference); names are
   **case-sensitive**.
4. **Do not click Close & Apply yet** — you'll add the remaining queries in Part 2.

#### Step 1.7 — Parameterise the endpoint (optional)

You'll create four queries, each hardcoding the same URL. Extracting it once makes a move to a
different App Insights resource a two-parameter change instead of four hand-edits.

🛑 **This must be done correctly or scheduled refresh will fail after publishing.**

Concatenating a variable directly into the `Web.Contents` URL creates what Power BI calls a
**dynamic data source** — one whose address isn't known until the query runs. Microsoft's
guidance is explicit: *"In most cases, Power BI semantic models that use dynamic data sources
can't be refreshed in the Power BI service."*

It works fine in Desktop. It fails on scheduled refresh. Same trap as the timezone conversion
in [Step 2.5](#25--set-data-types-and-add-eventdate).

**❌ Do not do this:**
```m
Web.Contents( AppInsightsEndpoint & "/v1/apps/" & AppInsightsAppId & "/query", [ ... ] )
```

**✅ Do this instead** — keep the base URL static and move the variable part into
`RelativePath`, which *is* supported for refresh:

```m
Web.Contents(
    AppInsightsEndpoint,
    [
        RelativePath = "v1/apps/" & AppInsightsAppId & "/query",
        Query = [ #"query" = "...your KQL...", #"x-ms-app" = "AAPBI" ],
        Timeout = #duration(0,0,4,0)
    ]
)
```

Microsoft names `RelativePath` and `Query` as the specific exception that allows a
parameterised `Web.Contents` call to refresh in the service.

**Setup:**
1. Power Query Editor → **Home → Manage Parameters → New Parameter**:
   - **Name:** `AppInsightsAppId`, **Type:** Text
   - **Current Value:** your Application ID GUID (App Insights → **Configure → API Access**)
2. **New Parameter** again:
   - **Name:** `AppInsightsEndpoint`, **Type:** Text
   - **Current Value:** `https://api.applicationinsights.io` (or the host from your export)
   - ⚠️ Base URL only — **no path**. The path belongs in `RelativePath`.
3. Rewrite each query's `Web.Contents` call using the shape above.

**Verify before publishing:**
**Data source settings → Data sources in current file**. If you see a warning that the query
references dynamic data sources, refresh **will** fail in the service — fix it now rather than
discovering it after the first scheduled run.

> **Is this worth it?** Only if you expect to repoint the dataset (dev → prod, or a new App
> Insights resource). Otherwise the four hardcoded URLs from **Export → Power BI (M query)**
> are simpler and carry zero refresh risk. **If in doubt, skip this step.**

---

### Method B — Azure Data Explorer (Kusto) connector

Use this **only if you need DirectQuery** (near real-time dashboards without refresh).

1. **Get data** → search **"Azure Data Explorer (Kusto)"** → **Connect**.
2. **Cluster** — enter the ADX proxy URL for your resource:

```
Commercial:
https://ade.applicationinsights.io/subscriptions/<sub-id>/resourcegroups/<rg>/providers/microsoft.insights/components/<ai-name>

US Government:
https://adx.monitor.azure.us/subscriptions/<sub-id>/resourcegroups/<rg>/providers/microsoft.insights/components/<ai-name>
```

For your environment, substitute `<rg>` = `TEC-AGENTIC-AI-RG` and `<ai-name>` = your App
Insights resource name.

3. Leave **Database** blank initially, expand the tree, and pick the database that matches
   your App Insights resource name (⚠️ **case-sensitive**).
4. Optionally paste a KQL query in the box.
5. Choose **Import** or **DirectQuery** → **OK**.
6. Authenticate with **Organizational account**.

**DirectQuery caveats — verified limitations:**

| Limitation | Effect on this dashboard |
|---|---|
| **1,000,000-row intermediate limit** | Any query or intermediate step returning more rows **fails** with `The resultset of a query to external data source has exceeded the maximum allowed size of '1000000' rows` |
| **4-minute query timeout in the service** | Users see an error, not slow results |
| **No automatic date hierarchy** | You already build an explicit date table, so this is fine |
| **Calculated columns limited to row-level expressions** | `EventDate` is fine; the `Topic` column using `SWITCH`/`CONTAINSSTRING` may not fold |
| **`PERCENTILEX.INC` is unsupported in calculated columns / RLS** and behaves poorly generally | `[P95 Response Time (s)]` would need replacing with a KQL-side `percentile()` |
| **Median, TopN and measure filters generate extra queries** | Page 2's `[Answer Rate %] < 0.8` filter and Page 4's Top-N table get materially slower |
| **Every visual interaction fires a live query** | Slower, and subject to Kusto throttling |

**Recommendation: use Import (Method A).** At this data volume DirectQuery buys nothing —
you'd trade working measures and fast visuals for freshness that HR benefits reporting does
not need. Only revisit if you have a hard requirement for sub-refresh-interval latency, and
expect to rewrite several measures if you do.

---

### Method C — Power BI (new Dataset) from the portal

The Logs **Export** menu also offers **Power BI (new Dataset)**, which creates a dataset
directly in the Power BI service — no Desktop required.

**Requires** `Microsoft.OperationalInsights/workspaces/write` (Log Analytics **Contributor**),
because it provisions a linked resource.

Good for a quick single-table dataset. **Not recommended here** — you need four tables, a date
table, relationships and ~25 measures, all of which require Power BI Desktop.

---

### Connection method comparison

| | A: M query | B: Kusto connector | C: New Dataset |
|---|---|---|---|
| Endpoint correctness | ✅ Auto-generated | ⚠️ Hand-typed | ✅ Auto |
| DirectQuery | ❌ | ✅ | ❌ |
| Requires Desktop | ✅ | ✅ | ❌ |
| Permission needed | Reader | Reader | **Contributor** |
| Multi-table modelling | ✅ | ✅ | ❌ |
| **Recommended here** | ✅ **Yes** | Only for real-time | No |

---

## Part 2 — Build the source tables

You already have `AgentInteractions` from [Part 1](#step-16--name-and-verify). Now add three
more queries using the same pattern.

### The workflow for each additional table

**Option 1 — Re-export from the portal (safest, recommended):**
1. Azure Portal → App Insights → **Logs**.
2. Paste the KQL from the relevant section below → **Run** → confirm rows return.
3. **Export → Export to Power BI (M query)**.
4. Power BI → Power Query Editor → **Home → New Source → Blank Query**.
5. **Advanced Editor** → paste (excluding the `/* */` header) → **Done**.
6. Rename the query to the exact name in the heading.

Azure handles the quote-escaping for you. **This is the recommended path.**

**Option 2 — Duplicate and edit in Power BI (faster, but error-prone):**
1. Right-click `AgentInteractions` in the Queries pane → **Duplicate**.
2. **Advanced Editor** → find the `#"query"="..."` value → replace the KQL.
3. ⚠️ **You must escape every double quote by doubling it.** `name == "UserFeedback"` becomes
   `name == ""UserFeedback""`. A single missed quote produces a cryptic
   *"Token Comma expected"* or a 400 from the API.
4. Rename the query.

> **Why the escaping matters:** the KQL lives inside an M string literal. M has no backslash
> escape — it uses doubled quotes. This is the #1 source of hand-editing errors, which is why
> re-exporting is recommended.

⚠️ **Do not change the query name after building measures.** Part 4's DAX references these
names literally.

### 2.1 — `AgentInteractions` ✅ already created
Built in [Step 1.2](#step-12--export-the-m-query). No action needed — the KQL is reproduced
there. Skip to 2.2.

### 2.2 — `UserFeedback`
```kql
customEvents
| where timestamp > ago(90d)
| where name == "UserFeedback"
| extend
    Rating         = tostring(customDimensions.rating),
    RawRating      = tostring(customDimensions.rawRating),
    Comment        = tostring(customDimensions.comment),
    HasComment     = tostring(customDimensions.hasComment),
    Question       = tostring(customDimensions.question),
    ConversationId = tostring(customDimensions.conversationId),
    UserId         = tostring(customDimensions.userId),
    UserName       = tostring(customDimensions.userName),
    UserEmail      = tostring(customDimensions.userEmail),
    IsNegative     = todouble(customDimensions.isNegative)
| project timestamp, Rating, RawRating, Comment, HasComment, Question, ConversationId,
          UserId, UserName, UserEmail, IsNegative
```

### 2.3 — `EmailsSent`
```kql
customEvents
| where timestamp > ago(90d)
| where name == "EmailSent"
| extend
    Question       = tostring(customDimensions.question),
    UserEmail      = tostring(customDimensions.userEmail),
    UserId         = tostring(customDimensions.userId),
    GraphStatus    = tostring(customDimensions.graphStatus),
    UserName       = tostring(customDimensions.userName),
    ConversationId = tostring(customDimensions.conversationId),
    HrAddress      = tostring(customDimensions.hrAddress),
    RecipientCount = todouble(customDimensions.recipientCount)
| project timestamp, Question, UserEmail, UserId, UserName, ConversationId,
          HrAddress, RecipientCount, GraphStatus
```

### 2.4 — `Failures` (optional)

⚠️ **The two failure events have different schemas.** This query unions them, so several
columns are populated for only one event type. That is expected, not a bug:

| Column | `AgentInteractionFailed` | `EmailFailed` |
|---|---|---|
| `Question`, `ErrorText` | ✅ | ✅ |
| `AgentName` | ✅ | ❌ always blank |
| `DurationMs` | ✅ | ❌ always blank |
| `ErrorCode` | ❌ always blank | ✅ Graph HTTP code |
| `ConversationId`, `UserId`, `UserEmail`, `HrAddress` | ❌ always blank | ✅ |

```kql
customEvents
| where timestamp > ago(90d)
| where name in ("AgentInteractionFailed", "EmailFailed")
| extend
    EventType      = name,
    Question       = tostring(customDimensions.question),
    ErrorText      = tostring(customDimensions.error),
    AgentName      = tostring(customDimensions.agentName),
    ErrorCode      = tostring(customDimensions.errorCode),
    ConversationId = tostring(customDimensions.conversationId),
    UserId         = tostring(customDimensions.userId),
    UserEmail      = tostring(customDimensions.userEmail),
    HrAddress      = tostring(customDimensions.hrAddress),
    DurationMs     = todouble(customDimensions.durationMs)
| project timestamp, EventType, Question, ErrorText, AgentName, ErrorCode,
          ConversationId, UserId, UserEmail, HrAddress, DurationMs
```

> **Why union them anyway:** a single "what is broken right now" table is more useful
> operationally than two. If the blank columns bother you, split into two queries instead —
> nothing else in this guide depends on them being combined.

⚠️ **`AgentInteractionFailed` cannot be correlated to a conversation or user.** It emits only
`agentName`, `question`, `error` and `durationMs`. If you need per-user failure analysis, add
`conversationId` and `userId` to that `track_event()` call in `function_app.py` — the values
are in scope at the point it fires.

### 2.5 — Set data types and add `EventDate`

Do all of this in the Power Query Editor **before** loading, for each of the four queries.

**Set the types:**
1. Numeric columns (`DurationMs`, `*Tokens`, `RecipientCount`, `IsNegative`) → **Decimal Number**.
2. Text columns → **Text**.
3. **Leave `timestamp` as `Date/Time/Timezone`** — the type the export already gives it.

> ⚠️ **Do not change `timestamp` to `Date/Time` at this stage.** That strips the timezone
> component, and both `DateTimeZone.SwitchZone` and `DateTimeZone.ToUtc` require a
> `datetimezone` input — `SwitchZone` raises an error outright if the zone is missing. Convert
> the type only *after* any timezone handling below, if at all.

> Explicit types prevent Power BI guessing wrongly on sparse columns. A column that is `null`
> in the first 1,000 preview rows often gets typed as `Text`, which silently breaks `SUM`.

**Timezone handling (read this — the obvious approach does not work):**

⚠️ `timestamp` arrives as UTC. Power BI does **not** convert it automatically. Without a
conversion, daily totals and the hour-of-day chart on
[Page 4](#page-4--cost-and-performance) are shifted by your UTC offset — 4–5 hours for the New
York area, pushing late-afternoon activity into the next day.

🛑 **Do NOT use Transform → Time zone → Local time.** That generates
`DateTimeZone.ToLocal`, which Microsoft documents as behaving differently by environment:

| Environment | `DateTimeZone.ToLocal` returns |
|---|---|
| Power BI **Desktop** | Your machine's local time ✅ |
| Power BI **service** (scheduled refresh) | **UTC — the conversion silently does nothing** ❌ |

This is the worst kind of defect: correct on your machine, silently wrong for everyone after
you publish, with no error. Power BI's cloud refresh VMs run in UTC, so "local" resolves to
UTC there.

**Choose one of these two approaches:**

| Approach | Accuracy | Effort |
|---|---|---|
| **A — Stay in UTC**, label axes "(UTC)" | Exact, just not local | None — ✅ **recommended** |
| **B — Fixed offset** via `DateTimeZone.SwitchZone` | ±1 hour during DST | Low |

> **Recommendation: choose A.** A 4–5 hour shift matters for an hour-of-day chart, but daily
> and weekly aggregates — which is what HR benefits reporting actually uses — are barely
> affected. An honest "(UTC)" axis label costs nothing and cannot silently break after
> publishing.

**If you chose A (UTC):** do nothing here. Skip to *Add the `EventDate` column* below.

**If you chose B (fixed offset):** select `timestamp` → **Add Column → Custom Column**, name it
`TimestampLocal`:

```m
DateTimeZone.SwitchZone([timestamp], -5)
```

⚠️ **A fixed offset does not handle daylight saving.** `-5` is Eastern Standard Time; Eastern
Daylight Time is `-4`. For roughly eight months of the year a fixed `-5` is an hour off. A
DST-aware alternative requires conditional M logic that is exact but brittle to maintain — which
is why approach A is recommended.

**Add the `EventDate` column:**

This is the join key to the date table, and it **must** be created here rather than as a DAX
calculated column — see the note below.

4. Select `timestamp` (or `TimestampLocal`, if you chose approach B).
5. **Add Column → Date → Date Only**.
6. Rename the new column to `EventDate` (double-click the header).
7. Confirm its type icon is a **calendar** (`Date`), not `Date/Time`.

Equivalent M, if you prefer the Advanced Editor:
```m
= Table.AddColumn(#"Previous Step", "EventDate", each Date.From([timestamp]), type date)
```

⚠️ **`Date.From` on a `datetimezone` uses the *local* datetime equivalent** — which means it
carries the same Desktop-vs-service split described above. To make `EventDate` deterministic
across both environments, strip the zone explicitly first:

```m
= Table.AddColumn(
    #"Previous Step",
    "EventDate",
    each Date.From( DateTimeZone.RemoveZone( DateTimeZone.ToUtc([timestamp]) ) ),
    type date
  )
```

`DateTimeZone.ToUtc` is environment-independent (unlike `ToLocal`), so this produces the same
UTC-based date in Desktop and after publishing. If you added a `TimestampLocal` column with an
explicit `SwitchZone` offset, use that column here instead — it is also deterministic.

> ⚠️ **Why not a DAX calculated column?** Power BI's storage engine only uses `DateTime`
> internally — `Date` and `Date/Time/Timezone` are formatting constructs layered on top.
> Changing the model data type to `Date` does **not** strip the time from the engine's view, so
> a relationship to the date table matches nothing. The time must be removed during load.
> (`DATEVALUE()` in DAX is also the wrong tool: it expects a **text** argument, not a datetime
> column.)

Repeat steps 1–7 for all four queries, then **Home → Close & Apply**.

✅ **Checkpoint:** four tables in the Data pane — `AgentInteractions`, `UserFeedback`,
`EmailsSent`, `Failures` — each with an `EventDate` column of type `Date`.

---

## Part 3 — Create the data model

### Step 3.1 — Add a Date table

`EventDate` already exists on all four tables from [Step 2.5](#25--set-data-types-and-add-eventdate).
Now create the shared date dimension. **Modeling → New table**:

```dax
DateTable =
VAR MinDate = MIN ( AgentInteractions[EventDate] )
VAR MaxDate = MAX ( AgentInteractions[EventDate] )
VAR StartDate = IF ( ISBLANK ( MinDate ), TODAY () - 90, DATE ( YEAR ( MinDate ), MONTH ( MinDate ), 1 ) )
VAR EndDate   = IF ( ISBLANK ( MaxDate ), TODAY (), MaxDate )
RETURN
ADDCOLUMNS (
    CALENDAR ( StartDate, EndDate ),
    "Year",        YEAR ( [Date] ),
    "Month",       FORMAT ( [Date], "MMM" ),
    "MonthNumber", MONTH ( [Date] ),
    "YearMonth",   FORMAT ( [Date], "yyyy-MM" ),
    "Day",         DAY ( [Date] ),
    "Weekday",     FORMAT ( [Date], "ddd" ),
    "WeekdayNum",  WEEKDAY ( [Date], 2 )
)
```

**Notes on this definition:**
- `"yyyy-MM"` uses **lowercase `yyyy`** — DAX format strings are case-sensitive, and `"YYYY"`
  does not produce a year.
- The `ISBLANK` guards prevent an error if a table is empty during first build.
- `WEEKDAY(..., 2)` returns Monday = 1.
- It spans only the range present in `AgentInteractions`. If other event tables extend beyond
  that range, their rows fall outside the relationship and vanish from date-filtered visuals.
  Widen `StartDate` / `EndDate` if that happens.

Then:
1. **Table tools → Mark as date table** → **Date column: `Date`** → OK.
2. Select the `Month` column → **Column tools → Sort by column → `MonthNumber`**. Without
   this, charts order months alphabetically (Apr, Aug, Dec…).
   - ⚠️ You must be in **Report view** — the *Column tools* tab is unavailable in Model or
     Table view.
   - This works because each `Month` value maps to exactly one `MonthNumber`. Sort-by-column
     requires that one-to-one mapping and matching granularity; it errors otherwise.

> **On "Mark as date table":** this is required for the *classic* DAX time-intelligence
> functions (`SAMEPERIODLASTYEAR`, `TOTALYTD`, and similar). None of the measures in this guide
> use them, so it is technically optional here — but mark it anyway. It costs nothing, removes
> the auto-generated hidden date tables, and means time-intelligence measures work if you add
> them later.

#### Turn off Auto date/time

⚠️ **Do this — it is on by default and works against you.**

Power BI automatically creates a **hidden date table for every date column** in the model. With
five date/datetime columns across four event tables plus the date table, that is several
redundant hidden tables inflating the model and cluttering the field list with duplicate date
hierarchies.

**Current file only:**
**File → Options and settings → Options → Current File → Data Load** → uncheck
**Auto date/time**.

**For all new files:**
Same dialog → **Global → Data Load** → uncheck **Auto date/time for new files**.

> You have a purpose-built date table, so the automatic ones are pure overhead. Microsoft's own
> guidance is that auto date/time "isn't recommended for more complex scenarios and larger
> models."

### Step 3.2 — Create relationships

**Model view** → drag `DateTable[Date]` onto each event table's `EventDate`:

| From | To | Cardinality | Cross-filter |
|---|---|---|---|
| `DateTable[Date]` | `AgentInteractions[EventDate]` | One-to-many (1:*) | Single |
| `DateTable[Date]` | `UserFeedback[EventDate]` | One-to-many (1:*) | Single |
| `DateTable[Date]` | `EmailsSent[EventDate]` | One-to-many (1:*) | Single |
| `DateTable[Date]` | `Failures[EventDate]` | One-to-many (1:*) | Single |

Double-click each relationship to confirm the cardinality and that it is **Active**.

⚠️ **Do NOT relate event tables to each other on `ConversationId`.** One conversation yields
many interactions, potentially several feedback rows and several emails — a genuine
many-to-many. Power BI would either refuse it or create a bidirectional limited relationship
that produces ambiguous, silently wrong filtering. Cross-event logic lives in the DAX measures
in [Part 4](#escalation-cross-event) instead.

✅ **Checkpoint:** a star schema — `DateTable` in the centre, four event tables radiating out,
no relationships between the event tables.

---

## Part 4 — Add DAX measures

Create a dedicated measures table so measures aren't scattered across data tables:
**Home → Enter data** → name it `Measures` → **Load**. Delete the placeholder `Column1` after
adding your first measure.

For each measure: select the `Measures` table → **Table tools → New measure** → paste →
press Enter.

> **Boolean values are lowercase strings.** `_clean_dimensions()` in `function_app.py`
> converts Python booleans to the literal strings `"true"` / `"false"`. Comparisons are
> **case-sensitive** in DAX — `= "True"` matches nothing. Always use lowercase.

### Volume
```dax
Total Interactions = COUNTROWS ( AgentInteractions ) + 0

Answered = CALCULATE ( [Total Interactions], AgentInteractions[CanAnswer] = "true" )

Unanswered = CALCULATE ( [Total Interactions], AgentInteractions[CanAnswer] = "false" )

Answer Rate % = DIVIDE ( [Answered], [Total Interactions], 0 )

Unique Users =
CALCULATE (
    DISTINCTCOUNT ( AgentInteractions[UserId] ),
    AgentInteractions[UserId] <> ""
)

Conversations =
CALCULATE (
    DISTINCTCOUNT ( AgentInteractions[ConversationId] ),
    AgentInteractions[ConversationId] <> ""
)

New Conversations =
CALCULATE ( [Total Interactions], AgentInteractions[IsNewConversation] = "true" )
```

⚠️ **`Answered` + `Unanswered` may not equal `Total Interactions`.** If `canAnswer` was ever
absent from an event, `CanAnswer` is an empty string and matches neither filter. Verify with:

```kql
customEvents
| where name == "AgentInteraction"
| summarize Rows = count() by CanAnswer = tostring(customDimensions.canAnswer)
```

If a blank bucket appears, add an explicit measure for it rather than letting the numbers
quietly fail to reconcile.

⚠️ **Missing values arrive as empty strings, and they will corrupt distinct counts.**
`_clean_dimensions()` in `function_app.py` **drops** any property whose value is `None`:

```python
if value is None:
    continue
```

The key is therefore absent from `customDimensions`, and `tostring(customDimensions.userId)`
returns `""` rather than null. A plain `DISTINCTCOUNT` counts that empty string as one
additional "user" or "conversation" — which is why the measures above filter `<> ""`.

This matters in practice: Copilot Studio does not always pass `user_id` or `conversation_id`,
so blanks are likely, not hypothetical. Check your exposure with:

```kql
customEvents
| where timestamp > ago(30d)
| where name == "AgentInteraction"
| summarize
    Total       = count(),
    MissingUser = countif(isempty(tostring(customDimensions.userId))),
    MissingConv = countif(isempty(tostring(customDimensions.conversationId)))
```

> **Apply the same `<> ""` guard to any new `DISTINCTCOUNT` measure you add.**

### Performance
```dax
Avg Response Time (s) = DIVIDE ( AVERAGE ( AgentInteractions[DurationMs] ), 1000 )

P95 Response Time (s) =
DIVIDE (
    PERCENTILEX.INC (
        FILTER ( AgentInteractions, NOT ISBLANK ( AgentInteractions[DurationMs] ) ),
        AgentInteractions[DurationMs],
        0.95
    ),
    1000
)

Max Response Time (s) = DIVIDE ( MAX ( AgentInteractions[DurationMs] ), 1000 )
```

⚠️ **The `FILTER` on `P95` is not optional.** `PERCENTILEX.INC` returns an **error** — not a
blank — if it cannot interpolate the requested percentile. Blank `DurationMs` rows make that
outcome more likely, and a single errored measure breaks the whole visual. Filtering blanks out
first avoids it.

> `AVERAGE` and `MAX` ignore blanks automatically, so they need no equivalent guard.

### Tokens and cost

🛑 **You must set the two rate variables before this measure means anything.** The values below
are deliberately zero so an unconfigured dashboard reports `$0.00` rather than a plausible-
looking wrong number.

**Where to get your rates:**
1. Azure Portal → your Foundry / Azure OpenAI resource → **Model deployments** → note the exact
   model and version backing your agent.
2. Look up that model on the
   [Azure OpenAI pricing page](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/).
3. ⚠️ **Check the units.** Most current models are priced **per 1M tokens**; older ones per 1K.
   The measure below expects a **per-1K** rate — divide a per-1M price by 1000.
4. ⚠️ **GCC/Government pricing differs from commercial.** Use your own cloud's rates.

```dax
Total Tokens = SUM ( AgentInteractions[TotalTokens] )

Input Tokens = SUM ( AgentInteractions[InputTokens] )

Output Tokens = SUM ( AgentInteractions[OutputTokens] )

Avg Tokens per Interaction = DIVIDE ( [Total Tokens], [Total Interactions] )

Estimated Cost =
-- 🛑 SET THESE TWO VALUES BEFORE USING THIS MEASURE.
-- Left at 0 the measure correctly reports $0.00 rather than a misleading figure.
-- Use price PER 1,000 TOKENS. If your model is priced per 1M, divide the
-- published rate by 1000 (e.g. $2.50 per 1M  ->  0.0025 per 1K).
VAR InputRatePer1K  = 0
VAR OutputRatePer1K = 0
RETURN
    DIVIDE ( [Input Tokens], 1000 ) * InputRatePer1K
  + DIVIDE ( [Output Tokens], 1000 ) * OutputRatePer1K

Cost per Interaction = DIVIDE ( [Estimated Cost], [Total Interactions] )
```

**Accuracy caveats — state these whenever you share a cost figure:**

| Issue | Effect on the estimate |
|---|---|
| Token counts absent when the API omits `usage` | **Understates** — those interactions contribute zero |
| `cachedInputTokens` bill at a reduced rate but are charged at full rate here | **Overstates** |
| Failed calls consume input tokens but emit no `usage` | **Understates** |
| Input/output rates differ by model, region and cloud | Either direction |

✅ **`reasoningTokens` are already included in `outputTokens`** — per the Responses API schema,
`output_tokens_details.reasoning_tokens` is a *subset* of `output_tokens`, not an addition.
The measure above is therefore correct. **Do not add `reasoningTokens` to the cost formula**;
doing so double-counts them.

> Track `reasoningTokens` separately if you want to see how much of your output spend goes to
> hidden thinking:
> ```dax
> Reasoning Tokens = SUM ( AgentInteractions[ReasoningTokens] )
> Reasoning Share % = DIVIDE ( [Reasoning Tokens], [Output Tokens], 0 )
> ```

Label any visual using this measure **"Estimated"**. It is useful for spotting trends and
outliers — it is **not** a billing reconciliation. Use Azure Cost Management for actuals.

### Feedback
```dax
Total Feedback = COUNTROWS ( UserFeedback ) + 0

Positive Feedback = CALCULATE ( [Total Feedback], UserFeedback[Rating] = "positive" )

Negative Feedback = CALCULATE ( [Total Feedback], UserFeedback[Rating] = "negative" )

Satisfaction % = DIVIDE ( [Positive Feedback], [Total Feedback], 0 )

Feedback Response Rate % = DIVIDE ( [Total Feedback], [Total Interactions], 0 )

Comments Provided = CALCULATE ( [Total Feedback], UserFeedback[HasComment] = "true" )
```

✅ **`Rating` is safe to filter on.** `submit_feedback` normalises ~20 input spellings
(`up`, `yes`, `👍`, `1`, `helpful`, …) down to exactly `"positive"` or `"negative"`, and
rejects anything else with a 400. Only those two values can ever reach App Insights.

> Use `RawRating` only for diagnosing what Copilot Studio is actually sending — never as a
> filter in a measure.

⚠️ **`Feedback Response Rate %` is approximate.** Feedback events and interaction events are
independent; a user may submit feedback for a conversation whose interactions fall outside the
current date filter. Read it as a rough engagement indicator, not an exact ratio.

### Escalation (cross-event)
There is no physical relationship on `ConversationId`, so these use explicit set logic.

```dax
Emails Sent = COUNTROWS ( EmailsSent ) + 0

Escalation Rate % = DIVIDE ( [Emails Sent], [Unanswered], 0 )

Negative Not Escalated =
VAR EmailedConvs =
    CALCULATETABLE (
        VALUES ( EmailsSent[ConversationId] ),
        ALL ( DateTable ),
        EmailsSent[ConversationId] <> ""
    )
VAR NegativeRows =
    FILTER (
        UserFeedback,
        UserFeedback[Rating] = "negative"
            && UserFeedback[ConversationId] <> ""
            && NOT ( UserFeedback[ConversationId] IN EmailedConvs )
    )
RETURN
    COUNTROWS ( NegativeRows ) + 0
```

⚠️ **Three things to understand about `Negative Not Escalated`:**

1. **It uses `FILTER`, not a CALCULATE boolean filter.** `NOT ... IN <table variable>` is not
   valid as a CALCULATE filter argument — it must be wrapped in `FILTER` over the table.
2. **Rows with a blank `ConversationId` are excluded** from both sides. Without the `<> ""`
   guards, every blank-ID feedback row would be counted as "not escalated" because blank never
   matches. Copilot Studio does not always pass a conversation ID.
3. **`ALL ( DateTable )` on the email side is deliberate.** A user might give negative feedback
   on Monday and email HR on Tuesday. Restricting emails to the same date filter would
   incorrectly flag Monday as un-escalated. The measure asks *"was this conversation ever
   escalated?"*, not *"escalated in this period?"*.

⚠️ **`Escalation Rate %` is an approximation.** The denominator is unanswered questions, but
`send_hr_email` can be invoked for **any** question — including ones the agent answered, if the
user was unsatisfied. The rate can therefore exceed 100%. Treat it as a directional signal.

For a precise figure, use this instead:

```dax
Unanswered Conversations Escalated =
VAR EmailedConvs =
    CALCULATETABLE (
        VALUES ( EmailsSent[ConversationId] ),
        ALL ( DateTable ),
        EmailsSent[ConversationId] <> ""
    )
VAR UnansweredConvs =
    CALCULATETABLE (
        VALUES ( AgentInteractions[ConversationId] ),
        AgentInteractions[CanAnswer] = "false",
        AgentInteractions[ConversationId] <> ""
    )
RETURN
    COUNTROWS ( INTERSECT ( UnansweredConvs, EmailedConvs ) ) + 0
```

⚠️ **`INTERSECT` is not commutative — the argument order matters.** It returns rows from the
*first* table that also appear in the second, **retaining duplicates from the first**. Here
both arguments come from `VALUES`, which returns distinct values, so there are no duplicates to
inflate the count. If you adapt this measure to use a raw table instead of `VALUES`, put the
already-deduplicated set first or you will over-count.

> `INTERSECT` compares columns **by position, with no type coercion**. Both arguments here are
> single-column `ConversationId` tables, so they align correctly.

### Failures
```dax
Total Failures = COUNTROWS ( Failures ) + 0

Agent Failures = CALCULATE ( [Total Failures], Failures[EventType] = "AgentInteractionFailed" )

Email Failures = CALCULATE ( [Total Failures], Failures[EventType] = "EmailFailed" )

Agent Failure Rate % =
DIVIDE ( [Agent Failures], [Total Interactions] + [Agent Failures], 0 )

Email Failure Rate % =
DIVIDE ( [Email Failures], [Emails Sent] + [Email Failures], 0 )
```

⚠️ **Do not compute a single blended failure rate.** `Failures` unions two unrelated
operations — an agent call failing and a Graph `sendMail` failing. Dividing the combined count
by `[Total Interactions]` inflates the figure, because email failures are not agent
interactions. The two rates above each use their own correct denominator.

> **Why `+ 0`:** `COUNTROWS` returns `BLANK()` — not zero — when nothing matches. Cards then
> render empty instead of "0", and arithmetic against blanks propagates blanks. Adding zero
> forces a numeric result.

### Formatting
Select each `%` measure → **Measure tools** → **Format: Percentage**, 1 decimal.
Format `Estimated Cost` as **Currency**, 2–4 decimals.

---

## Part 5 — Build the report pages

### Page 1 — Executive summary

**KPI cards** (Visualizations → *Card*), one per measure:
- `[Total Interactions]`
- `[Answer Rate %]`
- `[Satisfaction %]`
- `[Unique Users]`
- `[Estimated Cost]`
- `[Avg Response Time (s)]`

**Line chart — Volume and answer rate over time**
- X-axis: `DateTable[Date]`
- Y-axis: `[Total Interactions]`
- Secondary line (use *Line and stacked column chart*): `[Answer Rate %]`

**Donut — Answered vs unanswered**
- Legend: `AgentInteractions[CanAnswer]`
- Values: `[Total Interactions]`

**Slicers** (add to every page):
- `DateTable[Date]` → *Between* slicer

⚠️ **Only slice on `DateTable`.** A slicer built from `AgentInteractions[UserName]` filters
**only** that table — feedback and email visuals on the same page would ignore it, because the
event tables are deliberately unrelated ([Step 3.2](#step-32--create-relationships)). This
produces a page where the numbers appear inconsistent.

> **If you need a cross-table user slicer**, create a shared dimension: **Modeling → New
> table** with
> ```dax
> Users =
> FILTER (
>     DISTINCT (
>         UNION (
>             SELECTCOLUMNS ( AgentInteractions, "UserId", AgentInteractions[UserId] ),
>             SELECTCOLUMNS ( UserFeedback,      "UserId", UserFeedback[UserId] ),
>             SELECTCOLUMNS ( EmailsSent,        "UserId", EmailsSent[UserId] )
>         )
>     ),
>     [UserId] <> ""
> )
> ```
> The `FILTER` is required — without it the blank `UserId` becomes a slicer entry that
> aggregates every anonymous interaction under one meaningless member.
>
> Then relate `Users[UserId]` one-to-many to each event table and slice on that. This is
> optional — skip it unless per-user filtering is a stated requirement.

### Page 2 — Content gaps

**Table — Most frequent unanswered questions**
- Columns: `AgentInteractions[Question]`, `[Unanswered]`
- Sort by `[Unanswered]` descending
- No visual-level filter needed — `[Unanswered]` already restricts to `CanAnswer = "false"`

> Do **not** also apply a `CanAnswer is false` visual filter alongside `[Answer Rate %]`. The
> two contradict each other: the filter forces the rate to 0% for every row, making the column
> meaningless.

**Table — Popular questions with a low success rate**
- Columns: `AgentInteractions[Question]`, `[Total Interactions]`, `[Answered]`, `[Answer Rate %]`
- **No** `CanAnswer` filter — this view deliberately spans both outcomes
- Visual-level filters: `[Total Interactions]` **is greater than or equal to** 3,
  and `[Answer Rate %]` **is less than** 0.8

> ⚠️ Filtering on a measure ( `[Answer Rate %] < 0.8` ) is applied *after* aggregation. Power BI
> supports this, but it can be slow on large tables. If the visual is sluggish, raise the
> `[Total Interactions]` threshold first — it prunes the row set before the rate is evaluated.

**Cards:** `[Unanswered]`, `[Answer Rate %]`

> ⚠️ **Questions are free text and will not group.** "dental coverage?" and "Dental coverage"
> are separate rows, so these tables show *literal repeats only*. Real questions rarely repeat
> verbatim, so this page may look sparse. See
> [Grouping similar questions](#grouping-similar-questions) — for most workloads the `Topic`
> bucketing approach is far more useful than the raw question list.

### Page 3 — User feedback

**KPI cards:** `[Total Feedback]`, `[Satisfaction %]`, `[Negative Feedback]`,
`[Feedback Response Rate %]`

**Line chart — Satisfaction over time**
- X-axis: `DateTable[Date]`, Y-axis: `[Satisfaction %]`

**Table — Negative feedback review queue**
- Columns: `UserFeedback[timestamp]`, `Question`, `Comment`, `UserName`
- Filter: `Rating` **is** `negative`
- Sort by timestamp descending

**Card:** `[Negative Not Escalated]` — dissatisfied users who never reached HR

**Stacked bar — Feedback by user**
- Y-axis: `UserFeedback[UserName]`, X-axis: `[Total Feedback]`, Legend: `UserFeedback[Rating]`
- Both fields come from `UserFeedback`, so this visual is self-consistent

### Page 4 — Cost and performance

**Cards:** `[Estimated Cost]`, `[Total Tokens]`, `[Cost per Interaction]`,
`[P95 Response Time (s)]`

**Column chart — Daily token consumption**
- X-axis: `DateTable[Date]`
- Y-axis: `[Input Tokens]`, `[Output Tokens]` (stacked)

**Line chart — Response time trend**
- X-axis: `DateTable[Date]`
- Y-axis: `[Avg Response Time (s)]`, `[P95 Response Time (s)]`

**Table — Most expensive interactions**
- Columns: `AgentInteractions[timestamp]`, `Question`, `TotalTokens`, `DurationMs`
- ⚠️ For each numeric column, click its dropdown in the *Columns* well and set
  **Don't summarize** — otherwise Power BI sums them per distinct question and the "most
  expensive single interaction" becomes a total.
- Filter: **Top N** = 25 **by** `TotalTokens`

**Column chart — Peak usage hours**
1. Add a calculated column to `AgentInteractions`:
```dax
HourOfDay = HOUR ( AgentInteractions[timestamp] )
```
2. X-axis: `HourOfDay` (set to **Don't summarize**), Y-axis: `[Total Interactions]`

⚠️ **This reads whatever timezone `timestamp` carries — UTC by default.** A 9am ET peak appears
at 13:00 or 14:00. Per [Step 2.5](#25--set-data-types-and-add-eventdate), the recommended
approach is to stay in UTC and **rename the axis to "Hour (UTC)"** rather than attempt a
conversion that breaks after publishing.

If you did add a `TimestampLocal` column, build the calculated column from that instead:
```dax
HourOfDay = HOUR ( AgentInteractions[TimestampLocal] )
```

### Page 5 — Escalations and errors

**Cards:** `[Emails Sent]`, `[Escalation Rate %]`, `[Agent Failures]`,
`[Agent Failure Rate %]`, `[Email Failures]`, `[Email Failure Rate %]`

**Table — Recent escalations**
- Columns: `EmailsSent[timestamp]`, `Question`, `UserName`, `HrAddress`, `RecipientCount`

**Table — Recent failures**
- Columns: `Failures[timestamp]`, `EventType`, `ErrorCode`, `ErrorText`, `Question`
- Sort by `timestamp` descending
- ⚠️ `ErrorCode` is blank for `AgentInteractionFailed` rows and `DurationMs` is blank for
  `EmailFailed` rows — see [2.4](#24--failures-optional). Add `EventType` as a legend or
  filter so readers understand why.

**Column chart — Failures by type**
- X-axis: `Failures[EventType]`, Y-axis: `[Total Failures]`

---

## Part 6 — Publish and schedule refresh

### Step 6.1 — Publish
1. **Home → Publish** → choose a workspace.
2. Open the report in the Power BI service (`app.powerbigov.us` for GCC).

### Step 6.2 — Configure refresh
1. Workspace → **Semantic models** (formerly *Datasets*) → your model → **Settings**.
2. **Data source credentials** → **Edit credentials** →
   Authentication method: **OAuth2** → sign in → **Sign in**.
3. **Scheduled refresh** → **On** → set a frequency.
   - Pro / shared capacity: up to **8 scheduled refreshes/day**
   - PPU / Premium / Fabric capacity: up to **48/day**
   - Daily is ample for HR benefits reporting.
   - Manual **Refresh now** does *not* count against the 8/day quota; API-triggered refreshes
     do.
4. Enable **Send refresh failure notifications** so a broken credential surfaces immediately.
   Add a team alias under **Email these contacts when the refresh fails** — otherwise only the
   model owner is told.

> **No gateway required.** The Application Insights REST API is a cloud data source, so Power
> BI connects to it directly.

⚠️ **Refresh is disabled after 4 consecutive failures.** Power BI stops trying and emails the
owner. Fix the cause, then re-enable the schedule manually — it does not resume on its own.

⚠️ **Scheduled refresh is paused after 2 months of inactivity.** If nobody opens a report or
dashboard built on the model, Power BI pauses the schedule and emails the owner. This is a
realistic risk for a dashboard that is only consulted quarterly. To resume, open any report
built on the model, then re-enable the schedule.

⚠️ **Refresh must complete within 2 hours** on shared capacity (5 hours on Premium). Not a
concern at this data volume, but relevant if you later widen the time window substantially.

⚠️ **The dataset is a rolling window, not an archive.** Each refresh re-runs
`| where timestamp > ago(90d)` and **replaces** the data — it does not accumulate. Once an
event ages past Application Insights retention it is gone permanently. If you need multi-year
trends, **increase the workspace retention now** (up to 730 days); it cannot be applied
retroactively.

⚠️ **Credentials are per-user and will eventually expire.** Refresh runs under the identity
that configured it. If that person leaves or their token is revoked, refresh fails — surfaced
only by the notification email. For a shared report, configure it with a service or team
account rather than a personal one.

> **If you parameterised the endpoint** ([Step 1.7](#step-17--parameterise-the-endpoint-optional)),
> the parameter values are also editable in the service under **Settings → Parameters** —
> useful for repointing dev → prod without republishing.

### Step 6.3 — Create a dashboard (optional)
Reports and dashboards are different objects in Power BI:
1. Open the report → hover a visual → **📌 Pin visual**.
2. Pin to a **New dashboard** → name it *HR Benefits Agent*.
3. Repeat for your key KPIs.

Dashboards are single-page and good for at-a-glance monitoring; reports are for exploration.

### Privacy and access control

⚠️ **This dataset is sensitive.** It contains employees' benefits questions — potentially
about medical conditions, dependants, or family circumstances — joined to `userName` and
`userEmail`. Treat access as an HR data matter, not a BI convenience.

**Do this first, before any RLS work:**

1. **Restrict workspace membership** to the smallest possible group. Workspace access
   overrides everything else — a Member or Admin sees all rows regardless of RLS.
2. **Share via an App**, not by granting workspace access, for wider read-only distribution.
3. **Confirm the retention period** meets your HR data-handling policy.
4. **Consider dropping `Question` entirely** from any widely-shared page. Aggregate counts and
   the `Topic` bucket are usually sufficient for management reporting; the raw text is only
   needed for the content-gap review queue.

**Row-level security (optional):**

RLS restricts rows *within* a report for users who have read access.

🛑 **Read this before relying on RLS — it does not apply to most workspace members.**

RLS is enforced **only** for users assigned the workspace **Viewer** role (or who access the
report through an App). Anyone with **Admin**, **Member**, or **Contributor** has edit
permission on the semantic model, and **RLS is bypassed entirely for them** — they see every
row regardless of any role you define.

So if your HR analytics team are all workspace Members, adding RLS changes nothing. Restricting
workspace membership is the control that actually works; RLS only layers on top of it.

1. **Modeling → Manage roles → Create** → name it, e.g. `OwnDataOnly`.
2. Add a DAX filter on the relevant table:

```dax
[UserEmail] = USERPRINCIPALNAME()
```

⚠️ **Match on UPN, not display name.** `USERPRINCIPALNAME()` returns the signed-in user's UPN
(e.g. `jsmith@panynj.gov`). Comparing it to `UserName` — a display name like "John Smith" —
matches nothing, and the user sees an empty report with no error.

⚠️ **UPN is not always the same as the email address.** Microsoft's guidance is explicit: the
value returned is the *sign-in identifier*, which can differ from the `mail` attribute when a
user has an email alias. Your `userEmail` dimension comes from Copilot Studio, so confirm it
carries UPNs before trusting the match.

⚠️ **`USERPRINCIPALNAME()` and `USERNAME()` return the same value in the Power BI service**
(both return the UPN) but differ in Power BI **Desktop**, where `USERNAME()` returns
`DOMAIN\User`. Use `USERPRINCIPALNAME()` for consistent behaviour across both.

⚠️ **`AgentInteractions` has no `UserEmail` column.** Only `UserFeedback` and `EmailsSent`
capture email. To apply RLS across all tables you must either add `userEmail` to the
`AgentInteraction` event in `function_app.py`, or filter on `UserId` if that value is a UPN in
your Copilot Studio configuration. **Verify which** before relying on RLS:

```kql
customEvents
| where name == "AgentInteraction"
| project UserId = tostring(customDimensions.userId)
| take 20
```

3. **View as** (Modeling ribbon) to test the role before publishing.
4. Assign users to the role in the service: semantic model → **Security**.
5. ⚠️ **Confirm those users are workspace Viewers**, not Members — otherwise the role has no
   effect.

> **Test with a real account, not just "View as".** The *Test as role* feature evaluates
> `USERPRINCIPALNAME()` using **your own** identity, so it cannot reveal a UPN mismatch for
> another user. Have an actual Viewer open the report and confirm they see the expected rows.

> RLS is not a substitute for workspace hygiene. If the audience is "HR analytics team only",
> a restricted workspace is simpler and far less likely to fail open.

---

## Part 7 — Troubleshooting

### Connection and authentication errors

| Error message | Cause | Fix |
|---|---|---|
| `We couldn't authenticate with the credentials provided` | Wrong auth type selected | **Data source settings** → find the App Insights URL → **Edit Permissions** → **Credentials: Organizational account** → Sign in |
| `Access to the resource is forbidden` (403) | Account lacks read on the **linked Log Analytics workspace** | Grant **Log Analytics Reader** on the workspace, not just the App Insights resource. See [Permissions required](#permissions-required) |
| `The remote name could not be resolved` | Wrong cloud endpoint (commercial URL in GCC) | Re-export the M query from **your** portal (`portal.azure.us`). See [Government cloud note](#government-cloud-gcc-note) |
| `The underlying connection was closed` / SSL errors | TLS 1.2 not enabled, or corporate proxy TLS interception | Update Power BI Desktop. Your environment has a known TLS-intercepting proxy — may need a firewall exception for `*.applicationinsights.io` / `.us` |
| `Token Comma expected` in Advanced Editor | Unescaped `"` in hand-edited KQL | Double every quote (`""`), or re-export from the portal |
| `Expression.SyntaxError` on paste | Included the `/* ... */` header comment | Paste only from `let AnalyticsQuery =` onward |
| `(400) Bad Request` | Invalid KQL inside the M string | Run the raw KQL in the Portal first to validate it |
| `(404) Not Found` | Wrong Application ID GUID | App Insights → **Configure → API Access** → copy *Application ID* |
| Credentials prompt on **every** query | Credential scoped to the full URL | Data source settings → delete the entry → re-add, selecting the **base URL** level ([Step 1.5](#step-15--authenticate)) |
| `Query timed out` | Exceeded the 4-minute client timeout in the M script | Narrow the time range or aggregate in KQL. If the query legitimately needs longer, raise `Timeout=#duration(0,0,4,0)` — e.g. to `(0,0,9,0)`. The API's own ceiling is 10 minutes |

### Diagnosing a failing connection

Work through this in order — each step isolates a different layer:

1. **Does the KQL work in the Portal?** If not, it's a query problem, not a Power BI problem.
2. **Is the Application ID correct?** App Insights → **Configure → API Access**. The GUID in
   your M must match exactly.
3. **Test the endpoint in a browser.** Paste the query URL — a 401/403 response proves DNS and
   TLS are working. A DNS failure means the wrong cloud endpoint.
4. **Check credential scope.** **File → Options and settings → Data source settings** → select
   the entry → **Edit Permissions**.
5. **Clear and re-authenticate.** Delete the data source entry entirely, then re-run the query.

### Exporter health

Reference only — `customEvents` ingestion is confirmed working in this environment. Use this
if `customEvents` ever stops receiving new rows while the Function App is otherwise healthy.

`track_event()` writes to `customEvents` only when the `opencensus` exporter initialises. If it
fails, the code degrades to a plain trace line beginning with `EVENT` and `customEvents`
receives nothing — with no error surfaced by the app.

```kql
traces
| where timestamp > ago(1d)
| where message startswith "EVENT "
   or message has_any ("Custom event exporter unavailable",
                       "APPLICATIONINSIGHTS_CONNECTION_STRING not set",
                       "track_event failed")
| project timestamp, message
| order by timestamp desc
```

Any rows returned indicate the exporter is not writing to `customEvents`. Usual causes:
`opencensus-ext-azure` missing from the deployed `requirements.txt`, or
`APPLICATIONINSIGHTS_CONNECTION_STRING` unset on the Function App.

⚠️ **This is a diagnostic only — never a Power BI data source.** Fix the exporter and let the
data land in `customEvents`. Do not point Power BI at `traces` and parse JSON out of message
strings: it is fragile, unversioned, and every query and measure in this guide assumes
`customEvents`.

### Data and modelling issues

| Symptom | Likely cause | Fix |
|---|---|---|
| Query returns 0 rows | Time range, no traffic, or the exporter stopped writing | Validate in the Portal first ([Step 1.1](#step-11--verify-data-exists-first)); then check [Exporter health](#exporter-health) |
| Columns are all `null` | Dimension name mismatch | Names are **case-sensitive** — verify against the [appendix](#appendix--event-reference) |
| Numeric columns blank | Reading from `customMeasurements` | This app writes **all** numerics into `customDimensions` — see [Why numbers are in customDimensions](#why-numbers-are-in-customdimensions) |
| `E_QUERY_RESULT_SET_TOO_LARGE` / "result set has exceeded the internal record count limit" | More than 500,000 rows or ~64 MB returned | Narrow the time range, `project` away unused columns, or aggregate with `summarize` in KQL |
| Data older than 90 days missing | Default App Insights retention | Increase retention on the linked workspace (up to 730 days). ⚠️ Applies going forward only — aged-out data is unrecoverable |
| Refresh fails in the service | Expired credentials | Dataset settings → re-enter data source credentials |
| Measures break after renaming a query | DAX references literal table names | Rename back, or update every affected measure |

### Grouping similar questions

⚠️ **Read this before building Page 2.** Free-text questions almost never repeat verbatim, so
a "top questions" table typically shows a long list of count-1 rows and looks broken. Grouping
is what makes content-gap analysis actually work.

Options, cheapest first:

**1. Normalise in KQL** — collapses trivial variations (casing, stray whitespace):
```kql
| extend QuestionKey = trim(@"[\s\?\.!]+", tolower(Question))
```
Helps with "Dental coverage?" vs "dental coverage", but not with genuine rewording. Low effort,
low payoff.

**2. Keyword buckets (recommended)** — add a calculated column to `AgentInteractions`:
```dax
Topic =
VAR Q = AgentInteractions[Question]
RETURN
SWITCH (
    TRUE (),
    CONTAINSSTRING ( Q, "dental" ),                                  "Dental",
    CONTAINSSTRING ( Q, "vision" ) || CONTAINSSTRING ( Q, "eye" ),   "Vision",
    CONTAINSSTRING ( Q, "premium" ) || CONTAINSSTRING ( Q, "cost" ), "Premiums & cost",
    CONTAINSSTRING ( Q, "enroll" ) || CONTAINSSTRING ( Q, "signup" ),"Enrollment",
    CONTAINSSTRING ( Q, "depend" ) || CONTAINSSTRING ( Q, "spouse" ),"Dependants",
    CONTAINSSTRING ( Q, "401" ) || CONTAINSSTRING ( Q, "retire" ),   "Retirement",
    CONTAINSSTRING ( Q, "leave" ) || CONTAINSSTRING ( Q, "fmla" ),   "Leave",
    "Other"
)
```

**Notes on `CONTAINSSTRING`:**
- It is **already case-insensitive**, so no `LOWER()` wrapper is needed — "Dental", "dental"
  and "DENTAL" all match `"dental"`.
- ⚠️ It treats `?` and `*` as **wildcards**. A search term containing them behaves unexpectedly;
  escape with `~` (e.g. `"~*"`) if you ever need a literal.
- Use `CONTAINSSTRINGEXACT` if you deliberately want case-sensitive matching.
- Order matters: `SWITCH` returns the **first** match, so put narrower rules above broader ones.

Then build Page 2 around `Topic` rather than `Question`:
- Bar chart: `Topic` × `[Total Interactions]`, with `[Answer Rate %]` as a second value
- This immediately shows *which benefit areas the agent is weakest on* — the actionable insight

⚠️ **Tune the keyword list to your actual content.** The buckets above are illustrative. Run
this to see what people really ask, then write rules that fit:
```kql
customEvents
| where timestamp > ago(30d)
| where name == "AgentInteraction"
| where tostring(customDimensions.canAnswer) == "false"
| project Question = tostring(customDimensions.question)
| take 200
```

> **Watch the "Other" bucket.** If it exceeds ~30% of rows, your rules are too narrow and the
> chart is misleading. Review what landed there and add rules.

**3. Cluster upstream** — have the Function emit a `topic` dimension at write time (from the
agent's own classification). Most accurate and avoids per-report maintenance, but requires a
code change to `function_app.py`.

### Import vs DirectQuery
| | Import (default) | DirectQuery (Kusto connector) |
|---|---|---|
| Speed | Fast — data is in memory | Slower; every interaction queries Kusto |
| Freshness | As of last refresh | Near real-time |
| Row limits | 1 GB model on shared capacity | **1,000,000-row** query limit; exceeding it errors |
| Timeout | 2-hour refresh window | **4 minutes** per query in the service |
| DAX support | Full | Restricted — see [Method B](#method-b--azure-data-explorer-kusto-connector) |
| Measures in this guide | All work | `[P95 Response Time (s)]` needs rewriting |
| Recommended | ✅ **Yes, for this dashboard** | Only for a hard real-time requirement |

---

## Appendix — event reference

Exact names emitted by `function_app.py` (case-sensitive).

### `AgentInteraction` — every agent call
| Dimension | Type | Notes |
|---|---|---|
| `question` | text | Always captured |
| `canAnswer` | text | `"true"` / `"false"` |
| `agentName` | text | |
| `conversationId` | text | Join key |
| `userId`, `userName` | text | |
| `isNewConversation` | text | `"true"` / `"false"` |
| `durationMs` | number | Wall-clock time for the agent call |
| `inputTokens`, `outputTokens`, `totalTokens` | number | Only when the API returns `usage` |
| `reasoningTokens` | number | Reasoning models only. **Subset of `outputTokens`** |
| `cachedInputTokens` | number | Subset of `inputTokens`; billed at a lower rate |

### `UserFeedback` — thumbs up/down
| Dimension | Notes |
|---|---|
| `rating` | Exactly `"positive"` or `"negative"` — safe to filter on |
| `rawRating` | The unnormalised value as submitted; diagnostics only |
| `comment` | Free text. Present only when the user typed one |
| `hasComment` | `"true"` / `"false"` |
| `question` | **Negative feedback only** — blank for positive |
| `conversationId`, `userId`, `userName`, `userEmail` | May be blank if the flow omits them |
| `isNegative` | Numeric 1/0. Lands in `customDimensions` |

### `EmailSent` / `EmailFailed`
| Dimension | Notes |
|---|---|
| `question`, `userEmail`, `userId`, `userName` | |
| `conversationId` | |
| `hrAddress` | All recipients joined with **`", "`** (comma-space) |
| `graphStatus` | `EmailSent` only — the Graph HTTP status (202) |
| `recipientCount` | Numeric. `EmailSent` only. Lands in `customDimensions` |
| `errorCode`, `error` | `EmailFailed` only |

> `EmailFailed` emits `userId` but **not** `userName`, and has no `graphStatus` or
> `recipientCount`. `EmailSent` has no `errorCode` or `error`.

### `AgentInteractionFailed`
Emitted when the agent call raises. **Minimal schema — note what is absent.**

| Dimension | Notes |
|---|---|
| `agentName` | |
| `question` | The question that triggered the failure |
| `error` | Exception text, truncated to 2000 chars |
| `durationMs` | Numeric. Time until the failure |

⚠️ **No `conversationId`, `userId`, `userName` or `errorCode`.** These failures cannot be
joined to a user or conversation, so `[Agent Failure Rate %]` is a global metric only.

---

### Two rules that govern every query in this guide

1. **Booleans are the lowercase strings `"true"` / `"false"`.** `_clean_dimensions()` converts
   Python bools before sending. Comparisons are case-sensitive in both KQL and DAX.
2. **All numerics live in `customDimensions`, never `customMeasurements`.** `track_event()`
   merges measurements into the dimensions dictionary. See
   [Why numbers are in customDimensions](#why-numbers-are-in-customdimensions).

> **If `function_app.py` changes** — particularly `track_event()`, `_clean_dimensions()`, or
> `extract_token_usage()` — re-verify this appendix. These queries are coupled to the exact
> dimension names and types emitted there.

