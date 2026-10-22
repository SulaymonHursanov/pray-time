; Установщик «Время намаза». Собирается скриптом build.ps1 (нужен Inno Setup 6).

#define AppName "Время намаза"
; при сборке релиза версия берётся из тега: build.ps1 -Version 1.2.3 → ISCC /DAppVersion=1.2.3
#ifndef AppVersion
  #define AppVersion "1.0.3"
#endif
#define AppExe "PrayTime.exe"

[Setup]
AppId={{6B1E3E0A-7C1D-4E6B-9A3F-2D5C8B1F4A70}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=PrayTime
DefaultDirName={autopf}\PrayTime
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; ставится без прав администратора (в профиль пользователя); можно выбрать «для всех»
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=PrayTime-Setup-{#AppVersion}
SetupIconFile=PrayTime.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "autostart"; Description: "Запускать вместе с Windows"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "..\dist\PrayTime\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PrayTime"; ValueData: """{app}\{#AppExe}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// закрываем запущенную программу перед обновлением и удалением
procedure KillApp();
var Code: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(500);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  KillApp();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  KillApp();
  Result := True;
end;
