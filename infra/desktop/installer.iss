#ifndef StageDir
  #error StageDir must be provided
#endif
#ifndef OutputDir
  #error OutputDir must be provided
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
[Setup]
AppId={{523E4A58-B493-4F3F-B080-848DDF2E54F1}
AppName=城市通勤数据分析及智能预测系统
AppVersion={#AppVersion}
AppPublisher=UrbanCommute Project
AppSupportURL=https://github.com/xingyu-wind/urban-commute-analysis
DefaultDirName={localappdata}\Programs\UrbanCommute
DefaultGroupName=城市通勤演示版
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
OutputDir={#OutputDir}
OutputBaseFilename=UrbanCommute-Setup-{#AppVersion}
Compression=lzma2/fast
SolidCompression=no
DiskSpanning=no
UninstallDisplayIcon={app}\UrbanCommute.exe
CloseApplications=yes
RestartApplications=no
WizardStyle=modern
LicenseFile=TERMS.txt
InfoBeforeFile=INSTALL-NOTES.txt
SetupLogging=yes
VersionInfoVersion={#AppVersion}.0
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autodesktop}\城市通勤演示版"; Filename: "{app}\UrbanCommute.exe"; WorkingDir: "{app}"
Name: "{group}\城市通勤演示版"; Filename: "{app}\UrbanCommute.exe"; WorkingDir: "{app}"
Name: "{group}\卸载城市通勤演示版"; Filename: "{uninstallexe}"
[Run]
Filename: "{app}\prerequisites\VC_redist.x64.exe"; Parameters: "/install /passive /norestart"; StatusMsg: "正在安装随附 Microsoft VC++ x64 运行库……"; Check: NeedsVCRuntime; Flags: shellexec waituntilterminated
Filename: "{app}\UrbanCommute.exe"; Description: "启动城市通勤演示版"; Flags: nowait postinstall skipifsilent
[Code]
function NeedsVCRuntime(): Boolean;
begin
  Result := not FileExists(ExpandConstant('{sys}\vcruntime140.dll')) or
            not FileExists(ExpandConstant('{sys}\vcruntime140_1.dll')) or
            not FileExists(ExpandConstant('{sys}\msvcp140.dll'));
end;

function InitializeSetup(): Boolean;
var Existing: String; OldVersion, NewVersion: Int64;
begin
  Result := True;
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{523E4A58-B493-4F3F-B080-848DDF2E54F1}_is1', 'DisplayVersion', Existing) then
    if StrToVersion(Existing + '.0', OldVersion) and StrToVersion('{#AppVersion}.0', NewVersion) then
    if ComparePackedVersion(OldVersion, NewVersion) > 0 then begin
      MsgBox('已安装更新的版本。为保护数据，请不要降级覆盖。', mbError, MB_OK);
      Result := False;
    end;
end;
