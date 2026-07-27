# Deployment Checklist — "Email HR when the agent can't answer"

This checklist covers **every change outside the function code** required to enable the
feature: when the Benefit agent cannot answer a question, the Teams agent offers to email
the question to HR, and the Azure Function sends that email via Microsoft Graph.

Feature spans five systems:
1. Azure Function App (configuration + identity)
2. Microsoft Entra ID / Microsoft Graph (permissions)
3. Exchange Online (mailbox + access policy)
4. Azure AI Foundry (agent instruction)
5. Copilot Studio + Power Automate (topic logic + request construction)

> Legend: ☐ = to do. Work top to bottom; later steps assume earlier ones are done.

---

## 0. Prerequisites

- ☐ You have **admin** rights (or a co-admin) for:
  - Azure subscription (Contributor on the Function App).
  - Microsoft Entra ID role able to grant app roles (**Privileged Role Administrator** or **Global Administrator**).
  - **Exchange Online** administrator (for the Application Access Policy).
  - **Copilot Studio** maker access to the agent, in the correct environment.
- ☐ The Function code (`function_app.py`) with the `send_hr_email` route and `canAnswer`
  flag is **deployed** to the Function App.
- ☐ Note these values before starting (you will reuse them):
  - Function App name and resource group.
  - HR destination mailbox (e.g. `OpenEnrollment@panynj.gov`).
  - Sender shared mailbox (e.g. `benefits-bot@panynj.gov`).

---

## 1. Azure Function App — Application Settings

Location: **Azure Portal → Function App → Settings → Environment variables** (Application settings tab).

- ☐ Add `HR_TO_ADDRESS` = the HR destination mailbox (e.g. `OpenEnrollment@panynj.gov`).
- ☐ Add `HR_FROM_ADDRESS` = the shared mailbox / service account to send **as**
  (e.g. `benefits-bot@panynj.gov`).
- ☐ (If not already present) `APPLICATIONINSIGHTS_CONNECTION_STRING` = your App Insights
  connection string (so `logging.info`/error traces are visible).
- ☐ Click **Apply / Save**.
- ☐ **Restart** the Function App (Overview → Restart) so new settings load.

CLI alternative (PowerShell):
```powershell
az functionapp config appsettings set `
  --name "<FUNCTION_APP_NAME>" `
  --resource-group "<RESOURCE_GROUP>" `
  --settings `
	"HR_TO_ADDRESS=OpenEnrollment@panynj.gov" `
	"HR_FROM_ADDRESS=benefits-bot@panynj.gov"
```

---

## 2. Azure Function App — Managed Identity

Location: **Azure Portal → Function App → Settings → Identity**.

- ☐ Open the **System assigned** tab.
- ☐ Confirm **Status = On** (it should already be On because the agent call uses it).
  If Off, toggle **On → Save → Yes**.
- ☐ Copy the **Object (principal) ID** — you need it in Section 3.
- ☐ Also note the identity's **Application (client) ID**: go to
  **Microsoft Entra ID → Enterprise applications**, filter by the Function App name,
  open it, and copy **Application ID**. You need this in Section 4.

---

## 3. Microsoft Graph — grant `Mail.Send` (Application permission)

> The Azure Portal has **no UI** to assign Microsoft Graph application permissions to a
> **managed identity**. This must be done with **Microsoft Graph PowerShell**. An admin who
> can grant app roles must run it. The Portal is only used afterward to *verify*.

- ☐ Install the module (once):
```powershell
Install-Module Microsoft.Graph -Scope CurrentUser
```
- ☐ Connect as an admin:
```powershell
Connect-MgGraph -Scopes "AppRoleAssignment.ReadWrite.All","Application.Read.All"
```
- ☐ Assign `Mail.Send` (application) to the managed identity:
```powershell
$miObjectId = "<managed-identity-object-id>"   # from Section 2

# Microsoft Graph service principal (well-known appId)
$graph = Get-MgServicePrincipal -Filter "appId eq '00000003-0000-0000-c000-000000000000'"

# The Mail.Send application app role
$appRole = $graph.AppRoles | Where-Object {
	$_.Value -eq "Mail.Send" -and $_.AllowedMemberTypes -contains "Application"
}

New-MgServicePrincipalAppRoleAssignment `
  -ServicePrincipalId $miObjectId `
  -PrincipalId $miObjectId `
  -ResourceId $graph.Id `
  -AppRoleId $appRole.Id
```
- ☐ **Verify** in Portal: **Microsoft Entra ID → Enterprise applications** → open the
  managed identity → **Permissions** → confirm **Mail.Send** is listed.
- ☐ Allow a few minutes for propagation.

> Security note: `Mail.Send` application permission by default allows sending as **any**
> mailbox. Section 5 restricts it to the single shared mailbox — do not skip it.

---

## 4. Exchange Online — restrict sending with an Application Access Policy

> Done in **Exchange Online PowerShell** (no Portal UI). This limits the managed identity so
> it can send **only** as the benefits shared mailbox.

- ☐ Install/connect:
```powershell
Install-Module ExchangeOnlineManagement -Scope CurrentUser
Connect-ExchangeOnline -UserPrincipalName admin@<tenant>.onmicrosoft.com
```
- ☐ (Recommended) Create a mail-enabled security group containing the sender mailbox, e.g.
  `bot-allowed-senders@panynj.gov` with member `benefits-bot@panynj.gov`.
  (Or scope the policy directly to the mailbox address.)
- ☐ Create the policy using the managed identity's **Application (client) ID** (Section 2):
```powershell
New-ApplicationAccessPolicy `
  -AppId "<managed-identity-application-id>" `
  -PolicyScopeGroupId "bot-allowed-senders@panynj.gov" `
  -AccessRight RestrictAccess `
  -Description "Benefits bot may send only as the benefits shared mailbox"
```
- ☐ Test the scope:
```powershell
# Allowed mailbox -> Granted
Test-ApplicationAccessPolicy -Identity benefits-bot@panynj.gov -AppId "<application-id>"
# Any other mailbox -> Denied
Test-ApplicationAccessPolicy -Identity someone.else@panynj.gov  -AppId "<application-id>"
```
- ☐ Confirm `AccessCheckResult = Granted` for the shared mailbox and `Denied` otherwise.
- ☐ Allow up to ~30 minutes for the policy to take effect.

---

## 5. Sender mailbox

- ☐ Ensure `HR_FROM_ADDRESS` (e.g. `benefits-bot@panynj.gov`) exists as a
  **shared mailbox** or licensed service account.
- ☐ Confirm HR (`HR_TO_ADDRESS`) can receive external/internal mail from it.

---

## 6. Azure AI Foundry — add the `NO_ANSWER` instruction

Location: **https://ai.azure.com → project `proj-default` → Agents → PA-Health-Benefit-Agent**.

- ☐ Open the agent.
- ☐ In the **Instructions** (system prompt) field, append:
  ```
  When you cannot answer the question from the available Benefit Open Enrollment
  information, include the exact token NO_ANSWER somewhere in your reply.
  ```
- ☐ **Save** (publishes a new agent version).
- ☐ (Optional) In the **playground**, ask an off-topic question and confirm the raw reply
  contains `NO_ANSWER`. The function strips this token before the user sees it.
- ☐ No function redeploy needed — the function references the agent by name.

> How the function uses it: `detect_no_answer()` sets `canAnswer=false` when `NO_ANSWER`
> (or a fallback phrase / empty answer) is present, then strips `NO_ANSWER` from the
> user-visible `message`.

---

## 7. Copilot Studio / Power Automate — request body escaping

> Prevents user text containing `"` from breaking the JSON sent to the Function.

For **both** the agent action and the `send_hr_email` action, build the HTTP body with the
`addProperty` pattern instead of hand-typed JSON.

- ☐ Open the flow/action in **Power Automate** (make.powerautomate.com, same environment).
- ☐ Add a **Compose** action before the **HTTP** action.
- ☐ In Compose **Inputs**, use an expression like (adjust field sources):
  ```
  addProperty(addProperty(json('{}'), 'question', triggerBody()?['text']), 'conversation_id', variables('threadId'))
  ```
- ☐ In the **HTTP** action **Body**, reference `@{outputs('Compose')}`.
- ☐ Keep header **Content-Type: application/json**.
- ☐ **Save**.

---

## 8. Copilot Studio — topic logic (offer + send)

Location: **Copilot Studio → your agent → Topics → the topic that calls the agent action**.

- ☐ Confirm the **Call an action** node (agent) exposes outputs `message`, `threadId`,
  and `canAnswer`. If `canAnswer` is missing, run the action once to refresh its schema.
- ☐ Add a **Condition**: `canAnswer` **is equal to** `false`.
- ☐ On the **false** branch:
  - ☐ (Optional) **Send a message** showing `message` (the apology).
  - ☐ Add a **Question** node:
	- Prompt: "I couldn't find that in the benefits materials. Would you like me to email your question to HR?"
	- Identify: **Multiple choice** → options **Yes** and **No** → save to `Topic.EmailHR`.
  - ☐ Add a **Condition**: `Topic.EmailHR` **is** `Yes`.
	- ☐ On **Yes** → **Call an action** → `send_hr_email`, passing:
	  - `question` → original user message
	  - `user_full_name` → user profile / `text_3`
	  - `user_id` → `text_2`
	  - `conversation_id` → `threadId` from the agent action
	  - (Build this body with the `addProperty` escaping from Section 7.)
	- ☐ After it returns → **Send a message** with the confirmation (`message`:
	  "Your question has been emailed to HR.").
	- ☐ On **No** → send a courteous closing message.
- ☐ On the **true** branch (`canAnswer = true`) → show `message` normally.
- ☐ **Save** the topic and **Publish** the agent.

---

## 9. Connect the `send_hr_email` action

- ☐ Ensure Copilot Studio has an action/connector (or Power Automate flow) that POSTs to
  `https://<FUNCTION_APP>.azurewebsites.net/api/send_hr_email` including the **function key**
  (`?code=<key>` or an `x-functions-key` header).

---

## 10. End-to-end testing

- ☐ **Direct function test** (after Sections 1–5):
```powershell
curl -X POST "https://<FUNCTION_APP>.azurewebsites.net/api/send_hr_email?code=<FUNCTION_KEY>" `
  -H "Content-Type: application/json" `
  -d '{"question":"Can I enroll in the \"Choice Plus\" plan?","user_full_name":"Steven Choy","user_id":"SCHOY","conversation_id":"conv_123"}'
```
  - ☐ Expect `{"sent": true, ...}` and the email arriving in the HR mailbox.
  - ☐ If `502 Authorization_RequestDenied` → Section 3 not propagated / missing.
  - ☐ If `502 ErrorAccessDenied` on the mailbox → Section 4 policy excludes it.
- ☐ **Agent instruction test** (Section 6): ask an off-topic question; confirm function log
  shows `canAnswer=false`.
- ☐ **Teams end-to-end**: ask an off-topic question → confirm the Yes/No prompt appears →
  choose **Yes** → confirm HR receives the email and the user sees the confirmation.
- ☐ **Quote test**: ask a question containing `"` → confirm no `Request JSON parse failed`
  warning and a normal answer (validates Section 7).

---

## 11. Rollback / disable

- ☐ To disable the feature without code changes: in Copilot Studio, remove or deactivate the
  `canAnswer = false` branch (the agent still answers normally).
- ☐ To revoke email sending: remove the `Mail.Send` app-role assignment (Section 3) and/or
  delete the Application Access Policy (Section 4).

---

## Reference — settings summary

| Setting | Where | Value / Notes |
|---|---|---|
| `HR_TO_ADDRESS` | Function App settings | HR destination mailbox |
| `HR_FROM_ADDRESS` | Function App settings | Shared mailbox to send as |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Function App settings | Telemetry/logging |
| `Mail.Send` (Application) | Microsoft Graph, via PowerShell | Granted to MI object id |
| Application Access Policy | Exchange Online PowerShell | Restrict MI to the shared mailbox |
| `NO_ANSWER` instruction | Foundry agent instructions | Deterministic no-answer signal |
| `canAnswer` handling | Copilot Studio topic | Drives the email offer |
| `addProperty` body | Power Automate HTTP actions | JSON-escapes user text |
