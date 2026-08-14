# Power BI Dashboard Guide (Application Insights custom events)

How to build a Power BI dashboard over the custom events emitted by the Azure Function —
agent interactions, user feedback, HR email escalations, and token cost.

**Prerequisites:** telemetry is flowing (see
[ANALYTICS_KQL_QUERIES.md](./ANALYTICS_KQL_QUERIES.md)) and `customEvents` returns rows.

**Time required:** 90–120 minutes for the full dashboard.

---

## Table of contents
- [Before you begin](#before-you-begin)
- [Part 1 — Connect Power BI to Application Insights](#part-1--connect-power-bi-to-application-insights)
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
| **Power BI Desktop** | Latest version, installed locally |
| **Power BI licence** | Pro (or PPU/Premium) to publish and share |
| **Reader access** to the Application Insights resource | To query the data |
| Application Insights **resource name**, **subscription ID**, **resource group** | From the Azure Portal → your App Insights → Overview / Properties |

### ⚠️ Government cloud (GCC) note
Your tenant is GCC, so the service endpoints differ from commercial:

| Cloud | Power BI | App Insights query endpoint |
|---|---|---|
| Commercial | `app.powerbi.com` | `api.applicationinsights.io` / `ade.applicationinsights.io` |
| US Government | `app.powerbigov.us` | US Gov equivalents (`.us` domains) |

**Do not hand-type endpoints.** Use the *"Export → Power BI (M query)"* method in Part 1 —
Azure generates the correct URL for **your** cloud automatically. This avoids a whole class
of connection failures.

### ⚠️ Data considerations
- **Retention:** App Insights defaults to **90 days**. Longer trends need
  [continuous export](https://learn.microsoft.com/azure/azure-monitor/) to storage,
  or a Power BI dataset that accumulates history.
- **Row limits:** Analytics queries cap results (~500k rows / 64 MB). Aggregate in KQL
  rather than importing raw rows where possible.
- **Privacy:** these tables contain `question` text plus `userId` / `userName` / `userEmail`.
  Restrict who can access the report — see [Part 6](#row-level-security-optional).

---

## Part 1 — Connect Power BI to Application Insights

The most reliable method is to let Azure generate the M query.

### Step 1.1 — Get the generated M query
1. Azure Portal → your **Application Insights** resource → **Logs**.
2. Paste this query and **Run** it (confirm it returns rows):
```kql
customEvents
| where name == "AgentInteraction"
| take 10
```
3. Click **Export** (toolbar) → **Export to Power BI (M query)**.
4. A `.txt` file downloads. Open it — it looks like:

```
/*  The exported Power Query Formula Language (M Language)  ... */

let AnalyticsQuery =
let Source = Json.Document(Web.Contents(
  "https://api.applicationinsights.io/v1/apps/<APP_ID>/query",
  [Query=[#"query"="customEvents | where name == ""AgentInteraction"" | take 10",#"x-ms-app"="AAPBI"],
   Timeout=#duration(0,0,4,0)])),
...
```

5. **Copy the whole thing** — and note the `https://...` endpoint, which is correct for your
   cloud. You'll reuse this shape for every table.

### Step 1.2 — Create the first query in Power BI Desktop
1. Open **Power BI Desktop** → **Get data** → **Blank query**.
2. **Home** → **Advanced Editor**.
3. Delete the placeholder, paste the exported M, click **Done**.
4. When prompted for credentials, choose **Organizational account** → **Sign in** → **Connect**.
5. Rename the query (right pane → **Name**) to `AgentInteractions`.

✅ **Checkpoint:** a table preview appears with a `timestamp` column.

> **Alternative:** the **Azure Data Explorer (Kusto)** connector also works, pointing at
> `https://ade.applicationinsights.io/subscriptions/<sub>/resourcegroups/<rg>/providers/microsoft.insights/components/<name>`
> (swap for your cloud's domain). It supports **DirectQuery**, but the M-query route is
> simpler to get right the first time.

---

## Part 2 — Build the source tables

Create one query per event type. For each: **Home → Advanced Editor → New query**, paste the
exported M shape, and swap in the KQL below.

> **How to swap the query:** inside the M, find the `#"query"="..."` value and replace it.
> Remember M escapes double quotes by **doubling** them (`""`), so `tostring(x)` stays plain
> but `== "true"` becomes `== ""true""`.
>
> **Easier approach:** run each KQL in the Azure Portal first, then use
> **Export → Power BI (M query)** again. Azure handles the escaping for you.

### 2.1 — `AgentInteractions`
```kql
customEvents
| where name == "AgentInteraction"
| extend
	Question          = tostring(customDimensions.question),
	CanAnswer         = tostring(customDimensions.canAnswer),
	AgentName         = tostring(customDimensions.agentName),
	ConversationId    = tostring(customDimensions.conversationId),
	UserId            = tostring(customDimensions.userId),
	UserName          = tostring(customDimensions.userName),
	IsNewConversation = tostring(customDimensions.isNewConversation),
	DurationMs        = todouble(coalesce(customMeasurements.durationMs,      customDimensions.durationMs)),
	InputTokens       = todouble(coalesce(customMeasurements.inputTokens,     customDimensions.inputTokens)),
	OutputTokens      = todouble(coalesce(customMeasurements.outputTokens,    customDimensions.outputTokens)),
	TotalTokens       = todouble(coalesce(customMeasurements.totalTokens,     customDimensions.totalTokens)),
	ReasoningTokens   = todouble(coalesce(customMeasurements.reasoningTokens, customDimensions.reasoningTokens))
| project timestamp, Question, CanAnswer, AgentName, ConversationId, UserId, UserName,
		  IsNewConversation, DurationMs, InputTokens, OutputTokens, TotalTokens, ReasoningTokens
```

### 2.2 — `UserFeedback`
```kql
customEvents
| where name == "UserFeedback"
| extend
	Rating         = tostring(customDimensions.rating),
	Comment        = tostring(customDimensions.comment),
	HasComment     = tostring(customDimensions.hasComment),
	Question       = tostring(customDimensions.question),
	ConversationId = tostring(customDimensions.conversationId),
	UserId         = tostring(customDimensions.userId),
	UserName       = tostring(customDimensions.userName),
	UserEmail      = tostring(customDimensions.userEmail)
| project timestamp, Rating, Comment, HasComment, Question, ConversationId,
		  UserId, UserName, UserEmail
```

### 2.3 — `EmailsSent`
```kql
customEvents
| where name == "EmailSent"
| extend
	Question       = tostring(customDimensions.question),
	UserEmail      = tostring(customDimensions.userEmail),
	UserId         = tostring(customDimensions.userId),
	UserName       = tostring(customDimensions.userName),
	ConversationId = tostring(customDimensions.conversationId),
	HrAddress      = tostring(customDimensions.hrAddress),
	RecipientCount = todouble(coalesce(customMeasurements.recipientCount, customDimensions.recipientCount))
| project timestamp, Question, UserEmail, UserId, UserName, ConversationId,
		  HrAddress, RecipientCount
```

### 2.4 — `Failures` (optional)
```kql
customEvents
| where name in ("AgentInteractionFailed", "EmailFailed")
| extend
	EventType      = name,
	Question       = tostring(customDimensions.question),
	ErrorText      = tostring(customDimensions.error),
	ErrorCode      = tostring(customDimensions.errorCode),
	ConversationId = tostring(customDimensions.conversationId),
	UserId         = tostring(customDimensions.userId)
| project timestamp, EventType, Question, ErrorText, ErrorCode, ConversationId, UserId
```

### 2.5 — Set data types
For each query, in **Transform data** (Power Query):
1. Select `timestamp` → **Transform → Data type → Date/Time**.
2. Numeric columns (`DurationMs`, `*Tokens`, `RecipientCount`) → **Decimal Number**.
3. Text columns → **Text**.
4. **Close & Apply**.

> Explicit types prevent Power BI guessing wrongly on sparse columns.

### 2.6 — Add a Date table
**Modeling → New table**:
```dax
DateTable =
VAR MinDate = MIN ( AgentInteractions[timestamp] )
VAR MaxDate = MAX ( AgentInteractions[timestamp] )
RETURN
ADDCOLUMNS (
	CALENDAR ( DATE ( YEAR(MinDate), MONTH(MinDate), 1 ), MaxDate ),
	"Year",        YEAR ( [Date] ),
	"Month",       FORMAT ( [Date], "MMM" ),
	"MonthNumber", MONTH ( [Date] ),
	"YearMonth",   FORMAT ( [Date], "YYYY-MM" ),
	"Day",         DAY ( [Date] ),
	"Weekday",     FORMAT ( [Date], "ddd" ),
	"WeekdayNum",  WEEKDAY ( [Date], 2 )
)
```
Then **Table tools → Mark as date table** → choose `Date`.

---

## Part 3 — Create the data model

### Step 3.1 — Add date-only columns
The event tables hold timestamps; relate them to the date table on a date-only column.
Add a calculated column to **each** event table (Modeling → New column):

```dax
EventDate = DATE ( YEAR ( AgentInteractions[timestamp] ), MONTH ( AgentInteractions[timestamp] ), DAY ( AgentInteractions[timestamp] ) )
```
Repeat for `UserFeedback`, `EmailsSent`, `Failures` (change the table name).

### Step 3.2 — Create relationships
**Model view** → drag to connect:

| From | To | Cardinality | Direction |
|---|---|---|---|
| `DateTable[Date]` | `AgentInteractions[EventDate]` | One-to-many | Single |
| `DateTable[Date]` | `UserFeedback[EventDate]` | One-to-many | Single |
| `DateTable[Date]` | `EmailsSent[EventDate]` | One-to-many | Single |
| `DateTable[Date]` | `Failures[EventDate]` | One-to-many | Single |

**Do NOT** create relationships between the event tables on `ConversationId` — a conversation
can produce many interactions, feedback entries and emails, so it is many-to-many and will
produce ambiguous filtering. Cross-event analysis is handled by DAX measures in Part 4.

✅ **Checkpoint:** a star schema with `DateTable` at the centre.

---

## Part 4 — Add DAX measures

Create a dedicated measures table: **Home → Enter data** → name it `Measures` → **Load**,
then add the measures below to it.

### Volume
```dax
Total Interactions = COUNTROWS ( AgentInteractions )

Answered = CALCULATE ( [Total Interactions], AgentInteractions[CanAnswer] = "true" )

Unanswered = CALCULATE ( [Total Interactions], AgentInteractions[CanAnswer] = "false" )

Answer Rate % =
DIVIDE ( [Answered], [Total Interactions], 0 )

Unique Users = DISTINCTCOUNT ( AgentInteractions[UserId] )

Conversations = DISTINCTCOUNT ( AgentInteractions[ConversationId] )

New Conversations =
CALCULATE ( [Total Interactions], AgentInteractions[IsNewConversation] = "true" )
```

### Performance
```dax
Avg Response Time (s) = DIVIDE ( AVERAGE ( AgentInteractions[DurationMs] ), 1000 )

P95 Response Time (s) =
DIVIDE ( PERCENTILEX.INC ( AgentInteractions, AgentInteractions[DurationMs], 0.95 ), 1000 )

Max Response Time (s) = DIVIDE ( MAX ( AgentInteractions[DurationMs] ), 1000 )
```

### Tokens and cost
Update the two rate variables to match your model's pricing.
```dax
Total Tokens = SUM ( AgentInteractions[TotalTokens] )

Input Tokens = SUM ( AgentInteractions[InputTokens] )

Output Tokens = SUM ( AgentInteractions[OutputTokens] )

Avg Tokens per Interaction = DIVIDE ( [Total Tokens], [Total Interactions] )

Estimated Cost =
VAR InputRatePer1K  = 0.00015     -- set to your model's input price
VAR OutputRatePer1K = 0.00060     -- set to your model's output price
RETURN
	DIVIDE ( [Input Tokens], 1000 ) * InputRatePer1K
  + DIVIDE ( [Output Tokens], 1000 ) * OutputRatePer1K

Cost per Interaction = DIVIDE ( [Estimated Cost], [Total Interactions] )
```

### Feedback
```dax
Total Feedback = COUNTROWS ( UserFeedback )

Positive Feedback = CALCULATE ( [Total Feedback], UserFeedback[Rating] = "positive" )

Negative Feedback = CALCULATE ( [Total Feedback], UserFeedback[Rating] = "negative" )

Satisfaction % = DIVIDE ( [Positive Feedback], [Total Feedback], 0 )

Feedback Response Rate % = DIVIDE ( [Total Feedback], [Total Interactions], 0 )

Comments Provided = CALCULATE ( [Total Feedback], UserFeedback[HasComment] = "true" )
```

### Escalation (cross-event)
Because there is no physical relationship on `ConversationId`, these use set logic.
```dax
Emails Sent = COUNTROWS ( EmailsSent )

Escalation Rate % = DIVIDE ( [Emails Sent], [Unanswered], 0 )

Negative Not Escalated =
VAR EmailedConvs =
	CALCULATETABLE ( VALUES ( EmailsSent[ConversationId] ), ALL ( DateTable ) )
RETURN
CALCULATE (
	[Negative Feedback],
	NOT UserFeedback[ConversationId] IN EmailedConvs
)
```
> `Negative Not Escalated` = users who were dissatisfied **and** whose question was never
> emailed to HR — the highest-value review queue.

### Failures
```dax
Total Failures = COUNTROWS ( Failures )

Failure Rate % = DIVIDE ( [Total Failures], [Total Interactions] + [Total Failures], 0 )
```

### Formatting
Select each `%` measure → **Measure tools** → **Format: Percentage**, 1 decimal.
Format `Estimated Cost` as **Currency**, 2–4 decimals.

---

## Part 5 — Build the report pages

### Page 1 — Executive summary

**KPI cards** (Visualizations → *Card*), one per measure:
- Total Interactions
- Answer Rate %
- Satisfaction %
- Unique Users
- Estimated Cost
- Avg Response Time (s)

**Line chart — Volume and answer rate over time**
- X-axis: `DateTable[Date]`
- Y-axis: `[Total Interactions]`
- Secondary line (use *Line and stacked column chart*): `[Answer Rate %]`

**Donut — Answered vs unanswered**
- Legend: `AgentInteractions[CanAnswer]`
- Values: `[Total Interactions]`

**Slicers** (add to every page):
- `DateTable[Date]` → *Between* slicer
- `AgentInteractions[UserName]` → dropdown

### Page 2 — Content gaps

**Table — Most frequent unanswered questions**
- Columns: `AgentInteractions[Question]`, `[Total Interactions]`, `[Answer Rate %]`
- Filter: `CanAnswer` **is** `false`
- Sort by `[Total Interactions]` descending

**Table — Popular questions with low success rate**
- Columns: `Question`, `[Total Interactions]`, `[Answered]`, `[Answer Rate %]`
- Visual-level filters: `[Total Interactions]` ≥ 3, `[Answer Rate %]` < 0.8

**Card:** `[Unanswered]`

> ⚠️ Questions are free text, so near-duplicates ("dental coverage?" vs "Dental coverage")
> won't group. See [Part 7](#grouping-similar-questions) for normalisation options.

### Page 3 — User feedback

**KPI cards:** Total Feedback, Satisfaction %, Negative Feedback, Feedback Response Rate %

**Line chart — Satisfaction over time**
- X-axis: `DateTable[Date]`, Y-axis: `[Satisfaction %]`

**Table — Negative feedback review queue**
- Columns: `UserFeedback[timestamp]`, `Question`, `Comment`, `UserName`
- Filter: `Rating` **is** `negative`
- Sort by timestamp descending

**Card:** `[Negative Not Escalated]` — dissatisfied users who never reached HR

**Stacked bar — Feedback by user**
- Y-axis: `UserFeedback[UserName]`, X-axis: `[Total Feedback]`, Legend: `Rating`

### Page 4 — Cost and performance

**Cards:** Estimated Cost, Total Tokens, Cost per Interaction, P95 Response Time (s)

**Column chart — Daily token consumption**
- X-axis: `DateTable[Date]`
- Y-axis: `[Input Tokens]`, `[Output Tokens]` (stacked)

**Line chart — Response time trend**
- X-axis: `DateTable[Date]`
- Y-axis: `[Avg Response Time (s)]`, `[P95 Response Time (s)]`

**Table — Most expensive interactions**
- Columns: `timestamp`, `Question`, `TotalTokens`, `DurationMs`
- Sort by `TotalTokens` descending, Top N = 25

**Column chart — Peak usage hours**
1. Add a calculated column to `AgentInteractions`:
```dax
HourOfDay = HOUR ( AgentInteractions[timestamp] )
```
2. X-axis: `HourOfDay`, Y-axis: `[Total Interactions]`

### Page 5 — Escalations and errors

**Cards:** Emails Sent, Escalation Rate %, Total Failures, Failure Rate %

**Table — Recent escalations**
- Columns: `EmailsSent[timestamp]`, `Question`, `UserName`, `HrAddress`, `RecipientCount`

**Table — Recent failures**
- Columns: `Failures[timestamp]`, `EventType`, `ErrorCode`, `ErrorText`, `Question`

---

## Part 6 — Publish and schedule refresh

### Step 6.1 — Publish
1. **Home → Publish** → choose a workspace.
2. Open the report in the Power BI service (`app.powerbigov.us` for GCC).

### Step 6.2 — Configure refresh
1. Workspace → **Datasets** → your dataset → **Settings**.
2. **Data source credentials** → **Edit credentials** →
   Authentication method: **OAuth2** → sign in.
3. **Scheduled refresh** → **On** → set a frequency (daily, or up to 8×/day on Pro).

> **No gateway required.** The Application Insights REST API is a cloud source, so Power BI
> connects directly.

### Step 6.3 — Create a dashboard (optional)
Reports and dashboards are different objects in Power BI:
1. Open the report → hover a visual → **📌 Pin visual**.
2. Pin to a **New dashboard** → name it *HR Benefits Agent*.
3. Repeat for your key KPIs.

Dashboards are single-page and good for at-a-glance monitoring; reports are for exploration.

### Row-level security (optional)
Given the reports contain question text and user identities:
1. **Modeling → Manage roles** → **Create** → name it `OwnTeamOnly`.
2. Add a DAX filter on `AgentInteractions`, e.g.:
```dax
[UserName] = USERNAME()
```
3. Assign users to the role in the service (Dataset → **Security**).

At minimum, restrict workspace access to those who genuinely need question-level detail.

---

## Part 7 — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Web.Contents` credential error | Wrong auth type | Data source settings → **Organizational account** → sign in |
| Query returns 0 rows | Time range or ingestion delay | Test the KQL in the Portal first; allow 2–5 min for ingestion |
| Columns are all `null` | Dimension name mismatch | Verify names against the [appendix](#appendix--event-reference); they are case-sensitive |
| Numeric columns blank | Values landed in `customDimensions` not `customMeasurements` | The `coalesce(...)` in the queries handles both — make sure you copied it |
| "Query exceeded result size" | Importing too many raw rows | Add `| where timestamp > ago(30d)` or aggregate in KQL |
| Data older than 90 days missing | App Insights retention | Increase retention, or set up continuous export |
| Refresh fails in the service | Expired credentials | Dataset settings → re-enter data source credentials |
| Wrong endpoint / cannot connect (GCC) | Commercial URL used | Re-export the M query from **your** portal (Part 1.1) |

### Grouping similar questions
Free-text questions won't aggregate cleanly. Options, cheapest first:
1. **Normalise in KQL** — lowercase and trim:
   `| extend QuestionKey = tolower(trim(" ", Question))`
2. **Keyword buckets** — add a calculated column:
```dax
Topic =
SWITCH (
	TRUE (),
	CONTAINSSTRING ( AgentInteractions[Question], "dental" ), "Dental",
	CONTAINSSTRING ( AgentInteractions[Question], "vision" ), "Vision",
	CONTAINSSTRING ( AgentInteractions[Question], "premium" ), "Premiums",
	CONTAINSSTRING ( AgentInteractions[Question], "enroll" ),  "Enrollment",
	"Other"
)
```
   Then chart by `Topic` instead of raw question text.
3. **Cluster upstream** — have the Function emit a category dimension. Most accurate, but
   requires a code change.

### Import vs DirectQuery
| | Import (default) | DirectQuery (Kusto connector) |
|---|---|---|
| Speed | Fast | Slower per visual |
| Freshness | As of last refresh | Near real-time |
| Row limits | Dataset size limits | Query-time limits |
| Recommended | ✅ For this dashboard | Only if you need live data |

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
| `durationMs` | number | |
| `inputTokens`, `outputTokens`, `totalTokens` | number | When reported by the API |
| `reasoningTokens`, `cachedInputTokens` | number | Reasoning models only |

### `UserFeedback` — thumbs up/down
| Dimension | Notes |
|---|---|
| `rating` | `"positive"` / `"negative"` |
| `rawRating` | As submitted |
| `comment` | Free text, usually negative only |
| `hasComment` | `"true"` / `"false"` |
| `question` | **Negative feedback only** |
| `conversationId`, `userId`, `userName`, `userEmail` | |
| `isNegative` | measurement, 1/0 |

### `EmailSent` / `EmailFailed`
| Dimension | Notes |
|---|---|
| `question`, `userEmail`, `userId`, `userName` | |
| `conversationId` | |
| `hrAddress` | All recipients, comma separated |
| `graphStatus` | `EmailSent` only (202) |
| `recipientCount` | measurement, `EmailSent` only |
| `errorCode`, `error` | `EmailFailed` only |

### `AgentInteractionFailed`
| Dimension | Notes |
|---|---|
| `agentName`, `question`, `error` | |
| `durationMs` | measurement |

> **Booleans are stored as the strings `"true"` / `"false"`** (App Insights custom dimensions
> are strings). Always compare against the quoted text in DAX and KQL.
