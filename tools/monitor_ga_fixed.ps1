#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$ProjectDir = "C:\Users\user\Desktop\Франкинштэйн"

function TryReadJson([string]$Path) {
  try {
    if (!(Test-Path -LiteralPath $Path)) { return $null }
    $t = Get-Content -LiteralPath $Path -Raw
    if ([string]::IsNullOrWhiteSpace($t)) { return $null }
    return ($t | ConvertFrom-Json)
  } catch { return $null }
}

function GetNewestRun([string]$Root) {
  try {
    $rga = Join-Path $Root "results_ga"
    if (!(Test-Path -LiteralPath $rga)) { return $null }
    return (Get-ChildItem -LiteralPath $rga -Directory -Filter "run_*" |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 1)
  } catch { return $null }
}

Write-Host "=== Frankenstein MONITOR (Ctrl+C to stop) ===" -ForegroundColor Cyan
Write-Host ("Project: {0}" -f $ProjectDir) -ForegroundColor DarkGray

$lastRunName = ""
$lastHbTs    = ""

while ($true) {

  # results_ga
  $run = GetNewestRun $ProjectDir
  if ($run) {
    if ($run.Name -ne $lastRunName) {
      Write-Host ("[RGA] NEW run: {0} (LastWrite {1})" -f $run.Name, $run.LastWriteTime.ToString("HH:mm:ss")) -ForegroundColor Green
      $lastRunName = $run.Name
    } else {
      Write-Host ("[RGA] run: {0} (LastWrite {1})" -f $run.Name, $run.LastWriteTime.ToString("HH:mm:ss")) -ForegroundColor Gray
    }

    $params = Join-Path $run.FullName "params.json"
    $rep    = Join-Path $run.FullName "backtest_report.json"
    if (Test-Path -LiteralPath $params) { Write-Host "[RGA] params.json: OK" -ForegroundColor DarkGray } else { Write-Host "[RGA] params.json: MISSING" -ForegroundColor Yellow }
    if (Test-Path -LiteralPath $rep)    { Write-Host "[RGA] backtest_report.json: FOUND" -ForegroundColor Green } else { Write-Host "[RGA] backtest_report.json: not yet" -ForegroundColor Yellow }
  } else {
    Write-Host "[RGA] waiting run_* folder..." -ForegroundColor Yellow
  }

  # heartbeat
  $hb = Join-Path $ProjectDir "results\heartbeat_global.json"
  $g  = TryReadJson $hb
  if ($g) {
    if ($g.ts_iso -ne $lastHbTs) {
      $lastHbTs = $g.ts_iso
      $pct = 0
      try { if ($g.bars_total -gt 0) { $pct = [math]::Round((100.0 * ($g.bar_i / $g.bars_total)), 2) } } catch {}
      Write-Host ("[HB] {0} phase={1} pid={2} {3}% ({4}/{5}) elapsed={6}s" -f $g.ts_iso, $g.phase, $g.pid, $pct, $g.bar_i, $g.bars_total, [int]$g.elapsed_seconds) -ForegroundColor DarkGray
    } else {
      Write-Host "[HB] (no new heartbeat yet)" -ForegroundColor DarkGray
    }
  } else {
    Write-Host "[HB] heartbeat_global not ready/partial" -ForegroundColor DarkGray
  }

  Start-Sleep -Seconds 2
}