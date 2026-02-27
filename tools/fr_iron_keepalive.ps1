Set-StrictMode -Off
$ErrorActionPreference = 'SilentlyContinue'

try {
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  [Console]::OutputEncoding = $utf8
  $OutputEncoding = $utf8
} catch {}

$ROOT = 'C:\Users\user\Desktop\Франкинштэйн'
$AUTOSYNC = Join-Path $ROOT 'tools\fr_autosync.ps1'
$LOG = Join-Path $ROOT 'logs\fr_iron_keepalive.log'

function Log([string]$m){
  try { ('[' + (Get-Date -Format s) + '] ' + $m) | Add-Content -LiteralPath $LOG -Encoding UTF8 } catch {}
}

try { Set-Location $ROOT } catch { Log('Set-Location failed: ' + $_.Exception.Message); exit 0 }

# heal stale git lock (safe)
try { Remove-Item -LiteralPath (Join-Path $ROOT '.git\index.lock') -Force -ErrorAction SilentlyContinue } catch {}

# start watcher if missing
try {
  $running = Get-WmiObject Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -and ($_.CommandLine -like "*fr_autosync.ps1*") }

  if(-not $running){
    if(Test-Path -LiteralPath $AUTOSYNC){
      Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoProfile','-ExecutionPolicy','Bypass','-File', $AUTOSYNC
      ) -WindowStyle Hidden
      Log('Watcher started')
    } else {
      Log('Missing autosync: ' + $AUTOSYNC)
    }
  } else {
    Log('Watcher already running')
  }
} catch {
  Log('Keepalive error: ' + $_.Exception.Message)
}

exit 0