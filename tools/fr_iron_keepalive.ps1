Set-StrictMode -Off
$ErrorActionPreference = 'SilentlyContinue'
try {
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  [Console]::OutputEncoding = $utf8
  $OutputEncoding = $utf8
} catch {}

$ROOT   = 'C:\Users\user\Desktop\Франкинштэйн'
$BRANCH = 'main'
$LOG    = 'C:\Users\user\Desktop\Франкинштэйн\logs\fr_iron_keepalive.log'

function LogLine([string]$m){
  try { ($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' | ' + $m) | Out-File -LiteralPath $LOG -Append -Encoding UTF8 } catch {}
}
function IsAlive(){
  try{
    $p = Get-WmiObject Win32_Process -Filter "Name='powershell.exe'" |
      Where-Object { $_.CommandLine -and ($_.CommandLine -like "*fr_iron_tick.ps1*") } |
      Select-Object -First 1
    return [bool]$p
  } catch { return $false }
}

LogLine 'KEEPALIVE START'
if(!(Test-Path -LiteralPath $ROOT)){ LogLine ('ROOT missing: ' + $ROOT); exit 21 }
try { Set-Location $ROOT } catch { LogLine 'cd failed'; exit 22 }
if(!(Test-Path -LiteralPath (Join-Path $ROOT '.git'))){ LogLine 'Not a git repo'; exit 23 }

# just a sanity fetch (non-fatal if offline)
try { & git fetch --prune origin 1>$null 2>$null } catch { LogLine 'fetch failed (offline?)' }

LogLine 'KEEPALIVE OK'
exit 0
