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
- ☐ The email is always sent **from the employee's own mailbox** (`user_email`), so HR sees
  the request coming directly from them. This requires the managed identity's `Mail.Send`
  permission to cover employee mailboxes — see Sections 4 and 5.
- ☐ Note these values before starting (you will reuse them):
  - Function App name and resource group.
  - HR destination mailbox (e.g. `OpenEnrollment@panynj.gov`).

---

## 1. Azure Function App — Application Settings

Location: **Azure Portal → Function App → Settings → Environment variables** (Application settings tab).

- ☐ (Recommended) Add `HR_ALLOWED_RECIPIENTS` = comma/semicolon separated list of addresses
  or domains the caller may email, e.g. `OpenEnrollment@panynj.gov;benefits@panynj.gov`
  or just `panynj.gov`. Without it, any caller holding the function key can direct email to
  **any** address from the employee's mailbox.
- ☐ (Optional) Add `MAX_RECIPIENTS` = maximum recipients allowed per request
  (default `10`; set `0` to disable the cap).
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
	"HR_ALLOWED_RECIPIENTS=OpenEnrollment@panynj.gov"
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
> mailbox. Section 4 scopes it to the assistant's users — do not skip it.

---

## 4. Exchange Online — scope sending with an Application Access Policy

> Done in **Exchange Online PowerShell** (no Portal UI). Because the Function sends **as the
> employee**, the policy must cover every mailbox that may use the assistant.

> ⚠️ **Security note:** `Mail.Send` application permission lets the identity send email as any
> mailbox in scope. Scoping it to a group of assistant users (rather than the whole tenant) is
> strongly recommended, and this capability should be security-reviewed before production.

- ☐ Install/connect:
```powershell
Install-Module ExchangeOnlineManagement -Scope CurrentUser
Connect-ExchangeOnline -UserPrincipalName admin@<tenant>.onmicrosoft.com
```
- ☐ Create a mail-enabled security group containing the employees allowed to use the
  assistant, e.g. `benefits-assistant-users@panynj.gov`.
- ☐ Create the policy using the managed identity's **Application (client) ID** (Section 2):
```powershell
New-ApplicationAccessPolicy `
  -AppId "<managed-identity-application-id>" `
  -PolicyScopeGroupId "benefits-assistant-users@panynj.gov" `
  -AccessRight RestrictAccess `
  -Description "Benefits assistant may send only as enrolled assistant users"
```
- ☐ Test the scope:
```powershell
# A member of the group -> Granted
Test-ApplicationAccessPolicy -Identity steven.choy@panynj.gov -AppId "<application-id>"
# A non-member -> Denied
Test-ApplicationAccessPolicy -Identity someone.else@panynj.gov -AppId "<application-id>"
```
- ☐ Confirm `AccessCheckResult = Granted` for group members and `Denied` otherwise.
- ☐ Allow up to ~30 minutes for the policy to take effect.

---

## 5. Sender identity (the employee)

The email is always sent **from the signed-in employee's own mailbox**, using the
`user_email` value passed in from Copilot Studio. There is no shared sending mailbox.

- ☐ Confirm each assistant user has a **licensed Exchange Online mailbox**.
- ☐ Confirm those mailboxes are members of the group scoped in Section 4.
- ☐ Confirm the destination HR mailbox (passed as `to_address`) can receive mail from
  internal users.
- ☐ The employee's name and email are also written into the email body for traceability.
- ☐ A copy is saved to the employee's **Sent Items** (`saveToSentItems: true`).

### Requirement: the agent must be authenticated
`user_email` is **required** — the Function returns `400` without it.

- ☐ Copilot Studio → **Settings → Security → Authentication** must be set to
  **Authenticate with Microsoft** (or Teams SSO).
- ☐ With **No authentication**, `System.User.PrincipalName` is empty, `user_email` arrives
  blank, and the call fails with `400 Missing required parameter 'user_email'`.

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

- ☐ Open the flow/action in **Power Automate** (`gov.flow.microsoft.us` — the GCC portal; the commercial `make.powerautomate.com` will not show your tenant's flows), same environment.
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
	  - `user_email` → **System → User.PrincipalName** (required; see Section 5)
	  - `conversation_id` → `threadId` from the agent action
	  - `to_address` → the HR mailbox(es); one address, or several separated by `;`
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
- ☐ The flow must define **six** text inputs and forward them in the JSON body:
  `question`, `user_full_name`, `user_id`, `conversation_id`, `user_email`, `to_address`.
- ☐ Use the **built-in HTTP** action (not the *HTTP with Microsoft Entra ID* connector, which
  restricts calls to a pre-configured `BaseResourceUri` and will return 400).

---

## 10. End-to-end testing

- ☐ **Direct function test** (after Sections 1–5a):
```powershell
curl -X POST "https://<FUNCTION_APP>.azurewebsites.net/api/send_hr_email?code=<FUNCTION_KEY>" `
  -H "Content-Type: application/json" `
  -d '{"question":"Can I enroll in the \"Choice Plus\" plan?","user_full_name":"Steven Choy","user_id":"SCHOY","user_email":"steven.choy@panynj.gov","to_address":"OpenEnrollment@panynj.gov","conversation_id":"conv_123"}'
```
  - ☐ Expect `{"sent": true, ...}` and the email arriving in the HR mailbox.
  - ☐ Confirm the received email's **From** address is the employee (`user_email`), and a
    copy appears in that employee's **Sent Items**.
  - ☐ If `502 Authorization_RequestDenied` → Section 3 not propagated / missing.
  - ☐ If `502 ErrorAccessDenied` → the Section 4 policy does not cover that employee's
    mailbox.
  - ☐ If `400 Missing required parameter 'user_email'` → the caller did not supply it.
- ☐ **Agent instruction test** (Section 6): ask an off-topic question; confirm function log
  shows `canAnswer=false`.
- ☐ **User identity test** (Section 5): in Teams, trigger the email and confirm the function
  log line `HR email sent (... as <user email>)` shows the signed-in employee's address.
  If the call fails with `400`, authentication is not enabled or `user_email` is not passed.
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
| `HR_ALLOWED_RECIPIENTS` | Function App settings | Optional allow-list restricting `to_address`; every recipient must match |
| `MAX_RECIPIENTS` | Function App settings | Optional cap on recipients per request (default 10) |
| `to_address` input | Power Automate flow + topic | Destination mailbox(es); `;`-separated for multiple |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Function App settings | Telemetry/logging |
| `Mail.Send` (Application) | Microsoft Graph, via PowerShell | Granted to MI object id |
| Application Access Policy | Exchange Online PowerShell | Scope MI to the assistant's user mailboxes |
| `NO_ANSWER` instruction | Foundry agent instructions | Deterministic no-answer signal |
| `canAnswer` handling | Copilot Studio topic | Drives the email offer |
| Authentication | Copilot Studio → Settings → Security | Required for `System.User.PrincipalName` |
| `user_email` input | Power Automate flow + topic | Employee address — required; used as the sender |
| `addProperty` body | Power Automate — agent action HTTP body | JSON-escapes user text |
