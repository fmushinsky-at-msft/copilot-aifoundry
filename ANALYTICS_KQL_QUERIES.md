# Application Insights — Usage Analytics (KQL)

The Azure Function emits **custom events** to Application Insights for every agent
interaction and every email send. They land in the **`customEvents`** table.

## Events emitted

| Event name | When | Key custom dimensions |
|---|---|---|
| `AgentInteraction` | Every call to `agent_httptrigger` | `canAnswer`, `agentName`, `conversationId`, `userId`, `userName`, `isNewConversation`, `durationMs`, and `question` **only when `canAnswer` is `false`** |
| `AgentInteractionFailed` | The agent call threw an error | `question`, `error`, `durationMs` |
| `EmailSent` | HR email delivered successfully | `question`, `userEmail`, `userId`, `userName`, `conversationId`, `hrAddress`, `graphStatus` |
| `EmailFailed` | HR email failed | `question`, `userEmail`, `errorCode`, `error` |

> Custom dimensions are accessed in KQL as `customDimensions.<name>`.
> `canAnswer` is stored as the string `"true"` / `"false"`.

### What is deliberately NOT captured
- **Agent replies are never recorded.**
- **Question text is only recorded when it could not be answered, or when it was submitted
  for an email.** Successfully answered questions record no question text.

---

## Setup

- ☐ `APPLICATIONINSIGHTS_CONNECTION_STRING` must be set on the Function App.
- ☐ `opencensus-ext-azure` must be in `requirements.txt` (already added) so events reach the
  `customEvents` table.
- ☐ If the exporter is unavailable, the code falls back to `traces` rows prefixed with
  `EVENT <name>` so no data is lost.
- ☐ Allow 2–5 minutes for ingestion before querying.

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
