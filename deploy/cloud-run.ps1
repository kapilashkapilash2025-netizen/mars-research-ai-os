param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [string]$Region = "asia-south1",
    [string]$Service = "areograph-mission-api"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "Google Cloud CLI is required. Install it and authenticate before deployment."
}

$activeAccount = gcloud auth list --filter=status:ACTIVE --format="value(account)"
if (-not $activeAccount) {
    throw "No active Google Cloud account. Run 'gcloud auth login' first."
}

gcloud config set project $ProjectId
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud run deploy $Service `
    --source . `
    --region $Region `
    --allow-unauthenticated `
    --set-env-vars "AREOGRAPH_ALLOWED_ORIGIN=https://mars-knowledge-console.kapilashmacbook.chatgpt.site" `
    --min-instances 0 `
    --max-instances 3 `
    --memory 512Mi `
    --cpu 1 `
    --concurrency 20 `
    --timeout 60 `
    --quiet

gcloud run services describe $Service --region $Region --format="value(status.url)"
