# Foundry + Function App Setup Checklist

Everything required to stand up a **brand new** Azure AI Foundry account and configure the
Function App so `agent_httptrigger` works.

Derived from the code in [function_app.py](./function_app.py), not from memory. Line
references are to that file as it stands now. They drift when the code changes, so if one is
off, search for the variable name.

> Legend: ☐ = to do. Work top to bottom; later steps depend on earlier ones.

---

## Contents

- [0. Prerequisites](#0-prerequisites)
- [1. Create the Foundry resource and project](#1-create-the-foundry-resource-and-project)
- [2. Deploy a model](#2-deploy-a-model)
- [3. Create the agent](#3-create-the-agent)
- [4. Add knowledge (optional)](#4-add-knowledge-optional)
- [5. Function App managed identity](#5-function-app-managed-identity)
- [6. Grant RBAC on the Foundry resource](#6-grant-rbac-on-the-foundry-resource)
- [7. Application settings](#7-application-settings)
- [8. Verify](#8-verify)
- [Reference - all environment variables](#reference---all-environment-variables)
- [Troubleshooting](#troubleshooting)

---

## 0. Prerequisites

- ☐ An Azure subscription. **Commercial**, not Azure Government — the existing Function App
  and Foundry project both use commercial endpoints (`azurewebsites.net`,
  `services.ai.azure.com`).
- ☐ Permission to create resources and, critically, **to assign RBAC roles**
  (Owner or User Access Administrator at resource-group scope). Step 6 fails without this.
- ☐ The Function App already deployed, or ready to deploy.

---

## 1. Create the Foundry resource and project

- ☐ In the [Foundry portal](https://ai.azure.com), create a **Foundry resource** (this is the
  Azure resource, of type `Microsoft.CognitiveServices/accounts`).
- ☐ Create a **project** inside it. The code targets a project endpoint, not a resource
  endpoint.
- ☐ Copy the **project endpoint** from the project Overview page. It looks like:

```
https://<resource-name>.services.ai.azure.com/api/projects/<project-name>
```

This becomes `AIProjectEndpoint`.

> **Choose a region that supports Agents.** Not every region does, and model availability
> varies. Check
> [Agent Service regional support](https://learn.microsoft.com/azure/foundry/agents/concepts/limits-quotas-regions)
> before creating the resource — moving later means recreating it.

---

## 2. Deploy a model

- ☐ In the project, go to **Models + endpoints** → **Deploy model**.
- ☐ Deploy a chat model (for example `gpt-4o` or `gpt-4.1-mini`).
- ☐ Note the **deployment name** exactly as shown. This becomes `ModelDeploymentName`.

> The deployment name is chosen by you at deploy time and is **not** necessarily the model
> name. Copy what the portal shows, character for character.

Code default if unset: `gpt-5.5` ([L1079](./function_app.py)). Set the variable explicitly
rather than relying on that default.

---

## 3. Create the agent

- ☐ In the project, create a **prompt agent**.
- ☐ Give it a **name** — this is what you put in `AGENT_ID`.
- ☐ Paste in your system instructions.

> ⚠️ **`AGENT_ID` holds the agent NAME, not a GUID.** The code calls
> `project_client.agents.get(agent_name=agent_id)` ([L1098](./function_app.py)). Passing an
> ID-looking value fails to resolve. The variable name is misleading; the value is a name.

### Include the NO_ANSWER instruction

`agent_httptrigger` sets a `canAnswer` flag by scanning the reply for markers
([L1216](./function_app.py)). The Copilot Studio topic branches on it to offer HR escalation.
Without this, escalation never triggers.

- ☐ Add to the agent instructions something like:

  > If you cannot answer the question from your knowledge sources, reply with exactly
  > `NO_ANSWER` and nothing else.

The default markers are in `DEFAULT_NO_ANSWER_MARKERS` ([L570](./function_app.py)) and include `NO_ANSWER` plus
several natural-language phrases. Override with `NO_ANSWER_MARKERS` (`;`-separated) only if
your agent's refusal wording differs.

---

## 4. Add knowledge (optional)

Only if the agent should answer from your documents.

- ☐ Add a knowledge source to the agent — **File search** (upload files) or **Azure AI
  Search** (existing index).
- ☐ If using Azure AI Search, grant the **project's managed identity** the
  **Search Index Data Contributor** and **Search Service Contributor** roles on the search
  resource, otherwise tool calls fail with 401/403.
- ☐ Instruct the agent to cite sources, otherwise responses contain no annotations and
  `render_message_with_citations` ([L1205](./function_app.py)) has nothing to render.

---

## 5. Function App managed identity

- ☐ Azure Portal → Function App → **Settings** → **Identity**.
- ☐ **System assigned** tab → **Status: On** → **Save**.
- ☐ Copy the **Object (principal) ID**. Step 6 needs it.

This is what `DefaultAzureCredential()` ([L1094](./function_app.py)) uses in Azure. No keys or
secrets are involved.

---

## 6. Grant RBAC on the Foundry resource

**This is the step most likely to be missed, and it produces a confusing failure.**

- ☐ Azure Portal → your **Foundry resource** → **Access control (IAM)**
      → **Add role assignment**.
- ☐ Role: **Foundry Agent Consumer** (least privilege — the function only *calls* the agent,
      it never creates or edits one).
- ☐ Members → **Managed identity** → select your Function App.
- ☐ **Review + assign**.

CLI alternative:

```powershell
az role assignment create `
  --assignee "<function-app-principal-id>" `
  --role "Foundry Agent Consumer" `
  --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-resource>"
```

> **Role naming:** these roles were recently renamed. **Foundry User** was **Azure AI User**,
> and you may still see the old names in the portal. The role IDs and permissions are
> unchanged. Your README currently says "Azure AI Developer", which is **not** one of the
> roles that grants agent interaction.

**Why `Foundry Agent Consumer` and not Owner or Contributor:** per Microsoft's permissions
reference, `Owner` and `Contributor` on a Foundry project **cannot** interact with agent
endpoints. Assigning Owner and expecting it to work is a common and confusing dead end.

| Role | Can call agent endpoints? |
|---|---|
| Owner | ❌ No |
| Contributor | ❌ No |
| **Foundry Agent Consumer** | ✅ **Yes** — use this |
| Foundry User | ✅ Yes (broader than needed) |

- ☐ Allow a few minutes for the assignment to propagate before testing.

---

## 7. Application settings

Azure Portal → Function App → **Settings** → **Environment variables** → Application settings.

### Required

- ☐ `AIProjectEndpoint` = the project endpoint from Step 1.
- ☐ `ModelDeploymentName` = the deployment name from Step 2.
- ☐ `AGENT_ID` = the agent **name** from Step 3.
- ☐ `APPLICATIONINSIGHTS_CONNECTION_STRING` = your App Insights connection string.

> `ModelDeploymentName` and `AGENT_ID` are listed as optional in the README. In practice both
> are required: without `AGENT_ID` the agent lookup at [L1098](./function_app.py) fails, and
> the `ModelDeploymentName` default (`gpt-5.5`) is unlikely to match your deployment.

App Insights is technically optional — the code degrades to plain traces
([L58](./function_app.py)) — but without it you lose every `track_event` custom event and all
the KQL dashboards in [ANALYTICS_KQL_QUERIES.md](./ANALYTICS_KQL_QUERIES.md).

### Platform settings

Set automatically when you create a Python Function App. Verify they exist:

- ☐ `FUNCTIONS_WORKER_RUNTIME` = `python`
- ☐ `AzureWebJobsStorage` = storage connection string

> **`AzureWebJobsFeatureFlags=EnableWorkerIndexing` is not needed** on current runtimes — the
> Python v2 model is the default. The README still lists it as required; harmless if present,
> but not something to add on a new app.

### Recommended

- ☐ `MAX_CONVERSATION_TURNS` = `8` — caps history before the context window overflows
      ([L1109](./function_app.py)). Set `0` to disable. This exists because of a real
      `context_length_exceeded` failure; do not remove it casually.
- ☐ `REQUIRE_USER_ID` = `true` — reject any call that carries no authenticated identity.
      Turn it on once every caller sends `user_id` (the exported Copilot Studio flows do; see
      [IDENTITY_SPOOFING_HARDENING.md](./IDENTITY_SPOOFING_HARDENING.md)); otherwise legitimate calls fail.
- ☐ `HR_REPLY_FROM_ADDRESS` — required only if you use `send_hr_answer`. See
      [SEND_HR_ANSWER_COPILOT_STUDIO_GUIDE.md](./SEND_HR_ANSWER_COPILOT_STUDIO_GUIDE.md).

- ☐ Click **Apply / Save**, then **restart** the Function App so settings load.

CLI alternative:

```powershell
az functionapp config appsettings set `
  --name "<FUNCTION_APP_NAME>" `
  --resource-group "<RESOURCE_GROUP>" `
  --settings `
    "AIProjectEndpoint=https://<resource>.services.ai.azure.com/api/projects/<project>" `
    "ModelDeploymentName=<deployment-name>" `
    "AGENT_ID=<agent-name>" `
    "MAX_CONVERSATION_TURNS=8"
```

---

## 8. Verify

- ☐ Call the endpoint:

```powershell
$body = @{ message = "What is the open enrollment deadline?" } | ConvertTo-Json

Invoke-RestMethod `
  -Uri "https://<FUNCTION_APP>.azurewebsites.net/api/agent_httptrigger?code=<FUNCTION_KEY>" `
  -Method POST -ContentType "application/json" -Body $body
```

- ☐ Expect `message`, `threadId`, and `canAnswer` in the response.
- ☐ Send a deliberately unanswerable question and confirm `canAnswer` is `false` — this is the
      signal the HR escalation depends on, so test it explicitly.
- ☐ Send a second call passing the returned `threadId` as `threadid` and confirm the agent
      retains context.
- ☐ In App Insights, confirm a custom event appears (`customEvents | take 10`).

---

## Reference - all environment variables

Every variable the code reads, with the line that reads it.

| Variable | Line | Required | Purpose |
|---|---|---|---|
| `AIProjectEndpoint` | 1078 | **Yes** | Foundry project endpoint. Missing → `500` |
| `AGENT_ID` | 1080 | **Yes** | Agent **name** to serve requests |
| `ModelDeploymentName` | 1079 | **Yes** in practice | Model deployment name. Defaults to `gpt-5.5` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | 58 | Recommended | Custom events; without it, traces only |
| `MAX_CONVERSATION_TURNS` | 1109 | Recommended | Turn cap before rollover. Default `8` |
| `ENABLE_SUMMARY_CARRYOVER` | 1139 | Optional | Carry a summary into a new conversation. Default on |
| `REQUIRE_USER_ID` | 1019 | Recommended | Fail closed: reject calls with no authenticated `user_id`. See [IDENTITY_SPOOFING_HARDENING.md](./IDENTITY_SPOOFING_HARDENING.md) |
| `IDENTITY_GUARD_MODE` | 258 | Optional | Leave unset (`enforce`). `monitor` only logs identity-override attempts and does **not** protect requests; use it briefly during rollout, then remove it. Any other value enforces. See [IDENTITY_SPOOFING_HARDENING.md](./IDENTITY_SPOOFING_HARDENING.md) |
| `AGENT_INSTRUCTIONS_TEMPLATE` | 1047 | Optional | Template with `{placeholders}`, filled from `parameters`. The exported Flow A sends `user_id` and `user_full_name`, so a template may use both |
| `NO_ANSWER_MARKERS` | 582 | Optional | `;`-separated refusal phrases driving `canAnswer` |
| `CITATION_BASE_URL` | 644 | Optional | Base URL to turn file names into clickable citations |
| `DEBUG_RAW_RESPONSE` | 935 | Optional | Log raw request bodies when JSON parsing fails |
| `TELEMETRY_FLUSH` | 124 | Optional | Telemetry flush behaviour. `false` skips the per-event flush |
| `TELEMETRY_FLUSH_TIMEOUT` | 131 | Optional | Max seconds a request waits for the telemetry flush. Default `2` |

Used by the **other** routes in the same app, not by `agent_httptrigger`:

| Variable | Route | Purpose |
|---|---|---|
| `HR_ALLOWED_RECIPIENTS` | `send_hr_email` | Allow-list for question recipients |
| `MAX_RECIPIENTS` | `send_hr_email` | Fan-out cap. Default `10` |
| `HR_REPLY_FROM_ADDRESS` | `send_hr_answer` | **Required** for that route — shared sender mailbox |
| `HR_REPLY_ALLOWED_RECIPIENTS` | `send_hr_answer` | Optional allow-list for answer recipients |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `500` — *Missing AIProjectEndpoint* | Setting absent | Step 7; restart the app |
| `401` / `403` from Foundry | Managed identity lacks the role | Step 6. Owner/Contributor do **not** work |
| Agent not found | `AGENT_ID` holds a GUID instead of the agent name | Use the agent **name** |
| `DefaultAzureCredential failed` | Identity off | Step 5 |
| Model deployment not found | `ModelDeploymentName` mismatch | Copy the deployment name exactly |
| `canAnswer` always `true` | Agent never emits a refusal marker | Add the `NO_ANSWER` instruction (Step 3) |
| `context_length_exceeded` | Turn cap disabled or too high | Set `MAX_CONVERSATION_TURNS=8` |
| No custom events in App Insights | Connection string absent | Step 7 |
| Answers have no citations | Agent not instructed to cite, or no knowledge source | Step 4 |

---

## Related documents

- [README.md](./README.md) — project overview
- [SEND_HR_ANSWER_COPILOT_STUDIO_GUIDE.md](./SEND_HR_ANSWER_COPILOT_STUDIO_GUIDE.md) — email delivery route
- [EMAIL_HR_DEPLOYMENT_CHECKLIST.md](./EMAIL_HR_DEPLOYMENT_CHECKLIST.md) — Graph and Exchange setup
- [COPILOT_STUDIO_SETUP_GUIDE.md](./COPILOT_STUDIO_SETUP_GUIDE.md) — agent and flow authoring
- [ANALYTICS_KQL_QUERIES.md](./ANALYTICS_KQL_QUERIES.md) — telemetry queries
