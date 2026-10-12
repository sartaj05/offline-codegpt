param(
    [string]$Model = "qwen2.5-coder:1.5b",
    [string]$VisionModel = "llava:latest",
    [switch]$Offline,
    [switch]$SkipOllama,
    [switch]$SkipWorker,
    [switch]$Repair,
    [switch]$Uninstall,
    [switch]$RemoveData,
    [switch]$Confirmed
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Require-Command([string]$name, [string]$hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "$name was not found. $hint" }
}

if ($Uninstall) {
    if (-not $Confirmed) { throw "Uninstall requires -Confirmed. Project files are preserved; use -RemoveData only when explicitly requested." }
    if ($RemoveData) {
        $backup = Join-Path (Split-Path -Parent $projectRoot) ("SyntaxLocalAI-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
        New-Item -ItemType Directory -Path $backup -Force | Out-Null
        foreach ($item in @("db.sqlite3", ".env", "media", "local_models")) {
            $source = Join-Path $projectRoot $item
            if (Test-Path -LiteralPath $source) { Move-Item -LiteralPath $source -Destination $backup -Force }
        }
        Write-Host "Local data moved to $backup" -ForegroundColor Yellow
    }
    Write-Host "Uninstall preparation complete. The source checkout was not deleted." -ForegroundColor Green
    exit 0
}

Require-Command "py" "Install Python 3.10+ and enable the Python launcher."
if (-not (Test-Path ".\venv\Scripts\python.exe")) { py -3 -m venv venv }
$python = Join-Path $projectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "The local Python environment could not be created." }
if ($Offline) {
    if (-not (Test-Path ".\vendor\wheels")) { throw "Offline installation requires .\vendor\wheels with pinned dependency wheels." }
    & $python -m pip install --no-index --find-links ".\vendor\wheels" -r requirements.txt
} else {
    & $python -m pip install -r requirements.txt
}
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
& $python manage.py migrate --noinput
& $python manage.py check

function Test-LocalRuntime([string]$url) {
    try { $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2; return @{ reachable = $true; status = [int]$response.StatusCode } }
    catch { return @{ reachable = $false; status = 0; error = $_.Exception.Message.Substring(0, [Math]::Min(180, $_.Exception.Message.Length)) } }
}

$computer = Get-CimInstance Win32_ComputerSystem
$gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name })
$diagnostics = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    python = (& $python --version 2>&1 | Out-String).Trim()
    memory_gb = [Math]::Round($computer.TotalPhysicalMemory / 1GB, 2)
    gpu = $gpus
    runtimes = [ordered]@{
        ollama = Test-LocalRuntime "http://127.0.0.1:11434/api/tags"
        lmstudio = Test-LocalRuntime "http://127.0.0.1:1234/v1/models"
        llamacpp = Test-LocalRuntime "http://127.0.0.1:8080/health"
    }
    configured_model = $Model
    configured_vision_model = $VisionModel
    offline_install = [bool]$Offline
}
$diagnostics | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath ".\runtime-health.json" -Encoding UTF8

if (-not $SkipOllama -and (Get-Command ollama -ErrorAction SilentlyContinue)) {
    if ((Test-LocalRuntime "http://127.0.0.1:11434/api/tags").reachable) { Write-Host "Ollama detected. No model is downloaded by this installer." -ForegroundColor Green }
    else { Write-Warning "Ollama is installed but not reachable. Start it, then rerun the health check." }
}
if (-not $SkipWorker) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $projectRoot "scripts\register-workers.ps1")
}
Write-Host "Syntax Local AI Windows setup is ready." -ForegroundColor Green
Write-Host "Hardware/runtime report: .\runtime-health.json"
Write-Host "Start: .\venv\Scripts\python.exe manage.py runserver"
