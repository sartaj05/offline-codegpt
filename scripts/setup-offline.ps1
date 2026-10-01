param(
    [string]$Model = "qwen2.5-coder:1.5b",
    [string]$VisionModel = "llava:latest",
    [switch]$SkipOllama,
    [switch]$SkipVision
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Require-Command([string]$name, [string]$hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "$name was not found. $hint"
    }
}

Require-Command "py" "Install Python 3.10+ and enable the Python launcher."

if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "Creating local Python environment..." -ForegroundColor Cyan
    py -3 -m venv venv
}

$python = Join-Path $projectRoot "venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Review it before production use." -ForegroundColor Yellow
}

& $python manage.py migrate
& $python manage.py check

if (-not $SkipOllama) {
    Require-Command "ollama" "Install Ollama from https://ollama.com/download."
    $ollamaStatus = & ollama list 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Ollama is installed but not responding. Start Ollama and rerun setup."
    }
    Write-Host "Pulling chat model $Model..." -ForegroundColor Cyan
    & ollama pull $Model
    if (-not $SkipVision) {
        Write-Host "Pulling vision model $VisionModel..." -ForegroundColor Cyan
        & ollama pull $VisionModel
    }
}

Write-Host "Offline setup complete." -ForegroundColor Green
Write-Host "Start the app with: .\venv\Scripts\python.exe manage.py runserver"
