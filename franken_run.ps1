function Get-AvailablePairsPS {
  param([string]$Root)
  $pairs = (Get-AvailablePairsPS -Root $ROOT) | Select-Object -First 5
  $parq = Join-Path $Root "SCALPING_DATA_PARQUET"
  $raw  = Join-Path $Root "SCALPING_DATA_RAW"
  $csvd = Join-Path $Root "SCALPING_DATA"

  if (Test-Path $parq) {
    $pairs += Get-ChildItem $parq -File -Filter "*_1m.parquet" -ErrorAction SilentlyContinue | ForEach-Object { $_.BaseName -replace "_1m$","" }
  }
  if (Test-Path $raw) {
    $pairs += Get-ChildItem $raw -File -Filter "*_1m.csv" -ErrorAction SilentlyContinue | ForEach-Object { $_.BaseName -replace "_1m$","" }
  }
  if ((-not $pairs) -and (Test-Path $csvd)) {
    $pairs += Get-ChildItem $csvd -File -Filter "*_1m.csv" -ErrorAction SilentlyContinue | ForEach-Object { $_.BaseName -replace "_1m$","" }
  }
  $pairs = $pairs | Where-Object { $_ } | Sort-Object -Unique
  return ,$pairs
}
Set-StrictMode -Off
$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Fail($m){ Write-Host "[FAIL] $m" -ForegroundColor Red; throw $m }

function Tail-File($path, $lines=80){
  if (!(Test-Path $path)) { return @("[no file] $path") }
  try {
    $all = Get-Content $path -ErrorAction Stop
    if ($all.Count -le $lines) { return $all }
    return $all[($all.Count-$lines)..($all.Count-1)]
  } catch {
    return @("[tail failed] $path : $($_.Exception.Message)")
  }
}

$Root = Join-Path $HOME "Desktop\Франкинштэйн"
$Py   = "python"
$Main = Join-Path $Root "factory_ga.py"
if (!(Test-Path $Root)) { Fail "Нет папки проекта: $Root" }
if (!(Test-Path $Main)) { Fail "Нет файла: $Main" }

Set-Location $Root

# SETTINGS
$pairs = (Get-AvailablePairsPS -Root $ROOT) | Select-Object -First 5
$notional    = 50
$tphMin      = 5
$tphMax      = 100
$bars        = 525600
$population  = 200
$generations = 0
$timeoutSec  = 60

# RUNDIR
$RunDir = Join-Path $Root "results_ga\_run"
New-Item -ItemType Directory -Path $RunDir -Force | Out-Null

# START MONITOR (second window)
$MonitorFile = Join-Path $Root "franken_monitor.ps1"
if (!(Test-Path $MonitorFile)) { Fail "Нет монитора: $MonitorFile" }
Start-Process powershell.exe -ArgumentList @("-NoExit","-ExecutionPolicy","Bypass","-File",$MonitorFile) | Out-Null
Info "Monitor started."

# START PAIRS (no new windows)
$procs = @{}
foreach($pair in $pairs){
  $out = Join-Path $RunDir ("stdout_{0}.log" -f $pair)
  $err = Join-Path $RunDir ("stderr_{0}.log" -f $pair)
  $pidf = Join-Path $RunDir ("{0}.pid" -f $pair)

  foreach($f in @($out,$err,$pidf)){
    if (Test-Path $f) { Remove-Item $f -Force -ErrorAction SilentlyContinue }
  }

  $args = @(
    $Main,
    "--pair", $pair,
    "--notional", $notional,
    "--tph_min", $tphMin,
    "--tph_max", $tphMax,
    "--bars", $bars,
    "--population", $population,
    "--generations", $generations,
    "--timeout_sec", $timeoutSec
  )

  $p = Start-Process -FilePath $Py -ArgumentList $args -WorkingDirectory $Root -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  $p.Id | Out-File -Encoding ASCII $pidf
  $procs[$pair] = [pscustomobject]@{ Proc=$p; Out=$out; Err=$err; Pid=$p.Id }
  Info ("STARTED {0} pid={1}" -f $pair, $p.Id)
}

Info "RUNNING. Ctrl+C here stops everything."
Info ("Logs: " + $RunDir)

# Ctrl+C handler
$stopping = $false
$handler = [ConsoleCancelEventHandler]{
  param($sender, $e)
  $e.Cancel = $true
  $script:stopping = $true
}
[Console]::add_CancelKeyPress($handler)

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

    if (-not $alive){ Info "All processes exited."; break }
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

