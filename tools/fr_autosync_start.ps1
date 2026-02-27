Set-StrictMode -Off
$ErrorActionPreference = 'SilentlyContinue'

$AUTOSYNC = 'C:\Users\user\Desktop\Франкинштэйн\tools\fr_autosync.ps1'

$running = Get-WmiObject Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.CommandLine -and ($_.CommandLine -like "*fr_autosync.ps1*") }

if(-not $running){
  Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy","Bypass",
    "-File", $AUTOSYNC
  ) -WindowStyle Hidden
}