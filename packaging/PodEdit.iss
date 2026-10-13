; PodEdit per-user installer definition (Inno Setup 6).
; INTERNAL_OFFLINE_BUILD may be defined only after model redistribution rights
; are documented. The public default deliberately excludes gated model assets.
#define MyAppName "PodEdit"
#define MyAppVersion "1.4.0"
#define MyAppPublisher "PodEdit Project"
#define MyAppExeName "PodEdit.Desktop.exe"
#define Payload "build\engine\PodEdit.Engine"

[Setup]
AppId={{A01A78B2-36DD-4BF5-82D1-9AD26F0850D4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\PodEdit
DefaultGroupName=PodEdit
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=build\installer
OutputBaseFilename=PodEdit-1.4.0-win-x64-setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".model_cache\*"
#ifdef INTERNAL_OFFLINE_BUILD
Source: "{#Payload}\.model_cache\*"; DestDir: "{app}\.model_cache"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif

[Icons]
Name: "{group}\PodEdit"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\PodEdit"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch PodEdit"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Intentionally empty. User-selected jobs and %LOCALAPPDATA%\PodEdit settings,
; caches, and models survive uninstall. A future UI may offer explicit cleanup.
