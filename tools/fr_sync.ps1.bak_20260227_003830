Set-StrictMode -Off
$ErrorActionPreference="Stop"

$ROOT = "C:\Users\user\Desktop\Франкинштэйн"
$REPO = "https://github.com/ketler888-cmyk/FRANKENSTEIN_FACTORY.git"
$MSG  = ("sync: " + (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Host "[FAIL] $m" -ForegroundColor Red; throw $m }

function Safe-GitRmCached([string]$path){
  try { git rm -r --cached --ignore-unmatch -- $path 2>$null | Out-Null } catch { }
}

if(!(Test-Path -LiteralPath $ROOT)){ Fail "ROOT NOT FOUND: $ROOT" }
Set-Location $ROOT

if(!(Get-Command git -ErrorAction SilentlyContinue)){ Fail "git not found" }

# init if needed
if(!(Test-Path -LiteralPath ".git")){
  Info "git init..."
  git init | Out-Null
}

# ensure main
Info "checkout main..."
git checkout -B main | Out-Null

# remote
git remote remove origin 2>$null | Out-Null
git remote add origin $REPO | Out-Null

# cleanup stuck git states
$locks = @(".git\rebase-merge",".git\rebase-apply",".git\MERGE_HEAD",".git\index.lock")
foreach($l in $locks){
  if(Test-Path -LiteralPath $l){
    Remove-Item -LiteralPath $l -Recurse -Force -ErrorAction SilentlyContinue
  }
}

# HARD gitignore (mirror code/configs only; keep data/cache local)
@"
# ---- DATA / CACHE / OUTPUT (NEVER IN GIT) ----
SCALPING_DATA*/
SCALPING_DATA_PARQUET*/
SCALPING_DATA_RAW*/
cache/
logs/
results*/
results_ga*/
factory_top*/
gene_pool*/
tmp/
temp/

# ---- Large files ----
*.parquet
*.csv
*.zip
*.log

# ---- Python ----
.venv/
__pycache__/
*.pyc
"@ | Set-Content -LiteralPath ".gitignore" -Encoding UTF8

# untrack heavy dirs if they were ever added (but keep files on disk)
Safe-GitRmCached "cache"
Safe-GitRmCached "SCALPING_DATA"
Safe-GitRmCached "SCALPING_DATA_PARQUET"
Safe-GitRmCached "SCALPING_DATA_RAW"
Safe-GitRmCached "logs"
Safe-GitRmCached "results"
Safe-GitRmCached "results_ga"
Safe-GitRmCached "gene_pool"

# fetch before push (get fresh origin state)
Info "fetch origin..."
try { git fetch origin main --prune 2>$null | Out-Null } catch { }

# add + commit delta if needed
Info "git add -A"
git add -A | Out-Null

$porc = ""
try { $porc = (git status --porcelain) } catch { $porc = "X" }

if(-not [string]::IsNullOrWhiteSpace($porc)){
  Info "commit: $MSG"
  git commit -m $MSG | Out-Null
  Ok "commit created"
} else {
  Ok "no changes to commit"
}

# push delta (retry once if stale)
Info "push (delta)..."
$pushOk = $false
try {
  git push -u origin main --force-with-lease 2>&1 | Out-Host
  $pushOk = $true
} catch {
  Warn ("push failed: " + $_.Exception.Message)
  Warn "retry after fetch..."
  try { git fetch origin main --prune 2>$null | Out-Null } catch { }
  git push -u origin main --force-with-lease 2>&1 | Out-Host
  $pushOk = $true
}

if(-not $pushOk){ Fail "push failed" }

# verify mirror
try { git fetch origin main --prune 2>$null | Out-Null } catch { }
$local  = (git rev-parse HEAD 2>$null).Trim()
$remote = (git rev-parse origin/main 2>$null).Trim()

Info "LOCAL : $local"
Info "REMOTE: $remote"

if($local -and $remote -and ($local -eq $remote)){
  Ok "MIRROR PERFECT ✅ Local == origin/main"
} else {
  Warn "MIRROR MISMATCH ⚠️"
  Info "git status -sb:"
  git status -sb | Out-Host
  Info "diffstat origin/main..HEAD:"
  git diff --stat origin/main..HEAD | Out-Host
  Fail "Mirror mismatch"
}

Ok "SYNC DONE 🚀"
