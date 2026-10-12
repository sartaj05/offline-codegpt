#define MyAppName "Syntax Local AI"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Syntax Local"

[Setup]
AppId={{D6D37B01-5D3D-4BBE-8A89-3F4A8C7E91B2}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Syntax Local AI
DefaultGroupName={#MyAppName}
OutputDir=.
OutputBaseFilename=SyntaxLocalAI-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest

[Files]
Source: "..\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion; Excludes: ".git\*;venv\*;staticfiles\*;__pycache__\*;*.pyc;db.sqlite3;local_models\*;installer\*.exe"

[Icons]
Name: "{group}\Syntax Local AI setup"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File \"{app}\scripts\install-windows.ps1\""; WorkingDir: "{app}"
Name: "{group}\Syntax Local AI"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -Command \"Start-Process '{app}\venv\Scripts\python.exe' -ArgumentList 'manage.py runserver' -WorkingDirectory '{app}'\""; WorkingDir: "{app}"

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File \"{app}\scripts\install-windows.ps1\" -Uninstall -Confirmed"; WorkingDir: "{app}"; Flags: runhidden
