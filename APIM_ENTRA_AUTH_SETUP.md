# Routing Copilot Studio → Azure Function calls through API Management (Entra ID auth)

How to put **Azure API Management (APIM)** in front of your Azure Function, authenticate with
**Microsoft Entra ID** instead of function keys, and point your Copilot Studio flows at it.

**Why do this**
- Your tenant already governs outbound calls through `apim-tec-dev001.azure-api.net` — the
  Power Automate **HTTP with Microsoft Entra ID** connector is pre-configured with that
  `BaseResourceUri` and **rejects any URL outside it** (this is the `400` you hit earlier).
- Removes **function keys from URLs** (no secrets in flow definitions or logs).
- Central place for throttling, logging, IP restrictions, and versioning.

**Time required:** 60–90 minutes (plus admin time for the app registration).

---

## Table of contents
- [Target architecture](#target-architecture)
- [Before you begin](#before-you-begin)
- [Part 1 — Import the Function App into APIM](#part-1--import-the-function-app-into-apim)
- [Part 2 — Register the API in Entra ID](#part-2--register-the-api-in-entra-id)
- [Part 3 — Enforce Entra ID auth in APIM](#part-3--enforce-entra-id-auth-in-apim)
- [Part 4 — Decide how APIM authenticates to the Function](#part-4--decide-how-apim-authenticates-to-the-function)
- [Part 5 — Configure the Power Automate connection](#part-5--configure-the-power-automate-connection)
- [Part 6 — Update your flows](#part-6--update-your-flows)
- [Part 7 — Test end to end](#part-7--test-end-to-end)
- [Part 8 — Troubleshooting](#part-8--troubleshooting)
- [Reference — endpoint mapping](#reference--endpoint-mapping)

---

## Target architecture

```
Copilot Studio topic
	  |
	  v
Power Automate flow
  "HTTP with Microsoft Entra ID" connector
	  |  (bearer token, audience = APIM app ID URI)
	  v
Azure API Management   apim-tec-dev001.azure-api.net
  - validate-jwt  (verifies the Entra token)
  - injects the function key OR uses managed identity
	  |
	  v
Azure Function   func-hrbenefit-dev003
  agent_httptrigger | send_hr_email | submit_feedback
```

**Two separate authentication hops** — keep them distinct in your head:

| Hop | From → To | Mechanism |
|---|---|---|
| 1 | Power Automate → APIM | **Entra ID bearer token** (what this guide adds) |
| 2 | APIM → Function | Function key **or** APIM managed identity |

---

## Before you begin

Collect these values:

| Item | Example | Where |
|---|---|---|
| APIM instance name | `apim-tec-dev001` | Azure Portal → API Management |
| APIM gateway URL | `https://apim-tec-dev001.azure-api.net` | APIM → Overview |
| Function App name | `func-hrbenefit-dev003` | Azure Portal → Function App |
| Resource group | `TEC-AGENTIC-AI-RG` | |
| Tenant ID | | Entra ID → Overview |

**Permissions required**
- **Contributor** on the APIM instance and the Function App.
- Someone who can **create an app registration** in Entra ID (Application Administrator or
  equivalent). This is often a separate person — plan for it.

---

## Part 1 — Import the Function App into APIM

1. Azure Portal → open your **API Management** instance.
2. Left menu → **APIs** → **+ Add API**.
3. Choose the **Function App** tile.
4. Click **Browse** → select `func-hrbenefit-dev003`.
5. Select the functions to expose:
   - `agent_httptrigger`
   - `send_hr_email`
   - `submit_feedback`
6. Set:
   - **Display name:** `HR Benefits Functions`
   - **Name:** `hr-benefits`
   - **API URL suffix:** `hrbenefits`
7. Click **Create**.

✅ **Checkpoint:** your operations are reachable at
`https://apim-tec-dev001.azure-api.net/hrbenefits/<function-route>`

> **What APIM did for you:** it read the Function App's host key, stored it as a **named
> value** (Settings → Named values), and added a policy that injects it as the
> `x-functions-key` header on the way to the Function. Hop 2 is already handled.

### 1a — Subscription key requirement
By default APIM requires a subscription key (`Ocp-Apim-Subscription-Key`), which the Entra ID
connector does **not** send.

1. **APIs** → your API → **Settings**.
2. Find **Subscription required**.
3. **Uncheck it** (Entra ID becomes the sole auth mechanism — configured in Part 3).
4. **Save**.

> Prefer to keep subscription keys? Then you must add the header in each flow, and manage the
> key as a secret — which reintroduces what we are trying to remove.

---

## Part 2 — Register the API in Entra ID

This creates the identity that APIM will validate tokens against.

1. Azure Portal → **Microsoft Entra ID** → **App registrations** → **+ New registration**.
2. **Name:** `APIM-HR-Benefits-API`
3. **Supported account types:** *Accounts in this organizational directory only*.
4. Leave Redirect URI empty → **Register**.
5. On the Overview page, copy:
   - **Application (client) ID** → call this `<API_CLIENT_ID>`
   - **Directory (tenant) ID** → call this `<TENANT_ID>`
6. Left menu → **Expose an API** → next to *Application ID URI* click **Add**.
   - Accept the default `api://<API_CLIENT_ID>`, or set something readable like
	 `api://hr-benefits`.
   - **Save.** Record this as `<APP_ID_URI>` — the connector needs it as the **resource**.
7. Still on **Expose an API** → **+ Add a scope**:
   - **Scope name:** `Functions.Invoke`
   - **Who can consent:** *Admins and users* (or admins only per policy)
   - Fill the display names/descriptions → **Add scope**.

✅ **Checkpoint:** you have `<API_CLIENT_ID>`, `<TENANT_ID>`, and `<APP_ID_URI>`.

> **Note:** the Power Automate connector authenticates as the **signed-in user** or a stored
> connection identity. You do **not** need a separate client app registration unless your
> tenant requires explicit pre-authorization of client apps — see Part 8 if you hit consent
> errors.

---

## Part 3 — Enforce Entra ID auth in APIM

Add a `validate-jwt` policy so APIM rejects unauthenticated calls.

1. APIM → **APIs** → **HR Benefits Functions**.
2. Select **All operations**.
3. In the **Inbound processing** panel click **</>** (policy code editor).
4. Insert `validate-jwt` as the **first** element inside `<inbound>`:

```xml
<policies>
	<inbound>
		<base />
		<validate-jwt header-name="Authorization"
					  failed-validation-httpcode="401"
					  failed-validation-error-message="Unauthorized. Access token is missing or invalid.">
			<openid-config url="https://login.microsoftonline.com/<TENANT_ID>/v2.0/.well-known/openid-configuration" />
			<audiences>
				<audience><APP_ID_URI></audience>
				<audience><API_CLIENT_ID></audience>
			</audiences>
			<issuers>
				<issuer>https://sts.windows.net/<TENANT_ID>/</issuer>
				<issuer>https://login.microsoftonline.com/<TENANT_ID>/v2.0</issuer>
			</issuers>
		</validate-jwt>
		<!-- The function-key policy added during import stays below this. -->
	</inbound>
	<backend>
		<base />
	</backend>
	<outbound>
		<base />
	</outbound>
	<on-error>
		<base />
	</on-error>
</policies>
```

5. Replace `<TENANT_ID>`, `<APP_ID_URI>`, `<API_CLIENT_ID>` with your values.
6. **Save**.

> **Both audiences and both issuers are listed deliberately.** Entra issues v1.0 or v2.0
> tokens depending on the client, and the audience may appear as either the App ID URI or the
> raw client ID. Accepting both avoids a class of frustrating 401s.

> **Government clouds:** replace `login.microsoftonline.com` with your cloud's authority
> (e.g. `login.microsoftonline.us`) and `sts.windows.net` accordingly.

✅ **Checkpoint:** calling the APIM URL **without** a token now returns **401**.

---

## Part 4 — Decide how APIM authenticates to the Function

Hop 2 — pick one.

### Option A — Function key (default from import, simplest)
Nothing to do. APIM injects the key stored as a named value. The key never appears in
Copilot Studio or Power Automate.

Verify: APIM → **Named values** → look for an entry like `func-hrbenefit-dev003-key`.

### Option B — APIM managed identity (no keys at all)
More secure; requires configuring the Function App for Entra auth.

1. APIM → **Managed identities** → enable **System assigned** → **Save**.
2. Function App → **Authentication** → **Add identity provider** → **Microsoft**.
   - Restrict access: **Require authentication**
   - Unauthenticated requests: **HTTP 401**
3. In the API policy, replace the key header with:
```xml
<authentication-managed-identity resource="<FUNCTION_APP_CLIENT_ID>" />
```
4. Remove the `set-header` that injects `x-functions-key`.

⚠️ Option B changes how the Function authorizes **all** callers — test carefully, and note
your direct `curl` tests will stop working without a token.

**Recommendation:** start with **Option A**, move to B once the end-to-end path works.

---

## Part 5 — Configure the Power Automate connection

1. Open **Power Automate** (your cloud's portal) → correct environment.
2. Left menu → **Connections** → **+ New connection**.
3. Search for **HTTP with Microsoft Entra ID** → select it.
4. Fill in:
   - **Base Resource URL:** `https://apim-tec-dev001.azure-api.net`
   - **Azure AD Resource URI (Application ID URI):** `<APP_ID_URI>`
	 (e.g. `api://hr-benefits`)
5. **Create** → sign in and consent when prompted.

✅ **Checkpoint:** the connection appears in **Connections** with a healthy status.

> This is the same connector that failed earlier — it failed only because the URL was outside
> the allowed base. Now that calls go to APIM, that constraint is satisfied.

---

## Part 6 — Update your flows

Repeat for each flow: **agent call**, **Send HR Email**, **Submit Feedback**.

1. Open the flow → **Edit**.
2. **Delete** the existing plain **HTTP** action.
3. **+ Add an action** → search **HTTP with Microsoft Entra ID** →
   choose **Invoke an HTTP request**.
4. Select the connection created in Part 5.
5. Configure:
   - **Method:** `POST`
   - **Url of the request:**
	 `https://apim-tec-dev001.azure-api.net/hrbenefits/agent_httptrigger`
	 *(no `?code=` — the function key is gone)*
   - **Headers:** `Content-Type` = `application/json`
   - **Body:** keep exactly the same JSON you already had.
6. Re-point any downstream **Parse JSON** / **Respond to the agent** steps at the new action's
   **Body** output.
7. **Save**.

> **Keep the body identical.** Only the transport changes — the Function contract
> (`question`, `user_email`, `to_address`, `rating`, …) is unchanged.

⚠️ **Refresh Copilot Studio afterwards.** Replacing an action changes the flow's shape, so the
topic may need the node deleted and re-added to pick up the outputs. Note your input mappings
before doing so.

---

## Part 7 — Test end to end

### 7a — APIM test console
1. APIM → **APIs** → your API → select an operation → **Test** tab.
2. Provide a sample body and **Send**.
3. Expect **200**. A **401** here means the test console did not attach a valid token — normal
   for `validate-jwt`; rely on the flow test instead.

### 7b — Confirm auth is actually enforced
```powershell
# No token -> must be 401
curl -X POST "https://apim-tec-dev001.azure-api.net/hrbenefits/submit_feedback" `
  -H "Content-Type: application/json" `
  -d '{"rating":"up"}'
```
Getting **200** here means `validate-jwt` is not applied — recheck Part 3.

### 7c — Flow test
Power Automate → flow → **Test** → **Manually**, supply inputs, run.
- Open the run → the **Invoke an HTTP request** step → expect **200**.
- Check the request actually carried an `Authorization` header.

### 7d — Function logs
Azure Portal → Function App → **Log stream** — you should see the invocation arrive.

### 7e — Teams
Ask a question end to end and confirm the agent responds.

### 7f — APIM analytics
APIM → **Analytics** (or **Metrics**) — confirm requests are flowing and note the success rate.

---

## Part 8 — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `401 Unauthorized` from APIM | Audience/issuer mismatch | Ensure both the App ID URI **and** client ID are listed as audiences (Part 3) |
| `401` with *"Access token is missing"* | Connector not sending a token | Recheck the connection's **Azure AD Resource URI** (Part 5) |
| `BaseResourceUri must be a base of the full url` | Calling a non-APIM URL | The URL must start with the connector's Base Resource URL |
| `403` from APIM | Subscription key required | Uncheck **Subscription required** (Part 1a) |
| `401` from the **Function** (not APIM) | Key policy removed or wrong | Check APIM **Named values** and the inbound policy |
| `404` from APIM | Wrong suffix or operation path | Verify against the [endpoint mapping](#reference--endpoint-mapping) |
| Consent error on connection creation | Admin consent required | Ask an admin to grant consent for the API scope |
| Flow outputs disappeared in the topic | Action replaced, schema stale | Delete and re-add the tool node in Copilot Studio |
| Works in flow test, fails from Teams | Agent not published | **Publish** the agent |

### Useful diagnostics
- **APIM inspector:** APIs → operation → **Test** → run → **Trace** shows exactly which policy
  rejected the call.
- **Decode a token** at `jwt.ms` and compare `aud` and `iss` against your policy.
- **Function-side:** Application Insights →
```kql
requests
| where timestamp > ago(30m)
| project timestamp, name, resultCode, duration
| order by timestamp desc
```

---

## Reference — endpoint mapping

| Function route | Old (direct) | New (via APIM) |
|---|---|---|
| `agent_httptrigger` | `https://func-hrbenefit-dev003.azurewebsites.net/api/agent_httptrigger?code=...` | `https://apim-tec-dev001.azure-api.net/hrbenefits/agent_httptrigger` |
| `send_hr_email` | `https://func-hrbenefit-dev003.azurewebsites.net/api/send_hr_email?code=...` | `https://apim-tec-dev001.azure-api.net/hrbenefits/send_hr_email` |
| `submit_feedback` | `https://func-hrbenefit-dev003.azurewebsites.net/api/submit_feedback?code=...` | `https://apim-tec-dev001.azure-api.net/hrbenefits/submit_feedback` |

### After cutover — clean up
- ☐ Confirm every flow uses the APIM URL (no `?code=` remains anywhere).
- ☐ **Rotate the Function keys** — the old ones were exposed in flow definitions, logs, and
  the `.txt` files shared during troubleshooting.
- ☐ Consider restricting the Function App to accept traffic **only from APIM**
  (Networking → access restrictions, allowing the APIM outbound IP or VNet).
- ☐ Add APIM **rate-limit** policies if you want throttling.

### Values to record

| Value | Yours |
|---|---|
| APIM gateway URL | |
| API URL suffix | |
| `<API_CLIENT_ID>` | |
| `<TENANT_ID>` | |
| `<APP_ID_URI>` | |
| Connection name in Power Automate | |
