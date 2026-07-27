$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path "$ProjectRoot\backend\.venv\Scripts\python.exe")) {
    throw "backend\.venv is missing. Install the dependencies described in README.md."
}

if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    throw "pnpm is unavailable. Install Node.js and run: corepack enable"
}

if (-not (Test-Path "$ProjectRoot\frontend\node_modules")) {
    throw "frontend\node_modules is missing. Run pnpm install in frontend."
}

Start-Process powershell `
    -WorkingDirectory "$ProjectRoot\backend" `
    -ArgumentList "-NoExit", "-Command", ".\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"
Start-Process powershell `
    -WorkingDirectory "$ProjectRoot\frontend" `
    -ArgumentList "-NoExit", "-Command", "pnpm dev"

Write-Host "Backend: http://localhost:8000/docs"
Write-Host "Frontend: http://localhost:3000"
