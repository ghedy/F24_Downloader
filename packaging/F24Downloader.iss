; Per-user install: settings live outside {app} and survive uninstall.
#ifndef AppVersion
  #error AppVersion is required
#endif
[Setup]
AppId={{24D591C7-455D-48F6-BBAC-696B1D9C8B30}
AppName=F24 Downloader
AppVersion={#AppVersion}
AppPublisher=Quadra
AppPublisherURL=https://quadra.acortina.it/
AppSupportURL=https://github.com/ghedy/F24_Downloader/issues
AppUpdatesURL=https://github.com/ghedy/F24_Downloader
DefaultDirName={localappdata}\Programs\F24Downloader
DefaultGroupName=F24 Downloader
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\F24Downloader.exe
SetupIconFile={#AppIcon}
LicenseFile={#SourceDir}\LICENSE
OutputDir={#ArtifactDir}
OutputBaseFilename=F24-Downloader-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
[Tasks]
Name: "desktopicon"; Description: "Crea un collegamento sul desktop"; Flags: unchecked
[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\F24 Downloader"; Filename: "{app}\F24Downloader.exe"
Name: "{autodesktop}\F24 Downloader"; Filename: "{app}\F24Downloader.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\F24Downloader.exe"; Description: "Avvia F24 Downloader"; Flags: nowait postinstall skipifsilent
