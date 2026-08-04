# =============================================================================
# deploy.ps1 - Build and deploy the Azure Function package
#
# Portable: clone the repo on any machine, then run this script.
# Designed for Flex Consumption (remote build happens on the platform), but
# works for other Linux Python plans too.
#
# Prerequisites on the target machine:
#   - Azure CLI installed            https://aka.ms/installazurecli
#   - Signed in                      az login
#   - Correct subscription selected  az account set --subscription "<name-or-id>"
#   (Python is NOT required - dependencies are built in Azure from requirements.txt)
#
# Examples:
#   # Build the zip only (no deploy)
#   ./deploy.ps1 -ZipOnly
#
#   # Build and deploy
#   ./deploy.ps1 -FunctionAppName "func-hrbenefit-dev003" -ResourceGroup "rg-hrbenefit-dev"
#
#   # Build, deploy, then list the registered functions
#   ./deploy.ps1 -FunctionAppName "func-hrbenefit-dev003" -ResourceGroup "rg-hrbenefit-dev" -Verify
# =============================================================================

param(
	[string] $FunctionAppName,
	[string] $ResourceGroup,
	[string] $ZipPath = "deploy.zip",
	[switch] $ZipOnly,
	[switch] $Verify
)

$ErrorActionPreference = "Stop"

function Write-Section($text) {
	Write-Host ""
	Write-Host "==== $text ====" -ForegroundColor Cyan
}

# Files the Functions host actually needs at the archive ROOT.
# Add any new source folders/files here (e.g. "shared").
$Include = @(
	"function_app.py",
	"host.json",
	"requirements.txt"
)

# -----------------------------------------------------------------------------
# 1. Sanity checks
# -----------------------------------------------------------------------------
Write-Section "Checking project files"

$projectRoot = $PSScriptRoot
if (-not $projectRoot) { $projectRoot = (Get-Location).Path }
Set-Location $projectRoot
Write-Host "Project root: $projectRoot"

$missing = @()
foreach ($f in $Include) {
	if (-not (Test-Path (Join-Path $projectRoot $f))) { $missing += $f }
}
if ($missing.Count -gt 0) {
	throw "Missing required file(s): $($missing -join ', '). Run this script from the project root."
}
Write-Host "All required files present." -ForegroundColor Green

# Warn about artifacts that must never be deployed.
foreach ($bad in @(".venv", ".python_packages", "__pycache__")) {
	if (Test-Path (Join-Path $projectRoot $bad)) {
		Write-Host "NOTE: '$bad' exists locally and will be EXCLUDED from the package." -ForegroundColor Yellow
	}
}

# -----------------------------------------------------------------------------
# 2. Build the zip (staged so files land at the archive ROOT)
# -----------------------------------------------------------------------------
Write-Section "Building $ZipPath"

$stage = Join-Path ([System.IO.Path]::GetTempPath()) ("funcdeploy_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stage | Out-Null

try {
	foreach ($f in $Include) {
		Copy-Item (Join-Path $projectRoot $f) -Destination $stage -Recurse -Force
	}

	$zipFull = Join-Path $projectRoot $ZipPath
	Remove-Item $zipFull -Force -ErrorAction SilentlyContinue
	Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipFull -Force

	Add-Type -AssemblyName System.IO.Compression.FileSystem
	$archive = [System.IO.Compression.ZipFile]::OpenRead($zipFull)
	try {
		Write-Host "Package contents (must have NO folder prefix):"
		$archive.Entries | ForEach-Object { Write-Host ("  {0,-24} {1,8} bytes" -f $_.FullName, $_.Length) }
		$nested = $archive.Entries | Where-Object { $_.FullName -match '/' -and $_.FullName -notmatch '^[^/]+/$' }
		if ($nested -and -not ($Include | Where-Object { (Get-Item (Join-Path $projectRoot $_)).PSIsContainer })) {
			Write-Host "WARNING: nested paths detected; verify the host can find function_app.py." -ForegroundColor Yellow
		}
	}
	finally { $archive.Dispose() }

	$sizeKb = [math]::Round((Get-Item $zipFull).Length / 1KB, 1)
	Write-Host "Created $ZipPath ($sizeKb KB)" -ForegroundColor Green
}
finally {
	Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}

if ($ZipOnly) {
	Write-Section "Done (zip only)"
	Write-Host "Deploy it later with:" -ForegroundColor Cyan
	Write-Host "  az functionapp deployment source config-zip -g <RG> -n <APP> --src $ZipPath"
	return
}

# -----------------------------------------------------------------------------
# 3. Deploy
# -----------------------------------------------------------------------------
if (-not $FunctionAppName -or -not $ResourceGroup) {
	throw "Provide -FunctionAppName and -ResourceGroup to deploy, or use -ZipOnly to just build the package."
}

Write-Section "Checking Azure CLI"

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
	throw "Azure CLI not found. Install it from https://aka.ms/installazurecli then run 'az login'."
}

$account = az account show 2>$null
if (-not $account) {
	throw "Not signed in to Azure. Run 'az login' (and 'az account set --subscription <id>') then retry."
}
$sub = ($account | ConvertFrom-Json)
Write-Host "Subscription: $($sub.name) [$($sub.id)]"

Write-Section "Inspecting the Function App"

$appJson = az functionapp show -n $FunctionAppName -g $ResourceGroup -o json 2>$null
if (-not $appJson) {
	throw "Function App '$FunctionAppName' not found in resource group '$ResourceGroup'."
}
$app = $appJson | ConvertFrom-Json
Write-Host "Name    : $($app.name)"
Write-Host "State   : $($app.state)"
if ($app.functionAppConfig -and $app.functionAppConfig.runtime) {
	Write-Host "Runtime : $($app.functionAppConfig.runtime.name) $($app.functionAppConfig.runtime.version)"
}

Write-Section "Deploying $ZipPath"

az functionapp deployment source config-zip `
	-g $ResourceGroup `
	-n $FunctionAppName `
	--src (Join-Path $projectRoot $ZipPath)

if ($LASTEXITCODE -ne 0) {
	throw "Deployment failed. See the Azure CLI output above."
}
Write-Host "Deployment submitted." -ForegroundColor Green

# -----------------------------------------------------------------------------
# 4. Verify
# -----------------------------------------------------------------------------
if ($Verify) {
	Write-Section "Waiting for the platform to build dependencies and index functions"
	Write-Host "This can take 1-3 minutes on Flex Consumption..."
	Start-Sleep -Seconds 60

	Write-Section "Registered functions"
	az functionapp function list -g $ResourceGroup -n $FunctionAppName -o table

	Write-Host ""
	Write-Host "If the list is empty, the package deployed but function_app.py failed to import." -ForegroundColor Yellow
	Write-Host "Check Application Insights with:" -ForegroundColor Yellow
	Write-Host '  traces | where timestamp > ago(30m) | where message has_any ("ModuleNotFoundError","ImportError","Worker failed","Failed to index") | order by timestamp desc'
}

Write-Section "Done"
