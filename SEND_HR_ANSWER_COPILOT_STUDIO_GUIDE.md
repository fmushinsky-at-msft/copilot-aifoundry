# Plugging `send_hr_answer` into Copilot Studio

How to wire the **`send_hr_answer`** Azure Function into the Anonymous HR Relay so the
representative's answer is **emailed back** to the employee who asked.

This is the **return leg** of the relay:

```
Employee asks  ──►  agent can't answer  ──►  send_hr_email  ──►  HR mailbox
                                                                      │
                                                                 HR replies
                                                                 on a card
                                                                      ▼
Employee's inbox  ◄──  send_hr_answer  ◄──  Anonymous HR Relay flow
```

It replaces the **proactive Teams message**, which is blocked in this tenant by a
platform-side `403` from Microsoft Graph
(see [CONNECT_REP_OPTION_D_ANONYMOUS_RELAY.md](./CONNECT_REP_OPTION_D_ANONYMOUS_RELAY.md)).

> Legend: ☐ = to do. Work top to bottom; later steps assume earlier ones are done.

---

## Contents

- [1. What changes and what does not](#1-what-changes-and-what-does-not)
- [2. Prerequisites](#2-prerequisites)
- [3. Choose the shared sender mailbox](#3-choose-the-shared-sender-mailbox)
- [4. Exchange Online — scope the shared mailbox](#4-exchange-online--scope-the-shared-mailbox)
- [5. Azure Function App — application settings](#5-azure-function-app--application-settings)
- [6. Deploy and smoke-test the endpoint](#6-deploy-and-smoke-test-the-endpoint)
- [7. Power Automate — replace the delivery action](#7-power-automate--replace-the-delivery-action)
- [8. Handle the timeout branch](#8-handle-the-timeout-branch)
- [9. Tell the employee the answer is coming by email](#9-tell-the-employee-the-answer-is-coming-by-email)
- [10. End-to-end test](#10-end-to-end-test)
- [11. Telemetry](#11-telemetry)
- [12. Troubleshooting](#12-troubleshooting)
- [13. Rollback](#13-rollback)
- [Reference — API contract](#reference--api-contract)
- [Reference — settings summary](#reference--settings-summary)

---

## 1. What changes and what does not

| Piece | Status |
|---|---|
| `send_hr_email` (question → HR) | **Unchanged** |
| Adaptive card posted to the HR channel | **Unchanged** |
| Card submit → flow resumes | **Unchanged** |
| Delivery to the employee | **Replaced** — proactive Teams message ➜ `send_hr_answer` |
| Employee sees the answer in | Teams chat ➜ **their mailbox** |

Only the **last action** of the Anonymous HR Relay flow changes. Everything upstream stays
exactly as built.

### Anonymity is preserved

The employee's email says an HR team member answered — never *which* one:

- The endpoint accepts **no** responder name, address, or ID. Even if a caller supplied one
  it could not reach the message.
- The mail is sent **from a shared mailbox**, never from the representative.
- Replies land back in the shared mailbox, not in the representative's inbox.

HR still sees who asked, because `send_hr_email` sends **from the employee**. The
one-directional anonymity of the original design is intact.

---

## 2. Prerequisites

- ☐ The relay already works up to the point of delivery: card posts, HR submits, flow
  resumes. If not, fix that first — this guide only replaces the final step.
- ☐ `function_app.py` containing the `send_hr_answer` route is **deployed**.
- ☐ You have:
  - **Contributor** on the Function App.
  - **Exchange Online administrator** (for Section 4).
  - **Maker** access to the flow and the agent.
- ☐ Note these values — you will reuse them:
  - Function App name, e.g. `func-hrbenefit-dev003`.
  - The managed identity's **Application (client) ID**
    (`EMAIL_HR_DEPLOYMENT_CHECKLIST.md` §2).
  - A function key for the app.

---

## 3. Choose the shared sender mailbox

This is a **decision you must make before anything else works**, because it changes the
Exchange configuration in Section 4.

`send_hr_email` sends *from the employee*. `send_hr_answer` cannot do the same in reverse —
sending from the representative would put their name in the **From** line and destroy the
anonymity the whole design rests on.

So the reply is sent from a **shared mailbox**:

- ☐ Pick or create one, e.g. `hr-benefits@panynj.gov` or `OpenEnrollment@panynj.gov`.
- ☐ Prefer a mailbox HR already monitors — employees **will** reply to these messages, and
  those replies land there.
- ☐ It must be a real mailbox. A distribution list has no Sent Items and cannot be a
  `sendMail` sender.

> **Reusing the existing HR mailbox** (the one `send_hr_email` already targets) is usually
> the right call: HR watches it, and it needs no new provisioning. The trade-off is that
> inbound questions and outbound answers share one mailbox.

---

## 4. Exchange Online — scope the shared mailbox

> Done in **Exchange Online PowerShell** (no Portal UI). Requires the **Exchange
> Administrator** role, or membership of **Organization Management** for Section 4b.

Your current configuration scopes the managed identity to **employee** mailboxes so it can
send *as the employee*. It does **not** cover the shared mailbox. Until you extend it, every
call returns `502` with `ErrorAccessDenied`.

Exchange has two mechanisms here, and which one you use changes the commands:

| Mechanism | Status |
|---|---|
| Application Access Policy (`New-ApplicationAccessPolicy`) | **Legacy.** Microsoft says do not create new ones; deprecation is planned |
| RBAC for Applications (management scopes) | **Current.** Replaces Application Access Policies |

If your tenant already uses a policy, extending it is fine and is the smallest change.
Do **not** create a new policy from scratch — use 4b instead.

- ☐ Connect:
```powershell
Install-Module ExchangeOnlineManagement -Scope CurrentUser
Connect-ExchangeOnline -UserPrincipalName admin@<tenant>.onmicrosoft.com
```

- ☐ Find out which mechanism your tenant actually uses, and note the group name:
```powershell
Get-ApplicationAccessPolicy | Where-Object { $_.AppId -eq "<managed-identity-application-id>" }
```

Then follow **4a** if that returned a policy, or **4b** if it returned nothing.

### 4a — Existing Application Access Policy (legacy)

The scoping group may be a mail-enabled security group, a distribution list, or a
Microsoft 365 group. Add the shared mailbox to whichever it is:

```powershell
# Mail-enabled security group or distribution list
Add-DistributionGroupMember `
  -Identity "benefits-assistant-users@panynj.gov" `
  -Member "hr-benefits@panynj.gov"
```

- ☐ Confirm the identity may now send as the shared mailbox:
```powershell
Test-ApplicationAccessPolicy `
  -Identity hr-benefits@panynj.gov `
  -AppId "<managed-identity-application-id>"
```
- ☐ Confirm `AccessCheckResult = Granted`.

> ⚠️ **Nested groups do not work.** Only **direct** membership puts a mailbox in scope.
> Adding a group that contains the mailbox will silently fail to grant access.

### 4b — RBAC for Applications (current model)

If no policy exists, your tenant is using **RBAC for Applications**, which
[replaces Application Access Policies](https://learn.microsoft.com/exchange/permissions-exo/application-rbac).
Microsoft advises against creating new App Access Policies. Scope the shared mailbox with a
management scope instead:

```powershell
# One-time: register the pointer to the managed identity's service principal.
# Use the IDs from Enterprise applications, NOT App registrations.
New-ServicePrincipal `
  -AppId "<managed-identity-application-id>" `
  -ObjectId "<managed-identity-object-id>" `
  -DisplayName "HR Benefits Function"

# Scope: the mailboxes this app may send as.
New-ManagementScope `
  -Name "HR Benefits senders" `
  -RecipientRestrictionFilter "MemberOfGroup -eq '<distinguished-name-of-group>'"

New-ManagementRoleAssignment `
  -App "<managed-identity-object-id>" `
  -Role "Application Mail.Send" `
  -CustomResourceScope "HR Benefits senders"
```

- ☐ Get the group's **distinguished name** with `Get-Group "<group>" | Select DistinguishedName`.
- ☐ Verify:
```powershell
Test-ServicePrincipalAuthorization `
  -Identity "HR Benefits Function" `
  -Resource hr-benefits@panynj.gov | Format-Table
```
- ☐ Confirm `Application Mail.Send` appears with `InScope = True`.

> **Both models are additive.** An unscoped `Mail.Send` grant in Microsoft Entra ID stays in
> effect regardless of what you scope here. If you want real scoping, the Entra grant must be
> removed — otherwise the union of the two leaves the app effectively unscoped.

### Propagation

- ☐ Allow **30 minutes to 2 hours** for permission changes to take effect. Microsoft
  documents a cache that lives up to 2 hours for an app receiving traffic, and resets after
  30 minutes for an idle one. The `Test-` cmdlets bypass this cache, so they can report
  success while live calls still return `502`. If the test says `Granted`/`InScope` but the
  endpoint disagrees, you are waiting on the cache — do not start changing settings.

> ⚠️ **Security note:** this widens `Mail.Send` to include a mailbox that can email
> employees. Keep it scoped; never remove the scoping to "make it work".

---

## 5. Azure Function App — application settings

Location: **Azure Portal → Function App → Settings → Environment variables**
(Application settings tab).

- ☐ Add `HR_REPLY_FROM_ADDRESS` = the shared mailbox from Section 3,
  e.g. `hr-benefits@panynj.gov`. **Required** — without it every call returns `500`.
- ☐ (Optional) Add `HR_REPLY_ALLOWED_RECIPIENTS` = `panynj.gov`.
  Restricts who the endpoint may email. Leave it unset and the endpoint will deliver to any
  valid address; the Function logs a warning on every call to make that visible.
- ☐ Click **Apply / Save**.
- ☐ **Restart** the Function App (Overview → Restart) so new settings load.

CLI alternative (PowerShell):
```powershell
az functionapp config appsettings set `
  --name "<FUNCTION_APP_NAME>" `
  --resource-group "<RESOURCE_GROUP>" `
  --settings `
    "HR_REPLY_FROM_ADDRESS=hr-benefits@panynj.gov"

# Optional: restrict who may receive answers.
az functionapp config appsettings set `
  --name "<FUNCTION_APP_NAME>" `
  --resource-group "<RESOURCE_GROUP>" `
  --settings `
    "HR_REPLY_ALLOWED_RECIPIENTS=panynj.gov"
```

> **Worth setting even though it is optional.** Without it, anyone holding the function key
> can send mail from your HR mailbox to any address. Since `user_email` arrives from the
> flow, a wrong `text_N` mapping (Step 7.3) would also deliver an employee's answer
> somewhere unintended. The allow-list turns that into a `403` instead of a misdirected
> email.

> These are **separate** from `HR_ALLOWED_RECIPIENTS` used by `send_hr_email`. That one
> limits where questions go; these limit where answers go. Do not merge them.

---

## 6. Deploy and smoke-test the endpoint

Prove the Function works **before** touching the flow. Debugging one system is much easier
than debugging two.

- ☐ Deploy the updated `function_app.py`.
- ☐ Send yourself a test message:

```powershell
$body = @{
  answer         = "Yes, you can add a spouse during open enrollment.`nThe deadline is November 30."
  question       = "Can I add my spouse to my dental plan?"
  user_email     = "steven.choy@panynj.gov"
  user_full_name = "Steven Choy"
  agent_label    = "HR Benefits Assistant"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "https://<FUNCTION_APP>.azurewebsites.net/api/send_hr_answer?code=<FUNCTION_KEY>" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

- ☐ Expect `{"sent": true, "recipient": "steven.choy@panynj.gov", ...}`.
- ☐ Check the inbox. The message should show:
  - **From:** the shared mailbox (**not** a representative)
  - Your question quoted in grey
  - The answer, with the line break preserved
  - The 💬 disclosure line at the bottom

✅ **Checkpoint:** the email arrives and names no individual representative. Do not continue
until this passes — every later step depends on it.

---

## 7. Power Automate — replace the delivery action

Open the **Anonymous HR Relay** flow. The final action today is the proactive Teams message
(`Post as` = *Microsoft Copilot Studio agent*, `Post in` = *Chat with agent*) — the one
returning the `403`.

### Step 7.1 — Delete the blocked action
1. Click the **⋯** on the proactive Teams delivery action.
2. Select **Delete** → **OK**.

> Keep the card action and everything above it. Only the delivery action goes.

### Step 7.2 — Add the HTTP action
1. Hover the **arrow** where the deleted action was; a **+** circle appears. Click it.
2. Click **Add an action**.
3. Search for `HTTP`.
4. Choose the action named simply **HTTP** (globe icon, marked **Premium**).
5. Fill in the panel:
   - **URI:** `https://<FUNCTION_APP>.azurewebsites.net/api/send_hr_answer`
   - **Method:** open the dropdown → **POST**
   - **Headers:**
     - Key = `Content-Type`, Value = `application/json`
     - Key = `x-functions-key`, Value = `<FUNCTION_KEY>`
   - **Body:** see below

> Putting the key in an `x-functions-key` **header** rather than `?code=` keeps the secret
> out of URL logs. Same convention as
> [COPILOT_STUDIO_SETUP_GUIDE.md](./COPILOT_STUDIO_SETUP_GUIDE.md) Step 1.3.

### Step 7.3 — Build the body

```json
{
  "answer": "@{body('Post_adaptive_card_and_wait_for_a_response')?['data']?['answer']}",
  "question": "@{triggerBody()?['text']}",
  "user_email": "@{triggerBody()?['text_4']}",
  "user_full_name": "@{triggerBody()?['text_1']}",
  "conversation_id": "@{triggerBody()?['text_3']}",
  "agent_label": "HR Benefits Assistant"
}
```

Two fields need checking against **your** flow:

**`answer` — the card response path.** `?['data']?['answer']` assumes the card's input is
`id: "answer"`. To confirm: run the flow once, open the run history, expand
**Post adaptive card and wait for a response**, and read the raw **Outputs**. Use whatever
key actually appears under `data`.

**`user_email` — the trigger input.** Power Automate names trigger inputs `text`, `text_1`,
`text_2`, … in creation order. The mapping above assumes the standard order
(`question`, `user_full_name`, `user_id`, `conversation_id`, `user_email`, `to_address`).
To confirm: click in the Body box, open **Dynamic content** (lightning-bolt icon) and hover
each input — the tooltip shows its internal name.

> ⚠️ Getting `user_email` wrong sends the answer **to the wrong person**. Verify it rather
> than trusting the numbering.

✅ **Checkpoint:** the HTTP box shows Method `POST`, your URI, two headers, and the JSON body.

### Step 7.4 — Fail loudly, not silently
The HTTP action fails the run automatically on any non-2xx response, so a delivery failure
turns the run red. Nobody watches run history, though, so add a visible alert:

1. Add a **Post message in a chat or channel** action **after** the HTTP action.
2. Open its **⋯** → **Configure run after**.
3. Untick **is successful**; tick **has failed** and **has timed out**.
4. Post to the **HR channel** (never to the employee) with text such as:
   `⚠️ Could not email the answer for: @{triggerBody()?['text']}`

Without this, a delivery failure is invisible — HR believes they answered and the employee
never hears back.

---

## 8. Handle the timeout branch

> This gap exists in the current flow regardless of delivery method. Worth closing now.

If no representative submits the card, the flow currently ends silently and the employee
waits forever.

1. Select the **Post adaptive card and wait for a response** action.
2. Add a **parallel branch** (not a sequential step).
3. In the new branch add a second **HTTP** action, configured exactly as Step 7.2.
4. Open its **⋯** → **Configure run after** → untick **is successful**, tick
   **has timed out** and **has failed**.
5. Body:

```json
{
  "answer": "We could not reach a benefits representative in time. Please email hr-benefits@panynj.gov and someone will follow up with you directly.",
  "question": "@{triggerBody()?['text']}",
  "user_email": "@{triggerBody()?['text_4']}",
  "user_full_name": "@{triggerBody()?['text_1']}",
  "conversation_id": "@{triggerBody()?['text_3']}",
  "agent_label": "HR Benefits Assistant"
}
```

Now every question ends in a reply — an answer or an apology, never silence.

---

## 9. Tell the employee the answer is coming by email

The agent currently implies a reply will arrive **in chat**. That is now wrong and will make
employees think the system failed.

- ☐ In **Copilot Studio**, open the topic that calls the relay.
- ☐ Find the **Send a message** node after the escalation action.
- ☐ Change the text to set the right expectation, e.g.:

  > Thanks — I've passed your question to the HR benefits team.
  > **They'll email you the answer**, usually within one business day.

- ☐ **Save**, then **Publish** the agent.

> Skipping this is the most common cause of "it isn't working" reports after this change.
> The email arrives; the employee simply never thought to look.

---

## 10. End-to-end test

- ☐ In **Teams**, ask the agent something it cannot answer.
- ☐ Confirm the agent says the reply will arrive **by email**.
- ☐ In the HR channel, confirm the card appears.
- ☐ As a representative, type an answer and **Submit**.
- ☐ Confirm the card shows submitted.
- ☐ Within a minute, the **employee's mailbox** has the answer.
- ☐ Open it and verify:
  - **From** = the shared mailbox, **not** the representative
  - The representative's name appears **nowhere**
  - Line breaks render correctly
  - The 💬 disclosure line is present
- ☐ Check the flow run is green end to end.
- ☐ **Timeout test:** ask another question and leave the card alone until it expires.
  Confirm the fallback email arrives.

---

## 11. Telemetry

The Function emits two App Insights custom events, matching the existing convention:

| Event | When | Key dimensions |
|---|---|---|
| `HrAnswerDelivered` | Graph accepted the message | `userEmail`, `conversationId`, `graphStatus`, `agentLabel`, `answerLength` |
| `HrAnswerDeliveryFailed` | Graph or the Function failed | `userEmail`, `conversationId`, `errorCode`, `error` |

Failed deliveries in the last day:

```kusto
customEvents
| where name == "HrAnswerDeliveryFailed"
| where timestamp > ago(1d)
| project timestamp,
          userEmail    = tostring(customDimensions.userEmail),
          errorCode    = tostring(customDimensions.errorCode),
          error        = tostring(customDimensions.error)
| order by timestamp desc
```

Round-trip completion rate — questions sent to HR vs answers delivered:

```kusto
let sent      = customEvents | where name == "EmailSent"          | count;
let delivered = customEvents | where name == "HrAnswerDelivered"  | count;
print questionsToHr = toscalar(sent), answersDelivered = toscalar(delivered)
```

> A persistent gap between the two means representatives are not answering cards, or the
> timeout branch (Section 8) is missing.

---

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `500` — *Server is not configured: HR_REPLY_FROM_ADDRESS is missing* | App setting absent | Section 5, then **restart** the app |
| `502` — `ErrorAccessDenied` | Scoping does not cover the shared mailbox | Section 4; allow 30 min–2 h for the permission cache |
| `502` — `ErrorSendAsDenied` | Identity cannot send as that mailbox | Confirm it is a real mailbox, not a distribution list |
| `403` — *Recipient address is not permitted* | `user_email` outside `HR_REPLY_ALLOWED_RECIPIENTS` | Add the domain, or correct the address |
| `400` — *Missing required parameter 'answer'* | Card response path wrong | Fix `?['data']?['answer']` per Step 7.3 |
| `400` — *'user_email' is not a valid email address* | Wrong `text_N` index | Re-check the mapping per Step 7.3 |
| `401` from the Function | Wrong or missing function key | Re-copy the key; check the `x-functions-key` header |
| `200` but no email | Accepted by Graph, dropped by Exchange | Check the shared mailbox Sent Items; look for an NDR there |
| Answer arrives, employee unaware | Agent still promises a chat reply | Section 9 |
| Representative's name visible | Not possible via this endpoint | Check the *card* is not echoing the submitter |

> **On `202` from Graph:** it means *accepted for delivery*, not *delivered*. Per Microsoft's
> [sendMail reference](https://learn.microsoft.com/graph/api/user-sendmail), delivery still
> depends on Exchange. A `200` from the Function with no email in the inbox is therefore an
> Exchange problem, not a Function problem — start in the shared mailbox's Sent Items.

---

## 13. Rollback

- ☐ Disable the flow (**Power Automate → My flows → ⋯ → Turn off**), or
- ☐ Delete the `HR_REPLY_FROM_ADDRESS` app setting — the endpoint then returns `500` and the
  flow's failure branch (Step 7.4) alerts HR while nothing is emailed.
- ☐ Revert the message text in Section 9.

The `send_hr_email` path is untouched by all of the above and keeps working.

---

## Reference — API contract

**`POST /api/send_hr_answer`** · auth: function key

| Field | Required | Notes |
|---|---|---|
| `answer` | ✅ | The representative's response. Rejected if blank |
| `user_email` | ✅ | The employee who asked. The **only** recipient |
| `question` | | Original question, quoted for context |
| `user_full_name` | | Used in the greeting; falls back to "Hi," |
| `conversation_id` | | Telemetry correlation |
| `agent_label` | | Subject line and telemetry |

Accepts query-string parameters or a JSON body (including double-encoded JSON, which some
Power Automate connectors send).

| Status | Meaning |
|---|---|
| `200` | Sent. `{"sent": true, "recipient": "..."}` |
| `400` | Missing `answer`/`user_email`, or malformed address |
| `403` | Recipient blocked by `HR_REPLY_ALLOWED_RECIPIENTS` |
| `500` | `HR_REPLY_FROM_ADDRESS` not configured, or unexpected error |
| `502` | Graph rejected the send; `detail` carries the Graph error |

**Safety properties**

- All caller-supplied text is HTML-escaped — an answer containing markup cannot inject it.
- Exactly one recipient; the endpoint cannot fan out mail.
- No responder identity field exists, so none can leak.

---

## Reference — settings summary

| Setting | Required | Purpose |
|---|---|---|
| `HR_REPLY_FROM_ADDRESS` | ✅ | Shared mailbox the answer is sent from |
| `HR_REPLY_ALLOWED_RECIPIENTS` | Optional | Addresses/domains that may receive answers; unset = unrestricted |
| `HR_ALLOWED_RECIPIENTS` | *(existing)* | Used by `send_hr_email`; unrelated to this route |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | *(existing)* | Required for the telemetry in Section 11 |

---

## Related documents

- [CONNECT_REP_OPTION_D_ANONYMOUS_RELAY.md](./CONNECT_REP_OPTION_D_ANONYMOUS_RELAY.md) — the
  relay build and the `403` diagnostic this works around
- [EMAIL_HR_DEPLOYMENT_CHECKLIST.md](./EMAIL_HR_DEPLOYMENT_CHECKLIST.md) — the outbound leg;
  §4 covers the mailbox scoping extended here
- [COPILOT_STUDIO_SETUP_GUIDE.md](./COPILOT_STUDIO_SETUP_GUIDE.md) — click-by-click flow and
  topic authoring
- [ANALYTICS_KQL_QUERIES.md](./ANALYTICS_KQL_QUERIES.md) — the wider event schema
