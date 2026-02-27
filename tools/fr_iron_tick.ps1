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

function LogLine([string]$m){
  try { ($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' | ' + $m) | Out-File -LiteralPath $LOG -Append -Encoding UTF8 } catch {}
}
function GitRun([string[]]$a){
  $out = & git @a 2>&1
  $code = $LASTEXITCODE
  if($code -ne 0){
    LogLine (('GIT FAIL (' + $code + '): git ' + ($a -join ' ') + ' | ' + (($out | ForEach-Object { $_ }) -join ' || ')))
    return $false
  }
  return $true
}

LogLine 'TICK START'
if(!(Test-Path -LiteralPath $ROOT)){ LogLine ('ROOT missing: ' + $ROOT); exit 31 }
try { Set-Location $ROOT } catch { LogLine 'cd failed'; exit 32 }
if(!(Test-Path -LiteralPath (Join-Path $ROOT '.git'))){ LogLine 'Not a git repo'; exit 33 }

# heal locks / stuck ops
Remove-Item -LiteralPath (Join-Path $ROOT '.git\index.lock') -Force -ErrorAction SilentlyContinue
if(Test-Path -LiteralPath (Join-Path $ROOT '.git\rebase-merge')){ try{ & git rebase --abort 1>$null 2>$null } catch{} }
if(Test-Path -LiteralPath (Join-Path $ROOT '.git\rebase-apply')){ try{ & git rebase --abort 1>$null 2>$null } catch{} }
if(Test-Path -LiteralPath (Join-Path $ROOT '.git\MERGE_HEAD'))  { try{ & git merge  --abort 1>$null 2>$null } catch{} }

# update refs (non-fatal if offline)
GitRun @('fetch','--prune','origin') | Out-Null

# nothing to do?
$dirty = @(& git status --porcelain 2>$null)
if($dirty.Count -eq 0){ LogLine 'CLEAN -> no commit'; exit 0 }

# stage all
GitRun @('add','-A') | Out-Null

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
if(!(GitRun @('commit','-m',$msg))){ exit 41 }

# rebase to keep strict mirror (if remote moved)
GitRun @('fetch','--prune','origin') | Out-Null
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
