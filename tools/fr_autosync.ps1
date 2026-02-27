Set-StrictMode -Off
$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Host "[FAIL] $m" -ForegroundColor Red; throw $m }

$ROOT = "C:\Users\user\Desktop\Франкинштэйн"
$LOG  = Join-Path $ROOT "logs\fr_autosync.log"

if (!(Test-Path -LiteralPath $ROOT)) { Fail "ROOT not found: $ROOT" }
Set-Location $ROOT

if (!(Get-Command git -ErrorAction SilentlyContinue)) { Fail "git not found in PATH" }
if (!(Test-Path -LiteralPath (Join-Path $ROOT ".git"))) { Fail "Not a git repo: $ROOT" }

# ---- protect repo from junk/data ----
function Ensure-GitIgnore {
  $gi = Join-Path $ROOT ".gitignore"
  $rules = @(
    "SCALPING_DATA/",
    "SCALPING_DATA_PARQUET/",
    "SCALPING_DATA_RAW/",
    "cache/",
    "logs/",
    "results/",
    "parquet/",
    "__pycache__/",
    "*.parquet",
    "*.csv",
    "*.zip",
    "*.dmg"
  )
  if (!(Test-Path -LiteralPath $gi)) {
    ($rules -join "`r`n") | Out-File -LiteralPath $gi -Encoding UTF8
  } else {
    $existing = Get-Content -LiteralPath $gi -ErrorAction SilentlyContinue
    foreach($r in $rules){
      if($existing -notcontains $r){ Add-Content -LiteralPath $gi -Value $r }
    }
  }
}
Ensure-GitIgnore | Out-Null

# ---- heal git locks / stuck ops ----
function Heal-GitState {
  Remove-Item -LiteralPath (Join-Path $ROOT ".git\index.lock") -Force -ErrorAction SilentlyContinue
  if (Test-Path -LiteralPath (Join-Path $ROOT ".git\rebase-merge") -or Test-Path -LiteralPath (Join-Path $ROOT ".git\rebase-apply")) {
    try { git rebase --abort 2>$null | Out-Null } catch {}
  }
  if (Test-Path -LiteralPath (Join-Path $ROOT ".git\MERGE_HEAD")) {
    try { git merge --abort 2>$null | Out-Null } catch {}
  }
  if (Test-Path -LiteralPath (Join-Path $ROOT ".git\CHERRY_PICK_HEAD")) {
    try { git cherry-pick --abort 2>$null | Out-Null } catch {}
  }
}

# ---- keep only small/needed files in git (block big files) ----
function Drop-BigFilesFromIndex {
  param([int64]$MaxBytes = 50MB)
  $staged = @(git diff --cached --name-only)
  foreach($rel in $staged){
    if([string]::IsNullOrWhiteSpace($rel)){ continue }
    $p = Join-Path $ROOT $rel
    if(Test-Path -LiteralPath $p){
      try{
        $len = (Get-Item -LiteralPath $p -ErrorAction Stop).Length
        if($len -ge $MaxBytes){
          Warn ("Dropping big file from git (>50MB): " + $rel + " (" + $len + " bytes)")
          git reset -q -- $rel | Out-Null
          # add exact path to .gitignore so it won't come back
          $gi = Join-Path $ROOT ".gitignore"
          $existing = Get-Content -LiteralPath $gi -ErrorAction SilentlyContinue
          if($existing -notcontains $rel){ Add-Content -LiteralPath $gi -Value $rel }
        }
      } catch {}
    }
  }
}

# ---- sync routine: add -> commit -> rebase -> push -> verify ----
function Sync-Now {
  Heal-GitState

  # ensure main
  try { git checkout main 2>$null | Out-Null } catch {}

  $porc = @(git status --porcelain)
  if($porc.Count -eq 0){ return }

  # stage
  git add -A | Out-Null
  Drop-BigFilesFromIndex -MaxBytes 50MB

  # if nothing staged after dropping big files, stop
  $still = @(git diff --cached --name-only)
  if($still.Count -eq 0){ return }

  # commit
  $msg = "auto: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
  git commit -m $msg | Out-Null

  # rebase onto origin/main to avoid rejects
  git fetch --prune origin | Out-Null
  try {
    git rebase origin/main | Out-Null
  } catch {
    Warn "Rebase failed. Aborting rebase and stopping autosync to avoid corrupt state."
    try { git rebase --abort 2>$null | Out-Null } catch {}
    Fail "AUTOSYNC STOPPED: rebase conflict"
  }

  # push
  git push origin main | Out-Null

  # verify mirror
  $local  = (git rev-parse HEAD).Trim()
  $remote = (git rev-parse origin/main).Trim()
  if($local -ne $remote){ Fail "Mirror mismatch: HEAD != origin/main" }

  Ok ("PUSH OK | HEAD == origin/main | " + $msg)
}

# ---- watcher with debounce ----
$excludeTop = @(".git","SCALPING_DATA","SCALPING_DATA_PARQUET","SCALPING_DATA_RAW","cache","logs","results","parquet","_BACKUPS","_LOCAL_ONLY")
function Is-ExcludedPath($full){
  $rel = $full.Substring($ROOT.Length).TrimStart("\","/")
  if([string]::IsNullOrWhiteSpace($rel)){ return $false }
  $top = ($rel -split "[/\\]")[0]
  return ($excludeTop -contains $top)
}

$pending = $false
$lastEvt = Get-Date

$fsw = New-Object System.IO.FileSystemWatcher
$fsw.Path = $ROOT
$fsw.IncludeSubdirectories = $true
$fsw.NotifyFilter = [IO.NotifyFilters]'FileName, DirectoryName, LastWrite, Size'
$fsw.EnableRaisingEvents = $true

$action = {
  try {
    $p = $Event.SourceEventArgs.FullPath
    if($p -and (-not (Is-ExcludedPath $p))){
      $script:pending = $true
      $script:lastEvt = Get-Date
    }
  } catch {}
}

Register-ObjectEvent -InputObject $fsw -EventName Created -Action $action | Out-Null
Register-ObjectEvent -InputObject $fsw -EventName Changed -Action $action | Out-Null
Register-ObjectEvent -InputObject $fsw -EventName Renamed -Action $action | Out-Null
Register-ObjectEvent -InputObject $fsw -EventName Deleted -Action $action | Out-Null

"[$(Get-Date -Format s)] AUTOSYNC STARTED: $ROOT" | Add-Content -LiteralPath $LOG
Info "AUTOSYNC RUNNING (Ctrl+C to stop). Root: $ROOT"

while($true){
  Start-Sleep -Seconds 2
  if($pending){
    $age = (New-TimeSpan -Start $lastEvt -End (Get-Date)).TotalSeconds
    if($age -ge 3){
      $pending = $false
      try{
        Sync-Now
        "[$(Get-Date -Format s)] PUSH OK" | Add-Content -LiteralPath $LOG
      } catch {
        "[$(Get-Date -Format s)] ERROR: $($_.Exception.Message)" | Add-Content -LiteralPath $LOG
        throw
      }
    }
  }
}
