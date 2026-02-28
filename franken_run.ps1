Set-StrictMode -Off
$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Host "[FAIL] $m" -ForegroundColor Red; throw $m }

$Root = "C:\Users\user\Desktop\Франкинштэйн"
if (!(Test-Path -LiteralPath $Root)) { Fail "Нет папки проекта: $Root" }
Set-Location -LiteralPath $Root

function Get-AvailablePairsPS {
  param([string]$RootDir)

  $pairs = @()

  # 1) configs/factory_config.json has priority
  $cfg = Join-Path $RootDir "configs\factory_config.json"
  if (Test-Path -LiteralPath $cfg) {
    try {
      $j = Get-Content -LiteralPath $cfg -Raw | ConvertFrom-Json
      if ($j -and $j.pairs) {
        foreach($p in $j.pairs){
          $s = [string]$p
          if (![string]::IsNullOrWhiteSpace($s)) {
            $s = $s.Trim().ToUpper().Replace("/","").Replace("-","").Replace("_","")
            $pairs += $s
          }
        }
      }
    } catch {}
  }

  # 2) fallback: scan datasets
  foreach($dirName in @("SCALPING_DATA_PARQUET","SCALPING_DATA_RAW","SCALPING_DATA")) {
    $d = Join-Path $RootDir $dirName
    if (Test-Path -LiteralPath $d) {
      $pairs += Get-ChildItem -LiteralPath $d -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "_1m\.(csv|parquet)$" } |
        ForEach-Object { (.BaseName -replace "_1m$","").ToUpper().Replace("/","").Replace("-","").Replace("_","") }
    }
  }

  $pairs = $pairs | Where-Object { $_ } | Sort-Object -Unique
  return ,$pairs
}

# Python: prefer .venv
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $Py)) { $Py = "python" }

# Important scripts
$MainGA = Join-Path $Root "factory_ga.py"
if (!(Test-Path -LiteralPath $MainGA)) { Fail "Нет файла: $MainGA" }

$pairs = Get-AvailablePairsPS -RootDir $Root | Select-Object -First 5
if (! -or $pairs.Count -eq 0) { Fail "Не найдено ни одной пары (нет данных и/или не задано в configs/factory_config.json)" }

# Build indicator cache first (fast-mode bars optional via env)
$maxBars = 0
try { $maxBars = [int]() } catch { $maxBars = 0 }
Info ("Building indicator cache for pairs: " + ($pairs -join ", "))
foreach($p in $pairs){
  & $Py (Join-Path $Root "indicator_cache.py") --pair $p --force --max_bars $maxBars
}

# Optional heartbeat dashboard (reads results\heartbeat_*.json)
$Dash = Join-Path $Root "heartbeat_dashboard.ps1"
if (Test-Path -LiteralPath $Dash) {
  Start-Process powershell.exe -ArgumentList @("-NoExit","-ExecutionPolicy","Bypass","-File",$Dash,"-ResultsDir", (Join-Path $Root "results"), "-RefreshSeconds", "2") | Out-Null
  Info "Heartbeat dashboard started."
}

# Spawn per-pair factory_ga workers
$RunDir = Join-Path $Root "results_ga\_run"
New-Item -ItemType Directory -Path $RunDir -Force | Out-Null

$notional    = 50
$tphMin      = 5
$tphMax      = 100
$bars        = 120000
$population  = 64
$timeoutSec  = 1800

$procs = @{}
foreach($pair in $pairs){
  $out = Join-Path $RunDir ("stdout_{0}.log" -f $pair)
  $err = Join-Path $RunDir ("stderr_{0}.log" -f $pair)
  $pidf = Join-Path $RunDir ("{0}.pid" -f $pair)

  foreach($f in @($out,$err,$pidf)){
    if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue }
  }

  $args = @(
    $MainGA,
    "--pair", $pair,
    "--notional", $notional,
    "--tph_min", $tphMin,
    "--tph_max", $tphMax,
    "--bars", $bars,
    "--population", $population,
    "--timeout_sec", $timeoutSec
  )

  $p = Start-Process -FilePath $Py -ArgumentList $args -WorkingDirectory $Root -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  $p.Id | Out-File -Encoding ASCII -LiteralPath $pidf
  $procs[$pair] = [pscustomobject]@{ Proc=$p; Out=$out; Err=$err; Pid=$p.Id }
  Info ("STARTED {0} pid={1}" -f $pair, $p.Id)
}

Info "RUNNING. Ctrl+C stops all workers."
$stopping = $false
$handler = [ConsoleCancelEventHandler]{
  param($sender, $e)
  $e.Cancel = $true
  $script:stopping = $true
}
[Console]::add_CancelKeyPress($handler)

function Tail-File($path, $lines=80){
  if (!(Test-Path -LiteralPath $path)) { return @("[no file] $path") }
  try {
    $all = Get-Content -LiteralPath $path -ErrorAction Stop
    if ($all.Count -le $lines) { return $all }
    return $all[($all.Count-$lines)..($all.Count-1)]
  } catch {
    return @("[tail failed] $path : $(.Exception.Message)")
  }
}

try {
  while(-not $stopping){
    Start-Sleep -Seconds 1
    $alive = $false

    foreach($pair in $pairs){
      $x = $procs[$pair]
      if ($null -eq $x) { continue }
      try {
        if ($x.Proc -and -not $x.Proc.HasExited) { $alive = $true }
        elseif ($x.Proc -and $x.Proc.HasExited -and -not $x.Printed){
          $procs[$pair] | Add-Member -NotePropertyName Printed -NotePropertyValue $true -Force
          Write-Host ""
          Write-Host ("[CRASH] {0} pid={1} exit={2}" -f $pair, $x.Pid, $x.Proc.ExitCode) -ForegroundColor Red
          Write-Host "---- stderr tail ----" -ForegroundColor Yellow
          (Tail-File $x.Err 80) | ForEach-Object { Write-Host $_ }
          Write-Host "---- stdout tail ----" -ForegroundColor Yellow
          (Tail-File $x.Out 40) | ForEach-Object { Write-Host $_ }
          Write-Host ""
        }
      } catch {}
    }

    if (-not $alive){ Info "All workers exited."; break }
  }
}
finally {
  Info "STOPPING ALL..."
  foreach($pair in $pairs){
    $x = $procs[$pair]
    if ($null -eq $x) { continue }
    try {
      if ($x.Proc -and -not $x.Proc.HasExited){
        Stop-Process -Id $x.Pid -Force -ErrorAction SilentlyContinue
        Info ("STOPPED {0} pid={1}" -f $pair, $x.Pid)
      }
    } catch {}
  }
  try { [Console]::remove_CancelKeyPress($handler) } catch {}
  Info "DONE."
}