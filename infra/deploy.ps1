[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ProjectId,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9_-]{20,}$')]
    [string]$SpreadsheetId,

    [string]$Region = 'asia-east1',
    [string]$SchedulerLocation = 'asia-east1',
    [string]$ServiceName = 'option-alerts',
    [string]$SchedulerJob = 'option-alert-refresh',
    [string]$Schedule = '*/5 * * * *'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Gcloud {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & gcloud @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud 執行失敗：gcloud $($Arguments -join ' ')"
    }
}

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw '找不到 gcloud。請先安裝 Google Cloud CLI 並執行 gcloud auth login。'
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeAccountId = 'option-alert-runtime'
$SchedulerAccountId = 'option-alert-scheduler'
$RuntimeEmail = "$RuntimeAccountId@$ProjectId.iam.gserviceaccount.com"
$SchedulerEmail = "$SchedulerAccountId@$ProjectId.iam.gserviceaccount.com"

Push-Location $ProjectRoot
try {
    Invoke-Gcloud config set project $ProjectId
    Invoke-Gcloud services enable `
        run.googleapis.com `
        cloudscheduler.googleapis.com `
        cloudbuild.googleapis.com `
        artifactregistry.googleapis.com `
        sheets.googleapis.com `
        iam.googleapis.com `
        --project $ProjectId

    & gcloud iam service-accounts describe $RuntimeEmail --project $ProjectId *> $null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Gcloud iam service-accounts create $RuntimeAccountId `
            --display-name 'Option alerts runtime' `
            --project $ProjectId
    }

    & gcloud iam service-accounts describe $SchedulerEmail --project $ProjectId *> $null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Gcloud iam service-accounts create $SchedulerAccountId `
            --display-name 'Option alerts scheduler' `
            --project $ProjectId
    }

    Invoke-Gcloud run deploy $ServiceName `
        --source . `
        --region $Region `
        --project $ProjectId `
        --service-account $RuntimeEmail `
        --set-env-vars "SPREADSHEET_ID=$SpreadsheetId,MAX_MONITOR_ROWS=1000" `
        --no-allow-unauthenticated `
        --min-instances 0 `
        --max-instances 1 `
        --concurrency 1 `
        --memory 1Gi `
        --timeout 120 `
        --quiet

    $ServiceUrl = (& gcloud run services describe $ServiceName `
        --region $Region `
        --project $ProjectId `
        --format 'value(status.url)').Trim()
    if ($LASTEXITCODE -ne 0 -or -not $ServiceUrl) {
        throw '無法取得 Cloud Run URL。'
    }

    Invoke-Gcloud run services add-iam-policy-binding $ServiceName `
        --region $Region `
        --project $ProjectId `
        --member "serviceAccount:$SchedulerEmail" `
        --role 'roles/run.invoker' `
        --quiet

    & gcloud scheduler jobs describe $SchedulerJob `
        --location $SchedulerLocation `
        --project $ProjectId *> $null
    $SchedulerExists = $LASTEXITCODE -eq 0
    $SchedulerVerb = if ($SchedulerExists) { 'update' } else { 'create' }

    Invoke-Gcloud scheduler jobs $SchedulerVerb http $SchedulerJob `
        --location $SchedulerLocation `
        --project $ProjectId `
        --schedule $Schedule `
        --time-zone 'Etc/UTC' `
        --uri "$ServiceUrl/refresh" `
        --http-method POST `
        --headers 'Content-Type=application/json' `
        --message-body '{"force":false}' `
        --oidc-service-account-email $SchedulerEmail `
        --oidc-token-audience $ServiceUrl `
        --attempt-deadline 180s `
        --max-retry-attempts 1 `
        --quiet

    Write-Host ''
    Write-Host '部署完成。' -ForegroundColor Green
    Write-Host "Cloud Run URL: $ServiceUrl"
    Write-Host "請把 Google Sheet 分享給以下帳號並授予編輯權：$RuntimeEmail" -ForegroundColor Yellow
    Write-Host "測試排程：gcloud scheduler jobs run $SchedulerJob --location $SchedulerLocation --project $ProjectId"
}
finally {
    Pop-Location
}
