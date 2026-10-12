param(
    [switch]$Unregister,
    [string]$TaskName = "SyntaxLocalAI Offline Workers",
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $projectRoot "venv\Scripts\python.exe" }

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $TaskName" -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python executable was not found at $PythonPath. Run install-windows.ps1 first."
}

$action = New-ScheduledTaskAction -Execute $PythonPath -Argument "manage.py run_offline_workers --loop" -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Description "Runs Syntax Local AI agent jobs and offline scheduled tasks." -Force | Out-Null
Write-Host "Registered scheduled task: $TaskName" -ForegroundColor Green
