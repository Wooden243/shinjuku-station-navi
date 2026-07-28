$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$artifactDirectory = Join-Path $projectRoot "artifacts"
$archivePath = Join-Path $artifactDirectory "shinjuku-open-nav-source-20260728.zip"
New-Item -ItemType Directory -Force -Path $artifactDirectory | Out-Null

Push-Location $projectRoot
try {
  & tar.exe -a -c -f $archivePath `
    --exclude="./.git" `
    --exclude="./artifacts" `
    --exclude="./backend/.venv" `
    --exclude="./backend/*.egg-info" `
    --exclude="./frontend/node_modules" `
    --exclude="./frontend/.next" `
    --exclude="./frontend/out" `
    --exclude="./frontend/coverage" `
    --exclude="./frontend/.env.local" `
    --exclude="./frontend/android/.gradle" `
    --exclude="./frontend/android/app/build" `
    --exclude="./.pytest_cache" `
    --exclude="./.mypy_cache" `
    --exclude="./.ruff_cache" `
    --exclude="./__pycache__" `
    --exclude="./**/__pycache__" `
    --exclude="./**/.pytest_cache" `
    --exclude="./**/.mypy_cache" `
    --exclude="./**/.ruff_cache" `
    --exclude="./*.sqlite3" `
    --exclude="./data/*.sqlite3" `
    --exclude="./data/raw/*.geojson" `
    --exclude="./shinjuku_navi_app" `
    --exclude="./shinjuku_navi_app_a" `
    .
  if ($LASTEXITCODE -ne 0) { throw "tar.exe failed with exit code $LASTEXITCODE" }
} finally {
  Pop-Location
}

$archiveHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
Write-Host "Created: $archivePath"
Write-Host "SHA-256: $archiveHash"
