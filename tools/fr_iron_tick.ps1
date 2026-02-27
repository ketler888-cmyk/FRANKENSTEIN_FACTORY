Set-StrictMode -Off
$ErrorActionPreference = 'SilentlyContinue'

function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }

$ROOT   = 'C:\Users\user\Desktop\Франкинштэйн'
$BRANCH = 'main'

if(!(Test-Path -LiteralPath $ROOT)){ exit 10 }
Set-Location $ROOT

try { git checkout $BRANCH 1>$null 2>$null } catch { exit 11 }

# heal locks / stuck ops
Remove-Item -LiteralPath (Join-Path $ROOT ".git\index.lock") -Force -ErrorAction SilentlyContinue
if(Test-Path -LiteralPath (Join-Path $ROOT ".git\rebase-merge")){ try{ git rebase --abort 2>$null | Out-Null } catch{} }
if(Test-Path -LiteralPath (Join-Path $ROOT ".git\rebase-apply")){ try{ git rebase --abort 2>$null | Out-Null } catch{} }

# update from remote (avoid diverging)
try { git fetch --prune origin 1>$null 2>$null } catch { exit 12 }
try { git rebase ("origin/" + $BRANCH) 1>$null 2>$null } catch { try{ git rebase --abort 2>$null | Out-Null } catch{}; exit 13 }

# commit+push only if dirty
$dirty = @(git status --porcelain)
if($dirty.Count -eq 0){ exit 0 }

git add -A 1>$null 2>$null
$staged = @(git diff --cached --name-only)
if($staged.Count -eq 0){ exit 0 }

$msg = "tick: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
git commit -m $msg 1>$null 2>$null

try { git fetch --prune origin 1>$null 2>$null } catch { exit 14 }
try { git rebase ("origin/" + $BRANCH) 1>$null 2>$null } catch { try{ git rebase --abort 2>$null | Out-Null } catch{}; exit 15 }
try { git push origin $BRANCH 1>$null 2>$null } catch { exit 16 }

Ok "tick pushed"