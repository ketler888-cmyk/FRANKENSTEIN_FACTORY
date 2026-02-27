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
$LOCK   = Join-Path $ROOT 'logs\fr_iron_tick.lock'

function LogLine([string]$m){
  try { ($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' | ' + $m) | Out-File -LiteralPath $LOG -Append -Encoding UTF8 } catch {}
}

# ---- SINGLE INSTANCE (global mutex) ----
$mutexName = 'Global\FRANKEN_IRON_TICK_MUTEX'
$mutex = $null
$has = $false
try {
  $mutex = New-Object System.Threading.Mutex($false, $mutexName)
  $has = $mutex.WaitOne(0)
} catch {}

if(-not $has){
  LogLine 'SKIP: already running (mutex busy)'
  exit 0
}

try {
  # lockfile (debug)
  try { ('PID=' + $PID + ' START=' + (Get-Date -Format s)) | Out-File -LiteralPath $LOCK -Encoding UTF8 -Force } catch {}

  LogLine 'TICK START'
  if(!(Test-Path -LiteralPath $ROOT)){ LogLine ('ROOT missing: ' + $ROOT); exit 31 }
  try { Set-Location $ROOT } catch { LogLine 'cd failed'; exit 32 }
  if(!(Test-Path -LiteralPath (Join-Path $ROOT '.git'))){ LogLine 'Not a git repo'; exit 33 }

  # heal locks / stuck ops
  Remove-Item -LiteralPath (Join-Path $ROOT '.git\index.lock') -Force -ErrorAction SilentlyContinue
  if(Test-Path -LiteralPath (Join-Path $ROOT '.git\rebase-merge')){ try{ & git rebase --abort 1>$null 2>$null } catch{} }
  if(Test-Path -LiteralPath (Join-Path $ROOT '.git\rebase-apply')){ try{ & git rebase --abort 1>$null 2>$null } catch{} }
  if(Test-Path -LiteralPath (Join-Path $ROOT '.git\MERGE_HEAD'))  { try{ & git merge  --abort 1>$null 2>$null } catch{} }

  # fetch is non-fatal (offline ok)
  try { & git fetch --prune origin 1>$null 2>$null } catch { LogLine 'fetch failed (offline?)' }

  # quick dirty check
  $dirty = @(& git status --porcelain 2>$null)
  if($dirty.Count -eq 0){ LogLine 'CLEAN -> no commit'; exit 0 }

  # stage all
  & git add -A 1>$null 2>$null

  # drop huge files from index (>95MB)
  $staged = @(& git diff --cached --name-only 2>$null)
  foreach($rel in $staged){
    if([string]::IsNullOrWhiteSpace($rel)){ continue }
    $p = Join-Path $ROOT $rel
    if(Test-Path -LiteralPath $p){
      try{
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

  $msg = 'tick: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
  $cOut = & git commit -m $msg 2>&1
  if($LASTEXITCODE -ne 0){
    LogLine ('COMMIT FAIL: ' + (($cOut | ForEach-Object { $_ }) -join ' || '))
    exit 41
  }

  # keep linear history (if remote moved)
  try { & git fetch --prune origin 1>$null 2>$null } catch {}
  try {
    & git rebase ('origin/' + $BRANCH) 1>$null 2>$null
  } catch {
    try { & git rebase --abort 1>$null 2>$null } catch {}
    LogLine 'REBASE CONFLICT -> abort'
    exit 42
  }

  # push (progress noise allowed; exitcode decides)
  $pushOut = & git push origin $BRANCH 2>&1
  if($LASTEXITCODE -ne 0){
    LogLine ('PUSH FAIL: ' + (($pushOut | ForEach-Object { $_ }) -join ' || '))
    exit 43
  }

  LogLine 'PUSH OK'
  exit 0
}
finally {
  try { Remove-Item -LiteralPath $LOCK -Force -ErrorAction SilentlyContinue } catch {}
  try { if($mutex){ $mutex.ReleaseMutex() | Out-Null; $mutex.Dispose() } } catch {}
}
