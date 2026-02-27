Set-StrictMode -Off
$ErrorActionPreference = 'SilentlyContinue'

try {
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  [Console]::OutputEncoding = $utf8
  $OutputEncoding = $utf8
} catch {}

$ROOT   = 'C:\Users\user\Desktop\Франкинштэйн'
$BRANCH = 'main'
$LOG    = Join-Path $ROOT 'logs\fr_iron_tick.log'

function Log([string]$m){
  try { ('[' + (Get-Date -Format s) + '] ' + $m) | Add-Content -LiteralPath $LOG -Encoding UTF8 } catch {}
}

function Invoke-Git([string[]]$Args){
  # Captures stdout+stderr; throws ONLY when exitcode != 0 (progress messages are fine)
  $out = & git @Args 2>&1
  $code = $LASTEXITCODE
  if($code -ne 0){
    throw ("git " + ($Args -join ' ') + " failed (exit=$code):
" + ($out -join "
"))
  }
  return $out
}

try { Set-Location $ROOT } catch { Log('Set-Location failed: ' + $_.Exception.Message); exit 0 }

# heal stuck ops (safe)
try { Remove-Item -LiteralPath (Join-Path $ROOT '.git\index.lock') -Force -ErrorAction SilentlyContinue } catch {}
if(Test-Path -LiteralPath (Join-Path $ROOT '.git\rebase-merge')){ try{ Invoke-Git @('rebase','--abort') | Out-Null } catch{} }
if(Test-Path -LiteralPath (Join-Path $ROOT '.git\rebase-apply')){ try{ Invoke-Git @('rebase','--abort') | Out-Null } catch{} }
if(Test-Path -LiteralPath (Join-Path $ROOT '.git\MERGE_HEAD'))  { try{ Invoke-Git @('merge','--abort')  | Out-Null } catch{} }

try { Invoke-Git @('checkout', $BRANCH) | Out-Null } catch { Log('checkout warning: ' + $_.Exception.Message) }

try { Invoke-Git @('fetch','--prune','origin') | Out-Null } catch { Log('fetch failed: ' + $_.Exception.Message); exit 0 }

# rebase to keep linear history
try { Invoke-Git @('rebase', ('origin/' + $BRANCH)) | Out-Null } catch {
  try { Invoke-Git @('rebase','--abort') | Out-Null } catch {}
  Log('rebase failed: ' + $_.Exception.Message)
  exit 0
}

# if clean -> nothing to do
$dirty = @( & git status --porcelain 2>$null )
if($dirty.Count -eq 0){ Log('clean -> no-op'); exit 0 }

# add all changes (respects .gitignore)
try { Invoke-Git @('add','-A') | Out-Null } catch { Log('add failed: ' + $_.Exception.Message); exit 0 }
$staged = @( & git diff --cached --name-only 2>$null )
if($staged.Count -eq 0){ Log('nothing staged'); exit 0 }

# block huge files (>95MB) to avoid GitHub rejection
foreach($rel in $staged){
  if([string]::IsNullOrWhiteSpace($rel)){ continue }
  $p = Join-Path $ROOT $rel
  try {
    if(Test-Path -LiteralPath $p){
      $len = (Get-Item -LiteralPath $p).Length
      if($len -ge 95MB){
        & git reset -q -- $rel 2>$null | Out-Null
        Log('SKIP huge file: ' + $rel)
      }
    }
  } catch {}
}

$still = @( & git diff --cached --name-only 2>$null )
if($still.Count -eq 0){ Log('after huge-skip nothing staged'); exit 0 }

try {
  $msg = 'tick: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
  Invoke-Git @('commit','-m', $msg) | Out-Null
  Log('committed: ' + $msg)
} catch {
  Log('commit failed: ' + $_.Exception.Message)
  exit 0
}

# sync again and push
try { Invoke-Git @('fetch','--prune','origin') | Out-Null } catch { Log('fetch2 failed: ' + $_.Exception.Message); exit 0 }
try { Invoke-Git @('rebase', ('origin/' + $BRANCH)) | Out-Null } catch {
  try { Invoke-Git @('rebase','--abort') | Out-Null } catch {}
  Log('rebase2 failed: ' + $_.Exception.Message)
  exit 0
}

try {
  Invoke-Git @('push','origin', $BRANCH) | Out-Null
  Log('push ok')
} catch {
  Log('push failed: ' + $_.Exception.Message)
  exit 0
}

exit 0