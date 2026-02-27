Set-StrictMode -Off
$ErrorActionPreference = "Stop"

$ROOT = "C:\Users\user\Desktop\Франкинштэйн"
if(!(Test-Path -LiteralPath $ROOT)){ exit 2 }
Set-Location $ROOT

# heal locks / stuck rebase
Remove-Item -LiteralPath (Join-Path $ROOT ".git\index.lock") -Force -ErrorAction SilentlyContinue
if(Test-Path -LiteralPath (Join-Path $ROOT ".git\rebase-merge") -or Test-Path -LiteralPath (Join-Path $ROOT ".git\rebase-apply")){
  try { git rebase --abort 2>$null | Out-Null } catch {}
}

# ensure main
try { git checkout main 2>$null | Out-Null } catch {}

# no changes => exit
$porc = @(git status --porcelain)
if($porc.Count -eq 0){ exit 0 }

git add -A | Out-Null

# drop huge files from index (>50MB) + block them from reappearing
$staged = @(git diff --cached --name-only)
foreach($rel in $staged){
  if([string]::IsNullOrWhiteSpace($rel)){ continue }
  $p = Join-Path $ROOT $rel
  if(Test-Path -LiteralPath $p){
    try{
      $len = (Get-Item -LiteralPath $p -ErrorAction Stop).Length
      if($len -ge 50MB){
        git reset -q -- $rel | Out-Null
        $gi = Join-Path $ROOT ".gitignore"
        if(Test-Path -LiteralPath $gi){
          $norm = $rel.Replace("\","/")
          $existing = Get-Content -LiteralPath $gi -ErrorAction SilentlyContinue
          if($existing -notcontains $norm){ Add-Content -LiteralPath $gi -Value $norm }
        }
      }
    } catch {}
  }
}

$still = @(git diff --cached --name-only)
if($still.Count -eq 0){ exit 0 }

$msg = "tick: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
git commit -m $msg 2>$null | Out-Null

git fetch --prune origin | Out-Null
try { git rebase origin/main | Out-Null } catch { try { git rebase --abort 2>$null | Out-Null } catch {}; exit 3 }

git push origin main | Out-Null