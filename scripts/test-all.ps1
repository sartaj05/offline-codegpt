param(
    [switch]$WithBrowser,
    [switch]$WithInstaller
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Invoke-Step([string]$label, [scriptblock]$command) {
    Write-Host "`n== $label ==" -ForegroundColor Cyan
    & $command
    if ($LASTEXITCODE -ne 0) { throw "$label failed with exit code $LASTEXITCODE" }
}

$python = if (Test-Path ".\venv\Scripts\python.exe") { ".\venv\Scripts\python.exe" } else { "python" }
Invoke-Step "Django system check" { & $python manage.py check }
Invoke-Step "Migration check" { & $python manage.py makemigrations --check --dry-run }
Invoke-Step "Django tests" { & $python manage.py test chat --keepdb }

if (Get-Command node -ErrorAction SilentlyContinue) {
    Invoke-Step "Chat JavaScript syntax" { node --check static/chat/app.js }
    Invoke-Step "VS Code extension syntax" { node --check vscode-extension/extension.js }
    Invoke-Step "VS Code extension contract" { node tests/extension-contract.js }
    Invoke-Step "VS Code package manifest" { node -e "JSON.parse(require('fs').readFileSync('vscode-extension/package.json','utf8')); console.log('package.json valid')" }
} else {
    Write-Warning "Node.js is not installed; JavaScript checks were skipped."
}

if ($WithBrowser) {
    if (-not (Get-Command npx -ErrorAction SilentlyContinue)) { throw "npx is required for -WithBrowser." }
    if (-not (Get-Command playwright -ErrorAction SilentlyContinue)) { throw "Playwright is not installed locally; install it before using -WithBrowser." }
    Invoke-Step "Playwright responsive tests" { npx playwright test tests/responsive.spec.js }
}

if ($WithInstaller) {
    Invoke-Step "Installer definition" { & powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-installer.ps1" -CheckOnly }
}

Write-Host "`nAll requested local checks passed." -ForegroundColor Green
