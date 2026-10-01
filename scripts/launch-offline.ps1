$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Creating the local Python environment..."
    & py -3 -m venv (Join-Path $ProjectRoot ".venv")
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python 3 was not found. Install Python 3.11+ and run this launcher again."
}

Write-Host "Applying local database migrations..."
& $Python manage.py migrate --noinput
Write-Host "Starting Offline CodeGPT at http://127.0.0.1:8000 ..."
& $Python manage.py runserver 127.0.0.1:8000
