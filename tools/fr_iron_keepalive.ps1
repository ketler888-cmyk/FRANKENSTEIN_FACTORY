Set-StrictMode -Off
$ErrorActionPreference = 'SilentlyContinue'
$ROOT  = 'C:\Users\user\Desktop\Франкинштэйн'
$TOOLS = Join-Path $ROOT 'tools'
$WATCH = Join-Path $TOOLS 'fr_autosync.ps1'

if(!(Test-Path -LiteralPath $WATCH)){ exit 0 }

$running = Get-WmiObject Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.CommandLine -and ($_.CommandLine -like "*fr_autosync.ps1*") }

if(-not $running){
  Start-Process -FilePath "powershell.exe" -ArgumentList @(
    '-NoProfile',
    '-ExecutionPolicy','Bypass',
    '-File', $WATCH
  ) -WindowStyle Hidden | Out-Null
}