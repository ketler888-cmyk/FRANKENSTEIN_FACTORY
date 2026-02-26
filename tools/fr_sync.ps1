Set-StrictMode -Off
$ErrorActionPreference = "Stop"

$ROOT = "C:\Users\user\Desktop\Франкинштэйн"
$REPO = "https://github.com/ketler888-cmyk/FRANKENSTEIN_FACTORY.git"
$MSG  = ("sync: " + (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Host "[FAIL] $m" -ForegroundColor Red; throw $m }

function Split-GitArgs([string]$s){
  $s = $s.Trim()
  if($s.Length -eq 0){ return @() }
  $m = [regex]::Matches($s, '("([^"\\]|\\.)*"|\S+)')
  $a = @()
  foreach($x in $m){
    $t = $x.Value
    if($t.StartsWith('"') -and $t.EndsWith('"')){
      $t = $t.Substring(1, $t.Length-2)
      $t = $t -replace '\\"','"'
      $t = $t -replace '\\\\','\'
    }
    $a += $t
  }
  return $a
}

function Run-Git([string]$argsLine, [string]$label){
  $args = Split-GitArgs $argsLine
  if(!$args -or $args.Count -eq 0){ throw "Run-Git: empty args for $label" }

  # IMPORTANT (PS5.1): git often writes normal messages to stderr -> PowerShell turns into NativeCommandError when EAP=Stop
  $old = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    $out  = & git @args 2>&1
    $code = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $old
  }

  $txt = ""
  if($out){ $txt = ($out | Out-String).TrimEnd() }
  if($txt.Length -gt 0){ $out | Out-Host }

  if($code -ne 0){
    throw ("git " + $label + " failed (exit=" + $code + "):`n" + $txt)
  }
  if($txt -match "(?im)fatal:" -or $txt -match "(?im)^error:" -or $txt -match "(?im)\[rejected\]"){
    throw ("git " + $label + " failed:`n" + $txt)
  }
}

function Safe-RmCached([string]$path){
  $old = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try { & git rm -r --cached --ignore-unmatch -- $path 2>$null | Out-Null } finally { $ErrorActionPreference = $old }
  $null = $LASTEXITCODE
}

if(!(Test-Path -LiteralPath $ROOT)){ Fail "ROOT NOT FOUND: $ROOT" }
Set-Location -LiteralPath $ROOT

$git = Get-Command git -ErrorAction SilentlyContinue
if(!$git){ Fail "git not found. Install Git for Windows." }

if(!(Test-Path -LiteralPath ".git")){
  Info "git init..."
  Run-Git 'init' 'init'
}

Info "checkout main..."
Run-Git 'checkout -B main' 'checkout'

# remote (hard set)
$old = $ErrorActionPreference; $ErrorActionPreference="Continue"
try { & git remote remove origin 2>$null | Out-Null } finally { $ErrorActionPreference=$old }
$old = $ErrorActionPreference; $ErrorActionPreference="Continue"
try { & git remote add origin $REPO 2>$null | Out-Null } finally { $ErrorActionPreference=$old }

# clean stuck states
$locks = @(".git\rebase-merge",".git\rebase-apply",".git\MERGE_HEAD",".git\index.lock")
foreach($l in $locks){
  if(Test-Path -LiteralPath $l){
    Remove-Item -LiteralPath $l -Recurse -Force -ErrorAction SilentlyContinue
  }
}

# harden .gitignore (no data/cache/logs/results/zips)
@"
SCALPING_DATA*/
SCALPING_DATA_PARQUET*/
cache/
logs/
results*/
*.parquet
*.csv
.venv/
__pycache__/
*.log
*.zip
tmp/
temp/
"@ | Set-Content -LiteralPath ".gitignore" -Encoding UTF8

# ensure heavy dirs are NOT tracked (keep locally)
Safe-RmCached "cache"
Safe-RmCached "SCALPING_DATA_PARQUET"
Safe-RmCached "SCALPING_DATA"
Safe-RmCached "logs"
Safe-RmCached "results"

Info "fetch origin..."
try { Run-Git 'fetch origin main --prune' 'fetch' } catch { Warn $_.Exception.Message }

Info "git add -A"
Run-Git 'add -A' 'add'

$old = $ErrorActionPreference; $ErrorActionPreference="Continue"
try { $porc = & git status --porcelain 2>$null } finally { $ErrorActionPreference=$old }
if(-not [string]::IsNullOrWhiteSpace($porc)){
  Info "commit: $MSG"
  Run-Git ('commit -m "' + ($MSG.Replace('"','\"')) + '"') 'commit'
  Ok "commit created"
}else{
  Ok "no changes"
}

Info "push (delta)..."
try {
  Run-Git 'push -u origin main --force-with-lease' 'push'
  Ok "push OK"
} catch {
  Warn $_.Exception.Message
  Warn "retry: fetch + push"
  try { Run-Git 'fetch origin main --prune' 'fetch(retry)' } catch { Warn $_.Exception.Message }
  Run-Git 'push -u origin main --force-with-lease' 'push(retry)'
  Ok "push OK (retry)"
}

# verify mirror
Run-Git 'fetch origin main --prune' 'fetch(final)'
$local  = (& git rev-parse HEAD).Trim()
$remote = (& git rev-parse origin/main).Trim()

Info "LOCAL : $local"
Info "REMOTE: $remote"

if($local -and $remote -and ($local -eq $remote)){
  Ok "MIRROR PERFECT ✅ Local == origin/main"
}else{
  Warn "MIRROR MISMATCH ⚠️"
  & git status -sb | Out-Host
  & git diff --stat origin/main..HEAD | Out-Host
  throw "Mirror mismatch"
}

Ok "SYNC DONE 🚀"
