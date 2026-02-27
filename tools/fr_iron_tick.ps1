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
$LOG   = 'C:\Users\user\Desktop\Франкинштэйн\logs\fr_iron_tick.log'

function LogLine([string]$s){
  try { ($s) | Out-File -LiteralPath $LOG -Append -Encoding UTF8 } catch {}
}

function Invoke-Git([string[]]$GitArgs){
  if($null -eq $GitArgs -or $GitArgs.Count -eq 0){ throw 'Invoke-Git: empty args' }
  $out = & git @GitArgs 2>&1
  $code = $LASTEXITCODE
  if($code -ne 0){
    throw ("git " + ($GitArgs -join ' ') + " failed (exit=$code):
" + ($out -join "
"))
  }
  return $out
}

LogLine ('--- TICK ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ---')

if(!(Test-Path -LiteralPath $ROOT)){ LogLine 'ROOT missing'; exit 2 }
Set-Location $ROOT

# heal locks
Remove-Item -LiteralPath (Join-Path $ROOT '.git\index.lock') -Force -ErrorAction SilentlyContinue
if(Test-Path -LiteralPath (Join-Path $ROOT '.git\rebase-merge')){ try{ & git rebase --abort 1>$null 2>$null } catch{} }
if(Test-Path -LiteralPath (Join-Path $ROOT '.git\rebase-apply')){ try{ & git rebase --abort 1>$null 2>$null } catch{} }
if(Test-Path -LiteralPath (Join-Path $ROOT '.git\MERGE_HEAD'))  { try{ & git merge  --abort 1>$null 2>$null } catch{} }

# ensure branch (do not throw on non-terminating noise)
try { Invoke-Git @('checkout',$BRANCH) | Out-Null } catch { LogLine $_.Exception.Message; exit 11 }

# update
try { Invoke-Git @('fetch','--prune','origin') | Out-Null } catch { LogLine $_.Exception.Message; exit 12 }
try { Invoke-Git @('rebase',('origin/' + $BRANCH)) | Out-Null } catch {
  try { & git rebase --abort 1>$null 2>$null } catch {}
  LogLine ('Rebase failed: ' + $_.Exception.Message)
  exit 13
}

# if clean -> exit
$dirty = @( & git status --porcelain )
if($dirty.Count -eq 0){ LogLine 'Clean -> no commit'; exit 0 }

# stage all BUT drop huge files from index
Invoke-Git @('add','-A') | Out-Null

$staged = @( & git diff --cached --name-only )
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

$still = @( & git diff --cached --name-only )
if($still.Count -eq 0){ LogLine 'Nothing staged after size filter'; exit 0 }

$msg = 'tick: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
try { Invoke-Git @('commit','-m',$msg) | Out-Null } catch { LogLine $_.Exception.Message; exit 14 }

# push (stderr noise allowed, exitcode decides)
$pushOut = & git push origin $BRANCH 2>&1
if($LASTEXITCODE -ne 0){
  LogLine ('PUSH FAIL: ' + ($pushOut -join ' | '))
  exit 16
}

LogLine 'PUSH OK'
exit 0
