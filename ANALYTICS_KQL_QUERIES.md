# Application Insights — Usage Analytics (KQL)

The Azure Function emits **custom events** to Application Insights for every agent
interaction and every email send. They land in the **`customEvents`** table.

## Events emitted

| Event name | When | Key custom dimensions |
|---|---|---|
| `AgentInteraction` | Every call to `agent_httptrigger` | `canAnswer`, `agentName`, `conversationId`, `userId`, `userName`, `isNewConversation`, `durationMs`, token counts (`inputTokens`, `outputTokens`, `totalTokens`, `reasoningTokens`, `cachedInputTokens`), and `question` **only when `canAnswer` is `false`** |
| `AgentInteractionFailed` | The agent call threw an error | `question`, `error`, `durationMs` |
| `EmailSent` | HR email delivered successfully | `question`, `userEmail`, `userId`, `userName`, `conversationId`, `hrAddress` (all recipients, comma separated), `graphStatus`, `recipientCount` |
| `EmailFailed` | HR email failed | `question`, `userEmail`, `errorCode`, `error` |
| `UserFeedback` | User rates an answer 👍/👎 | `rating` (`positive`/`negative`), `rawRating`, `comment`, `hasComment`, `conversationId`, `userId`, `userName`, `userEmail`, and `question` **only for negative feedback** |

> Custom dimensions are accessed in KQL as `customDimensions.<name>`.
> `canAnswer` is stored as the string `"true"` / `"false"`.

### What is deliberately NOT captured
- **Agent replies are never recorded.**
- **Question text is only recorded when it could not be answered, or when it was submitted
  for an email.** Successfully answered questions record no question text.

---

## Setup

- ☐ `APPLICATIONINSIGHTS_CONNECTION_STRING` must be set on the Function App.
- ☐ `opencensus-ext-azure` must be in `requirements.txt` (already added, pinned) so events
  reach the `customEvents` table.
- ☐ If the exporter is unavailable, the code falls back to `traces` rows prefixed with
  `EVENT <name>` so no data is lost.
- ☐ Allow 2–5 minutes for ingestion before querying.

### Reliability on Consumption / Flex plans
Azure Functions can freeze or recycle a worker immediately after a request completes, which
would drop buffered telemetry. The code mitigates this by:
- using a short exporter `export_interval` (2s), and
- calling `flush_events()` immediately after each `track_event`.

If you still see missing events under bursty load, check the Function App is not scaling to
zero mid-flush and confirm ingestion sampling is disabled in `host.json`.

### Verbose diagnostics are OFF by default
`DEBUG_RAW_RESPONSE` controls logging of the **full model response** and **raw request
bodies**. These contain the employee's HR profile, knowledge-base document text and the
user's question, so they are **not** logged unless you explicitly enable the flag.

- Enable temporarily for troubleshooting: set `DEBUG_RAW_RESPONSE=true`, reproduce, then
  **remove the setting**.
- Leave it unset in production.

---

## Core queries

### 1. All interactions in the last 24 hours
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(24h)
| project timestamp,
		  canAnswer   = tostring(customDimensions.canAnswer),
		  user        = tostring(customDimensions.userName),
		  durationMs  = todouble(customDimensions.durationMs),
		  question    = tostring(customDimensions.question)  // populated only when unanswered
| order by timestamp desc
```

### 2. Answered vs unanswered — the headline metric
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(7d)
| summarize count() by canAnswer = tostring(customDimensions.canAnswer)
```

### 3. Answer rate over time (daily trend)
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(30d)
| summarize
	total     = count(),
	answered  = countif(tostring(customDimensions.canAnswer) == "true"),
	unanswered= countif(tostring(customDimensions.canAnswer) == "false")
	by bin(timestamp, 1d)
| extend answerRatePct = round(100.0 * answered / total, 1)
| order by timestamp asc
```

### 4. Every question the agent could NOT answer (for review)
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(30d)
| where tostring(customDimensions.canAnswer) == "false"
| project timestamp,
		  question = tostring(customDimensions.question),
		  user     = tostring(customDimensions.userName),
		  userId   = tostring(customDimensions.userId),
		  conversationId = tostring(customDimensions.conversationId)
| order by timestamp desc
```

### 5. Most frequent unanswered questions (content-gap analysis)
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(30d)
| where tostring(customDimensions.canAnswer) == "false"
| extend question = tolower(trim(" ", tostring(customDimensions.question)))
| where isnotempty(question)
| summarize occurrences = count(), lastAsked = max(timestamp) by question
| where occurrences > 1
| order by occurrences desc
```
> Use this to decide what content to add to the knowledge base.

### 6. All emails sent to HR, with the question text
```kql
customEvents
| where name == "EmailSent"
| where timestamp > ago(30d)
| project timestamp,
		  question  = tostring(customDimensions.question),
		  fromUser  = tostring(customDimensions.userEmail),
		  userName  = tostring(customDimensions.userName),
		  hrAddress = tostring(customDimensions.hrAddress),
		  conversationId = tostring(customDimensions.conversationId)
| order by timestamp desc
```

### 7. Email failures
```kql
customEvents
| where name == "EmailFailed"
| where timestamp > ago(7d)
| project timestamp,
		  question  = tostring(customDimensions.question),
		  fromUser  = tostring(customDimensions.userEmail),
		  errorCode = tostring(customDimensions.errorCode),
		  error     = tostring(customDimensions.error)
| order by timestamp desc
```

### 8. Escalation rate — how often an unanswered question becomes an email
```kql
let unanswered = toscalar(
	customEvents
	| where name == "AgentInteraction" and timestamp > ago(30d)
	| where tostring(customDimensions.canAnswer) == "false"
	| count);
let emailed = toscalar(
	customEvents
	| where name == "EmailSent" and timestamp > ago(30d)
	| count);
print unanswered = unanswered,
	  emailed = emailed,
	  escalationRatePct = round(100.0 * emailed / unanswered, 1)
```

---

## Usage statistics

### Active users per day
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(30d)
| summarize activeUsers = dcount(tostring(customDimensions.userId))
	by bin(timestamp, 1d)
| order by timestamp asc
```

### Busiest users
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(30d)
| summarize questions = count(),
			unanswered = countif(tostring(customDimensions.canAnswer) == "false")
	by user = tostring(customDimensions.userName)
| order by questions desc
```

### Conversations started vs follow-up turns
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(7d)
| summarize count() by isNewConversation = tostring(customDimensions.isNewConversation)
```

### Response-time distribution
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(7d)
| extend durationMs = todouble(customDimensions.durationMs)
| summarize avg = avg(durationMs),
			p50 = percentile(durationMs, 50),
			p95 = percentile(durationMs, 95),
			max = max(durationMs)
	by bin(timestamp, 1h)
| order by timestamp desc
```

### Peak usage hours
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(30d)
| extend hour = datetime_part("hour", timestamp)
| summarize questions = count() by hour
| order by hour asc
| render columnchart
```

### Errors
```kql
customEvents
| where name == "AgentInteractionFailed"
| where timestamp > ago(7d)
| project timestamp,
		  question = tostring(customDimensions.question),
		  error    = tostring(customDimensions.error)
| order by timestamp desc
```

---

## Token consumption

Token counts are emitted as **measurements** on `AgentInteraction`. Depending on the
App Insights schema they surface either in `customMeasurements` or `customDimensions`, so
these queries read `customMeasurements` first and fall back to `customDimensions`.

### Tokens per interaction
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(24h)
| extend inTok  = todouble(coalesce(customMeasurements.inputTokens,  customDimensions.inputTokens)),
		 outTok = todouble(coalesce(customMeasurements.outputTokens, customDimensions.outputTokens)),
		 total  = todouble(coalesce(customMeasurements.totalTokens,  customDimensions.totalTokens))
| project timestamp,
		  user = tostring(customDimensions.userName),
		  canAnswer = tostring(customDimensions.canAnswer),
		  inTok, outTok, total
| order by timestamp desc
```

### Daily token totals (cost tracking)
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(30d)
| extend inTok  = todouble(coalesce(customMeasurements.inputTokens,  customDimensions.inputTokens)),
		 outTok = todouble(coalesce(customMeasurements.outputTokens, customDimensions.outputTokens))
| summarize interactions = count(),
			inputTokens  = sum(inTok),
			outputTokens = sum(outTok),
			totalTokens  = sum(inTok) + sum(outTok)
	by bin(timestamp, 1d)
| order by timestamp asc
```

### Estimated cost per day
Replace the two rates with your model's actual price per 1K tokens.
```kql
let inputRatePer1K  = 0.00015;   // <-- set to your model's input price
let outputRatePer1K = 0.00060;   // <-- set to your model's output price
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(30d)
| extend inTok  = todouble(coalesce(customMeasurements.inputTokens,  customDimensions.inputTokens)),
		 outTok = todouble(coalesce(customMeasurements.outputTokens, customDimensions.outputTokens))
| summarize inputTokens = sum(inTok), outputTokens = sum(outTok)
	by bin(timestamp, 1d)
| extend estimatedCost = round(inputTokens / 1000 * inputRatePer1K
							 + outputTokens / 1000 * outputRatePer1K, 4)
| order by timestamp asc
```

### Token usage per user (who is driving spend)
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(30d)
| extend total = todouble(coalesce(customMeasurements.totalTokens, customDimensions.totalTokens))
| summarize interactions = count(),
			totalTokens = sum(total),
			avgTokens   = round(avg(total), 0)
	by user = tostring(customDimensions.userName)
| order by totalTokens desc
```

### Most expensive interactions
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(7d)
| extend total = todouble(coalesce(customMeasurements.totalTokens, customDimensions.totalTokens))
| top 25 by total desc
| project timestamp, total,
		  canAnswer = tostring(customDimensions.canAnswer),
		  user = tostring(customDimensions.userName),
		  question = tostring(customDimensions.question)
```

### Reasoning-token overhead
Shows how much of the output is model "thinking" — useful when tuning reasoning effort.
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(7d)
| extend outTok    = todouble(coalesce(customMeasurements.outputTokens,    customDimensions.outputTokens)),
		 reasoning = todouble(coalesce(customMeasurements.reasoningTokens, customDimensions.reasoningTokens))
| where isnotnull(reasoning)
| summarize outputTokens = sum(outTok), reasoningTokens = sum(reasoning)
	by bin(timestamp, 1d)
| extend reasoningSharePct = round(100.0 * reasoningTokens / outputTokens, 1)
| order by timestamp asc
```

### Do unanswered questions cost more?
```kql
customEvents
| where name == "AgentInteraction"
| where timestamp > ago(30d)
| extend total = todouble(coalesce(customMeasurements.totalTokens, customDimensions.totalTokens))
| summarize interactions = count(),
			avgTokens = round(avg(total), 0),
			totalTokens = sum(total)
	by canAnswer = tostring(customDimensions.canAnswer)
```

---

## User feedback

Emitted by the `submit_feedback` route. Works in any cloud (including GCC) because
it does not depend on the built-in Copilot Studio feedback store.

### Satisfaction summary
```kql
customEvents
| where name == "UserFeedback"
| where timestamp > ago(30d)
| summarize count() by rating = tostring(customDimensions.rating)
```

### Satisfaction rate over time
```kql
customEvents
| where name == "UserFeedback"
| where timestamp > ago(90d)
| summarize
	total    = count(),
	positive = countif(tostring(customDimensions.rating) == "positive"),
	negative = countif(tostring(customDimensions.rating) == "negative")
	by bin(timestamp, 1d)
| extend satisfactionPct = round(100.0 * positive / total, 1)
| order by timestamp asc
```

### All negative feedback with comments (the review queue)
```kql
customEvents
| where name == "UserFeedback"
| where timestamp > ago(30d)
| where tostring(customDimensions.rating) == "negative"
| project timestamp,
		  question = tostring(customDimensions.question),
		  comment  = tostring(customDimensions.comment),
		  user     = tostring(customDimensions.userName),
		  userEmail = tostring(customDimensions.userEmail),
		  conversationId = tostring(customDimensions.conversationId)
| order by timestamp desc
```

### Only negative feedback that included a written comment
```kql
customEvents
| where name == "UserFeedback"
| where timestamp > ago(30d)
| where tostring(customDimensions.rating) == "negative"
| where tostring(customDimensions.hasComment) == "true"
| project timestamp,
		  comment  = tostring(customDimensions.comment),
		  question = tostring(customDimensions.question)
| order by timestamp desc
```

### Recurring themes in negative feedback
```kql
customEvents
| where name == "UserFeedback"
| where timestamp > ago(90d)
| where tostring(customDimensions.rating) == "negative"
| extend question = tolower(trim(" ", tostring(customDimensions.question)))
| where isnotempty(question)
| summarize complaints = count(), lastSeen = max(timestamp) by question
| where complaints > 1
| order by complaints desc
```

### Feedback joined to the original interaction
Correlates a rating with the interaction's `canAnswer` flag and token cost, using
`conversationId` as the join key.
```kql
let interactions =
	customEvents
	| where name == "AgentInteraction" and timestamp > ago(30d)
	| project interactionTime = timestamp,
			  conversationId  = tostring(customDimensions.conversationId),
			  canAnswer       = tostring(customDimensions.canAnswer),
			  totalTokens     = todouble(coalesce(customMeasurements.totalTokens, customDimensions.totalTokens));
let feedback =
	customEvents
	| where name == "UserFeedback" and timestamp > ago(30d)
	| project feedbackTime  = timestamp,
			  conversationId = tostring(customDimensions.conversationId),
			  rating         = tostring(customDimensions.rating),
			  comment        = tostring(customDimensions.comment);
feedback
| join kind=leftouter interactions on conversationId
| project feedbackTime, rating, comment, canAnswer, totalTokens, conversationId
| order by feedbackTime desc
```

### Did the user still dislike an answer the agent *could* answer?
Highlights answers that were confidently given but rated poorly — the highest-value
content to review.
```kql
let interactions =
	customEvents
	| where name == "AgentInteraction" and timestamp > ago(30d)
	| project conversationId = tostring(customDimensions.conversationId),
			  canAnswer      = tostring(customDimensions.canAnswer);
customEvents
| where name == "UserFeedback" and timestamp > ago(30d)
| where tostring(customDimensions.rating) == "negative"
| extend conversationId = tostring(customDimensions.conversationId)
| join kind=leftouter interactions on conversationId
| where canAnswer == "true"
| project timestamp,
		  comment  = tostring(customDimensions.comment),
		  question = tostring(customDimensions.question),
		  conversationId
| order by timestamp desc
```

### Feedback response rate
How many interactions actually receive a rating.
```kql
let interactions = toscalar(
	customEvents | where name == "AgentInteraction" and timestamp > ago(30d) | count);
let rated = toscalar(
	customEvents | where name == "UserFeedback" and timestamp > ago(30d) | count);
print interactions = interactions,
	  rated = rated,
	  responseRatePct = round(100.0 * rated / interactions, 1)
```

### Users giving the most negative feedback
```kql
customEvents
| where name == "UserFeedback"
| where timestamp > ago(30d)
| summarize total = count(),
			negative = countif(tostring(customDimensions.rating) == "negative")
	by user = tostring(customDimensions.userName)
| extend negativePct = round(100.0 * negative / total, 1)
| order by negative desc
```

---

## Fallback: querying traces
If the custom-event exporter is not active, the same payloads appear in `traces`:
```kql
traces
| where timestamp > ago(24h)
| where message startswith "EVENT "
| extend eventName = extract(@"^EVENT (\w+)", 1, message)
| project timestamp, eventName, message
| order by timestamp desc
```

---

## Privacy note
`question` text is captured **only** when the agent could not answer, when the call failed,
or when the question was emailed to HR. Answered questions record no question text, and
**agent replies are never captured**. User identity (`userEmail` / `userId` / `userName`) is
recorded on interactions.

- ☐ Confirm this retention is acceptable to your privacy/compliance team.
- ☐ Review the App Insights **data retention** period (default 90 days).
- ☐ Restrict who can read the Application Insights resource.
