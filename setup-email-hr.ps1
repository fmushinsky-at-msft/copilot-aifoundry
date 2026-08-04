# =============================================================================
# setup-email-hr.ps1
# Companion automation for EMAIL_HR_DEPLOYMENT_CHECKLIST.md
#
# Runs the scriptable portions of the "Email HR when no answer" setup:
#   Section 1 - Function App settings (az)
#   Section 3 - Microsoft Graph Mail.Send grant to the managed identity (Graph PS)
#   Section 4 - Exchange Online Application Access Policy (Exchange PS)
#
# NOT automated (do manually per the checklist):
#   Section 6 - Foundry NO_ANSWER instruction
#   Section 7/8/9 - Copilot Studio / Power Automate topic logic
#
# Requirements:
#   - Azure CLI (az) logged in:            az login
#   - Microsoft.Graph module + admin       Connect-MgGraph
#   - ExchangeOnlineManagement module      Connect-ExchangeOnline
#   - Admin able to grant app roles and manage Exchange
#
# Usage (fill in the parameters):
#   ./setup-email-hr.ps1 `
#       -FunctionAppName "myfunc" `
#       -ResourceGroup "myrg" `
#       -AllowedRecipients "OpenEnrollment@panynj.gov" `
#       -AssistantUsersGroup "benefits-assistant-users@panynj.gov" `
#       -TestMailbox "steven.choy@panynj.gov"
# =============================================================================

param(
	[Parameter(Mandatory = $true)] [string] $FunctionAppName,
	[Parameter(Mandatory = $true)] [string] $ResourceGroup,
	[Parameter(Mandatory = $true)] [string] $AllowedRecipients,
	[Parameter(Mandatory = $true)] [string] $AssistantUsersGroup,
	[string] $TestMailbox = "",
	[string] $AppInsightsConnectionString = "",
	[switch] $SkipFunctionSettings,
	[switch] $SkipGraphGrant,
	[switch] $SkipExchangePolicy
)

$ErrorActionPreference = "Stop"
$GraphAppId = "00000003-0000-0000-c000-000000000000"  # Microsoft Graph well-known appId

function Write-Section($text) {
	Write-Host ""
	Write-Host "==== $text ====" -ForegroundColor Cyan
}

# -----------------------------------------------------------------------------
# Section 1 - Function App application settings
# -----------------------------------------------------------------------------
if (-not $SkipFunctionSettings) {
	Write-Section "Section 1: Function App settings"

	$settings = @(
		"HR_ALLOWED_RECIPIENTS=$AllowedRecipients"
	)
	if ($AppInsightsConnectionString -ne "") {
		$settings += "APPLICATIONINSIGHTS_CONNECTION_STRING=$AppInsightsConnectionString"
	}

	Write-Host "Applying settings to $FunctionAppName ..."
	az functionapp config appsettings set `
		--name $FunctionAppName `
		--resource-group $ResourceGroup `
		--settings $settings | Out-Null

	Write-Host "Restarting the Function App ..."
	az functionapp restart --name $FunctionAppName --resource-group $ResourceGroup | Out-Null
	Write-Host "Function App settings applied and restarted." -ForegroundColor Green
}

# -----------------------------------------------------------------------------
# Resolve the Function App's system-assigned managed identity
# -----------------------------------------------------------------------------
Write-Section "Resolving managed identity"
$miObjectId = az functionapp identity show `
	--name $FunctionAppName `
	--resource-group $ResourceGroup `
	--query principalId -o tsv

if ([string]::IsNullOrWhiteSpace($miObjectId)) {
	throw "System-assigned managed identity is not enabled on $FunctionAppName. Enable it (Identity -> System assigned -> On) and re-run."
}
Write-Host "Managed identity object (principal) id: $miObjectId" -ForegroundColor Green

# The identity's application (client) id is needed for the Exchange policy.
$miAppId = az ad sp show --id $miObjectId --query appId -o tsv 2>$null
if ([string]::IsNullOrWhiteSpace($miAppId)) {
	Write-Host "Warning: could not resolve the managed identity Application (client) ID automatically." -ForegroundColor Yellow
	Write-Host "Find it under Entra ID -> Enterprise applications -> $FunctionAppName -> Application ID." -ForegroundColor Yellow
}
else {
	Write-Host "Managed identity application (client) id: $miAppId" -ForegroundColor Green
}

# -----------------------------------------------------------------------------
# Section 3 - Grant Microsoft Graph Mail.Send (application) to the identity
# -----------------------------------------------------------------------------
if (-not $SkipGraphGrant) {
	Write-Section "Section 3: Grant Graph Mail.Send to the managed identity"

	if (-not (Get-Module -ListAvailable -Name Microsoft.Graph)) {
		throw "Microsoft.Graph module not installed. Run: Install-Module Microsoft.Graph -Scope CurrentUser"
	}
	Import-Module Microsoft.Graph.Applications -ErrorAction SilentlyContinue

	# Requires an interactive admin connection with app-role grant rights.
	if (-not (Get-MgContext)) {
		Write-Host "Connecting to Microsoft Graph (admin consent required) ..."
		Connect-MgGraph -Scopes "AppRoleAssignment.ReadWrite.All", "Application.Read.All" | Out-Null
	}

	$graphSp = Get-MgServicePrincipal -Filter "appId eq '$GraphAppId'"
	$appRole = $graphSp.AppRoles | Where-Object {
		$_.Value -eq "Mail.Send" -and $_.AllowedMemberTypes -contains "Application"
	}
	if (-not $appRole) { throw "Could not find the Mail.Send application app role on Microsoft Graph." }

	# Idempotency: skip if already assigned.
	$existing = Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $miObjectId -All |
		Where-Object { $_.AppRoleId -eq $appRole.Id -and $_.ResourceId -eq $graphSp.Id }

	if ($existing) {
		Write-Host "Mail.Send is already granted to the managed identity. Skipping." -ForegroundColor Green
	}
	else {
		New-MgServicePrincipalAppRoleAssignment `
			-ServicePrincipalId $miObjectId `
			-PrincipalId $miObjectId `
			-ResourceId $graphSp.Id `
			-AppRoleId $appRole.Id | Out-Null
		Write-Host "Granted Mail.Send (application) to the managed identity." -ForegroundColor Green
		Write-Host "Allow a few minutes for propagation." -ForegroundColor Yellow
	}
}

# -----------------------------------------------------------------------------
# Section 4 - Exchange Online Application Access Policy (scope to one mailbox)
# -----------------------------------------------------------------------------
if (-not $SkipExchangePolicy) {
	Write-Section "Section 4: Exchange Application Access Policy"

	if ([string]::IsNullOrWhiteSpace($miAppId)) {
		Write-Host "Skipping Exchange policy: managed identity Application ID unknown. Set it manually and re-run with -SkipFunctionSettings -SkipGraphGrant." -ForegroundColor Yellow
	}
	else {
		if (-not (Get-Module -ListAvailable -Name ExchangeOnlineManagement)) {
			throw "ExchangeOnlineManagement module not installed. Run: Install-Module ExchangeOnlineManagement -Scope CurrentUser"
		}
		Import-Module ExchangeOnlineManagement -ErrorAction SilentlyContinue

		if (-not (Get-ConnectionInformation)) {
			Write-Host "Connecting to Exchange Online (admin) ..."
			Connect-ExchangeOnline -ShowBanner:$false | Out-Null
		}

		# Idempotency: check for an existing policy for this app.
		$existingPolicy = Get-ApplicationAccessPolicy -ErrorAction SilentlyContinue |
			Where-Object { $_.AppId -eq $miAppId -and $_.ScopeIdentity -eq $AssistantUsersGroup }

		if ($existingPolicy) {
			Write-Host "An Application Access Policy for this app + group already exists. Skipping." -ForegroundColor Green
		}
		else {
			New-ApplicationAccessPolicy `
				-AppId $miAppId `
				-PolicyScopeGroupId $AssistantUsersGroup `
				-AccessRight RestrictAccess `
				-Description "Benefits assistant may send only as enrolled assistant users" | Out-Null
			Write-Host "Created Application Access Policy restricting the app to $AssistantUsersGroup." -ForegroundColor Green
			Write-Host "Allow up to ~30 minutes for the policy to take effect." -ForegroundColor Yellow
		}

		if ($TestMailbox -ne "") {
			Write-Host "Testing access policy against $TestMailbox ..."
			try {
				$test = Test-ApplicationAccessPolicy -Identity $TestMailbox -AppId $miAppId
				Write-Host "Test-ApplicationAccessPolicy result for $TestMailbox : $($test.AccessCheckResult)" -ForegroundColor Green
			}
			catch {
				Write-Host "Could not run Test-ApplicationAccessPolicy yet (may need propagation): $_" -ForegroundColor Yellow
			}
		}
		else {
			Write-Host "Skipping policy test (pass -TestMailbox <user@domain> to verify)." -ForegroundColor Yellow
		}
	}
}

Write-Section "Done"
Write-Host "Scriptable steps complete. Remaining MANUAL steps (see EMAIL_HR_DEPLOYMENT_CHECKLIST.md):" -ForegroundColor Cyan
Write-Host "  - Section 6: Add the NO_ANSWER instruction in Azure AI Foundry."
Write-Host "  - Section 7-9: Copilot Studio topic + Power Automate body escaping + action wiring."
Write-Host "  - Section 10: End-to-end testing."
