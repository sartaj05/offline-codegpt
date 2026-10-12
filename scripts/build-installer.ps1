param(
    [switch]$CheckOnly,
    [string]$Compiler = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$definition = Join-Path $projectRoot "installer\SyntaxLocalAI.iss"
if (-not (Test-Path -LiteralPath $definition)) { throw "Installer definition is missing: $definition" }
$content = Get-Content -LiteralPath $definition -Raw
foreach ($required in @("[Setup]", "AppId=", "DefaultDirName=", "[Files]", "install-windows.ps1")) {
    if ($content -notmatch [regex]::Escape($required)) { throw "Installer definition is missing $required" }
}
if ($CheckOnly) {
    Write-Host "Installer definition check passed: $definition" -ForegroundColor Green
    exit 0
}

if (-not $Compiler) {
    $candidate = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($candidate) { $Compiler = $candidate.Source }
}
if (-not $Compiler) {
    $candidate = Get-ChildItem "${env:ProgramFiles(x86)}\Inno Setup *\ISCC.exe", "${env:ProgramFiles}\Inno Setup *\ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($candidate) { $Compiler = $candidate.FullName }
}
if (-not $Compiler -or -not (Test-Path -LiteralPath $Compiler)) {
    throw "Inno Setup ISCC.exe was not found. Install Inno Setup, or use -CheckOnly to validate the definition without compiling."
}
& $Compiler $definition
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed with exit code $LASTEXITCODE." }
Write-Host "Installer built from $definition" -ForegroundColor Green
