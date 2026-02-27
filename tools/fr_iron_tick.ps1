Set-StrictMode -Off
$ErrorActionPreference = 'SilentlyContinue'
try {
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  [Console]::OutputEncoding = $utf8
  $OutputEncoding = $utf8
} catch {}

$ROOT   = 'C:\Users\user\Desktop\Франкинштэйн'
$BRANCH = 'main'
$MAX_FILE_BYTES = 99614720
$LOG    = 'C:\Users\user\Desktop\Франкинштэйн\logs\fr_iron_tick.log'
$ALERT  = 'C:\Users\user\Desktop\Франкинштэйн\logs\fr_iron_alert.txt'
$LOCK   = Join-Path $ROOT 'logs\fr_iron_tick.lock'

function LogLine([string]$m){
  try { ($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' | ' + $m) | Out-File -LiteralPath $LOG -Append -Encoding UTF8 } catch {}
}
function Alert([string]$m){
  try { ($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' | ' + $m) | Out-File -LiteralPath $ALERT -Append -Encoding UTF8 } catch {}
  LogLine ('ALERT: ' + $m)
}

# single instance mutex
$mutexName = 'Global\FRANKEN_IRON_TICK_MUTEX'
$mutex = $null
$has = $false
try { $mutex = New-Object System.Threading.Mutex($false, $mutexName); $has = $mutex.WaitOne(0) } catch {}
if(-not $has){ LogLine 'SKIP: already running (mutex busy)'; exit 0 }

try {
  try { ('PID=' + $PID + ' START=' + (Get-Date -Format s)) | Out-File -LiteralPath $LOCK -Encoding UTF8 -Force } catch {}

  LogLine 'TICK START'
  if(!(Test-Path -LiteralPath $ROOT)){ Alert ('ROOT missing: ' + $ROOT); exit 31 }
  try { Set-Location $ROOT } catch { Alert 'cd failed'; exit 32 }
  if(!(Test-Path -LiteralPath (Join-Path $ROOT '.git'))){ Alert 'Not a git repo'; exit 33 }

  # heal stuck states
  Remove-Item -LiteralPath (Join-Path $ROOT '.git\index.lock') -Force -ErrorAction SilentlyContinue
  if(Test-Path -LiteralPath (Join-Path $ROOT '.git\rebase-merge')){ try{ & git rebase --abort 1>$null 2>$null } catch{} }
  if(Test-Path -LiteralPath (Join-Path $ROOT '.git\rebase-apply')){ try{ & git rebase --abort 1>$null 2>$null } catch{} }
  if(Test-Path -LiteralPath (Join-Path $ROOT '.git\MERGE_HEAD'))  { try{ & git merge  --abort 1>$null 2>$null } catch{} }

  # fetch non-fatal
  try { & git fetch --prune origin 1>$null 2>$null } catch { LogLine 'fetch failed (offline?)' }

  # dirty?
  $dirty = @(& git status --porcelain 2>$null)
  if($dirty.Count -eq 0){ LogLine 'CLEAN -> no commit'; exit 0 }

  # stage
  & git add -A 1>$null 2>$null

  # drop huge files
  $staged = @(& git diff --cached --name-only 2>$null)
  foreach($rel in $staged){
    if([string]::IsNullOrWhiteSpace($rel)){ continue }
    $p = Join-Path $ROOT $rel
    if(Test-Path -LiteralPath $p){
      try {
        $len = (Get-Item -LiteralPath $p -ErrorAction Stop).Length
        if($len -ge $MAX_FILE_BYTES){
          & git reset -q -- $rel 1>$null 2>$null
          LogLine ('DROP >95MB from index: ' + $rel)
        }
      } catch {}
    }
  }

  $still = @(& git diff --cached --name-only 2>$null)
  if($still.Count -eq 0){ LogLine 'Nothing staged after size filter'; exit 0 }

  # commit
  $msg = 'tick: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
  $cOut = & git commit -m $msg 2>&1
  if($LASTEXITCODE -ne 0){
    Alert ('COMMIT FAIL: ' + (($cOut | ForEach-Object { $_ }) -join ' || '))
    exit 41
  }

  # rebase (keep linear)
  try { & git fetch --prune origin 1>$null 2>$null } catch {}
  try { & git rebase ('origin/' + $BRANCH) 1>$null 2>$null } catch {
    try { & git rebase --abort 1>$null 2>$null } catch {}
    Alert 'REBASE CONFLICT -> abort'
    exit 42
  }

  # push
  $pushOut = & git push origin $BRANCH 2>&1
  if($LASTEXITCODE -ne 0){
    Alert ('PUSH FAIL: ' + (($pushOut | ForEach-Object { $_ }) -join ' || '))
    exit 43
  }

  LogLine 'PUSH OK'
  exit 0
}
finally {
  try { Remove-Item -LiteralPath $LOCK -Force -ErrorAction SilentlyContinue } catch {}
  try { if($mutex){ $mutex.ReleaseMutex() | Out-Null; $mutex.Dispose() } } catch {}
}
