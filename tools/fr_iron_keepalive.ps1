Set-StrictMode -Off
$ErrorActionPreference = 'SilentlyContinue'
try {
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  [Console]::OutputEncoding = $utf8
  $OutputEncoding = $utf8
} catch {}

$ROOT = 'C:\Users\user\Desktop\Франкинштэйн'
$LOGS = 'C:\Users\user\Desktop\Франкинштэйн\logs'
$LOG  = 'C:\Users\user\Desktop\Франкинштэйн\logs\fr_iron_keepalive.log'
$AUTOSYNC = Join-Path $ROOT 'tools\fr_autosync.ps1'

function LogLine([string]$s){
  try { ($s) | Out-File -LiteralPath $LOG -Append -Encoding UTF8 } catch {}
}

LogLine ('--- KEEPALIVE ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ---')

if(!(Test-Path -LiteralPath $ROOT)){ LogLine 'ROOT missing'; exit 2 }
if(!(Test-Path -LiteralPath $AUTOSYNC)){ LogLine 'fr_autosync.ps1 missing'; exit 3 }

# detect autosync by commandline substring
try {
  $running = Get-WmiObject Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -and ($_.CommandLine -like '*fr_autosync.ps1*') }
} catch {
  LogLine ('WMI error: ' + $_.Exception.Message)
  exit 4
}

if(-not $running){
  try {
    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
      '-NoProfile',
      '-ExecutionPolicy','Bypass',
      '-File', $AUTOSYNC
    ) -WindowStyle Hidden
    LogLine 'Started fr_autosync.ps1'
    exit 0
  } catch {
    LogLine ('Start-Process failed: ' + $_.Exception.Message)
    exit 5
  }
} else {
  LogLine ('Already running PID=' + (($running | Select-Object -First 1).ProcessId))
  exit 0
}
