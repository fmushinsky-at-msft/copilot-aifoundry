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

> **Sections 8 and 9 have a detailed click-by-click companion guide:**
> [COPILOT_STUDIO_SETUP_GUIDE.md](./COPILOT_STUDIO_SETUP_GUIDE.md)

---

## 0. Prerequisites

- ☐ You have **admin** rights (or a co-admin) for:
  - Azure subscription (Contributor on the Function App).
  - Microsoft Entra ID role able to grant app roles (**Privileged Role Administrator** or **Global Administrator**).
  - **Exchange Online** administrator (for the Application Access Policy).
  - **Copilot Studio** maker access to the agent, in the correct environment.
- ☐ The Function code (`function_app.py`) with the `send_hr_email` route, the `canAnswer`
  flag and `user_email` support is **deployed** to the Function App.
- ☐ Decide whether the email should be sent from the **shared mailbox with Reply-To set to
  the employee** (default, recommended) or **from the employee's own mailbox**
  (`SEND_AS_USER=true`). See Section 5a.
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
- ☐ (Optional) Add `SEND_AS_USER` = `true` **only** if the email must originate from the
  employee's own mailbox instead of the shared mailbox. See Section 5a before enabling —
  this requires broader `Mail.Send` scope and a security review. Leave unset for the
  recommended Reply-To behaviour.
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

## 5a. Who the email comes from (user identity)

The employee's email address is captured from the signed-in Teams user and passed to the
Function as `user_email`. It is used in two ways:

| Mode | `SEND_AS_USER` | Email is sent from | Reply goes to | Extra permissions |
|---|---|---|---|---|
| **Reply-To (default, recommended)** | unset / `false` | the shared mailbox | the **employee** (via `Reply-To`) | none beyond Section 4 |
| **Send as user** | `true` | the **employee's own mailbox** | the employee | ⚠️ requires widening Section 4 |

- ☐ Decide which mode you need. **Default (Reply-To) is recommended** — HR still replies
  straight to the employee, with no impersonation risk.
- ☐ The employee's name and email are also written into the email body for traceability.

> ⚠️ **Before enabling `SEND_AS_USER=true`:** the managed identity must hold `Mail.Send`
> over each employee's mailbox, which means **widening or removing** the Application Access
> Policy created in Section 4. That would allow the Function to send email **as any user in
> scope** — treat this as impersonation capability and obtain a security review first.
> If `SEND_AS_USER` is on but no `user_email` is supplied, the Function safely falls back to
> the shared mailbox and logs a warning.

### Requirement: the agent must be authenticated
`user_email` is only available when the agent knows who the user is.

- ☐ Copilot Studio → **Settings → Security → Authentication** must be set to
  **Authenticate with Microsoft** (or Teams SSO).
- ☐ With **No authentication**, `System.User.PrincipalName` is empty, `user_email` arrives
  blank, and the email falls back to shared-mailbox-only with no Reply-To.

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

For the **agent action** (`agent_httptrigger`), build the HTTP body with the
`addProperty` pattern instead of hand-typed JSON.

- ☐ Open the flow/action in **Power Automate** (make.powerautomate.com, same environment).
- ☐ Add a **Compose** action before the **HTTP** action.
- ☐ In Compose **Inputs**, use an expression like (adjust field sources):
  ```
  addProperty(addProperty(json('{}'), 'message', triggerBody()?['text']), 'threadid', triggerBody()?['text_1'])
  ```
- ☐ In the **HTTP** action **Body**, reference `@{outputs('Compose')}`.
- ☐ Keep header **Content-Type: application/json**.
- ☐ **Save**.

---

## 8. Copilot Studio — topic logic (offer + send)

> Detailed steps: [COPILOT_STUDIO_SETUP_GUIDE.md → Part 2](./COPILOT_STUDIO_SETUP_GUIDE.md#part-2--topic-logic-offer--send-section-8)

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
	  - `user_full_name` → user profile / `text_3` (or **System → User.DisplayName**)
	  - `user_id` → `text_2`
	  - `user_email` → **System → User.PrincipalName** (requires authentication, Section 5a)
	  - `conversation_id` → `threadId` from the agent action
	- ☐ After it returns → **Send a message** with the confirmation (`message`:
	  "Your question has been emailed to HR.").
	- ☐ On **No** → send a courteous closing message.
- ☐ On the **true** branch (`canAnswer = true`) → show `message` normally.
- ☐ **Save** the topic and **Publish** the agent.

---

## 9. Connect the `send_hr_email` action

> Detailed steps: [COPILOT_STUDIO_SETUP_GUIDE.md → Part 1](./COPILOT_STUDIO_SETUP_GUIDE.md#part-1--create-the-send_hr_email-flow-section-9)

- ☐ Ensure Copilot Studio has an action/connector (or Power Automate flow) that POSTs to
  `https://<FUNCTION_APP>.azurewebsites.net/api/send_hr_email` including the **function key**
  (`?code=<key>` or an `x-functions-key` header).
- ☐ The flow must define **five** text inputs and forward them in the JSON body:
  `question`, `user_full_name`, `user_id`, `conversation_id`, `user_email`.
- ☐ Use the **built-in HTTP** action (not the *HTTP with Microsoft Entra ID* connector, which
  restricts calls to a pre-configured `BaseResourceUri` and will return 400).

---

## 10. End-to-end testing

- ☐ **Direct function test** (after Sections 1–5a):
```powershell
curl -X POST "https://<FUNCTION_APP>.azurewebsites.net/api/send_hr_email?code=<FUNCTION_KEY>" `
  -H "Content-Type: application/json" `
  -d '{"question":"Can I enroll in the \"Choice Plus\" plan?","user_full_name":"Steven Choy","user_id":"SCHOY","user_email":"steven.choy@panynj.gov","conversation_id":"conv_123"}'
```
  - ☐ Expect `{"sent": true, ...}` and the email arriving in the HR mailbox.
  - ☐ Open the received email and click **Reply** — it must address
    `user_email` (the employee), not the shared mailbox.
  - ☐ If `502 Authorization_RequestDenied` → Section 3 not propagated / missing.
  - ☐ If `502 ErrorAccessDenied` on the mailbox → Section 4 policy excludes it
    (with `SEND_AS_USER=true`, the policy must also cover the employee's mailbox).
- ☐ **Agent instruction test** (Section 6): ask an off-topic question; confirm function log
  shows `canAnswer=false`.
- ☐ **User identity test** (Section 5a): in Teams, trigger the email and confirm the function
  log line `HR email sent (... replyTo=<user email>)` shows a real address, not `none`.
  If it shows `none`, authentication is not enabled or `user_email` is not being passed.
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
| `SEND_AS_USER` | Function App settings | Optional; `true` sends from the employee's mailbox (needs wider `Mail.Send`) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Function App settings | Telemetry/logging |
| `Mail.Send` (Application) | Microsoft Graph, via PowerShell | Granted to MI object id |
| Application Access Policy | Exchange Online PowerShell | Restrict MI to the shared mailbox |
| `NO_ANSWER` instruction | Foundry agent instructions | Deterministic no-answer signal |
| `canAnswer` handling | Copilot Studio topic | Drives the email offer |
| Authentication | Copilot Studio → Settings → Security | Required for `System.User.PrincipalName` |
| `user_email` input | Power Automate flow + topic | Employee address → Reply-To / sender |
| `addProperty` body | Power Automate — agent action HTTP body | JSON-escapes user text |
