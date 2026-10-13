param(
    [switch]$Register,
    [switch]$Unregister,
    [Parameter(Mandatory = $false)][string]$ServerUrl,
    [Parameter(Mandatory = $false)][string]$Token,
    [Parameter(Mandatory = $false)][string]$Workspace,
    [Parameter(Mandatory = $false)][string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$valueName = "SyntaxLocalAIHybridConnector"
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

if ($Register) {
    if ([string]::IsNullOrWhiteSpace($ServerUrl) -or [string]::IsNullOrWhiteSpace($Token) -or [string]::IsNullOrWhiteSpace($Workspace)) {
        throw "-Register requires -ServerUrl, -Token, and -Workspace."
    }
    $scriptPath = Join-Path $PSScriptRoot "local_connector_tray.py"
    $arguments = "`"$scriptPath`" --server-url `"$ServerUrl`" --token `"$Token`" --workspace `"$Workspace`" --autostart"
    New-Item -Path $runKey -Force | Out-Null
    New-ItemProperty -Path $runKey -Name $valueName -Value "`"$Python`" $arguments" -PropertyType String -Force | Out-Null
    Write-Output "Registered Hybrid connector startup entry."
    exit 0
}

if ($Unregister) {
    Remove-ItemProperty -Path $runKey -Name $valueName -ErrorAction SilentlyContinue
    Write-Output "Removed Hybrid connector startup entry."
    exit 0
}

throw "Use -Register or -Unregister."
