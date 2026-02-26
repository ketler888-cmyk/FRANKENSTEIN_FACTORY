param(
  [Parameter(Mandatory=$true)]
  [string]$ProjectDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

function TryReadJson([string]$Path) {
  try {
    if (!(Test-Path -LiteralPath $Path)) { return $null }
    $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    if (!$raw) { return $null }
    return ($raw | ConvertFrom-Json -ErrorAction SilentlyContinue)
  } catch { return $null }
}

function GetNewestRun([string]$RgaDir) {
  try {
    if (!(Test-Path -LiteralPath $RgaDir)) { return $null }
    return (Get-ChildItem -LiteralPath $RgaDir -Directory -Filter "run_*" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1)
  } catch { return $null }
}

Write-Host "=== Frankenstein MONITOR (Ctrl+C to stop) ===" -ForegroundColor Cyan
Write-Host ("ProjectDir: {0}" -f $ProjectDir) -ForegroundColor DarkGray

$rga = Join-Path $ProjectDir "results_ga"
$hb  = Join-Path $ProjectDir "results\heartbeat_global.json"

Write-Host ("Watching:  {0}" -f $rga) -ForegroundColor DarkGray
Write-Host ("Heartbeat: {0}" -f $hb)  -ForegroundColor DarkGray

$lastHbTs = ""
$lastRunName = ""

while ($true) {
  $run = GetNewestRun $rga
  if ($run) {
    if ($run.Name -ne $lastRunName) {
      Write-Host ("`n[RGA] NEW run: {0}  (LastWrite {1})" -f $run.Name, $run.LastWriteTime.ToString("HH:mm:ss")) -ForegroundColor Green
      $lastRunName = $run.Name
    } else {
      Write-Host ("[RGA] run: {0}  (LastWrite {1})" -f $run.Name, $run.LastWriteTime.ToString("HH:mm:ss")) -ForegroundColor Gray
    }

    $p = Join-Path $run.FullName "params.json"
    $r = Join-Path $run.FullName "backtest_report.json"
    if (Test-Path -LiteralPath $p) { Write-Host "[RGA] params.json: OK" -ForegroundColor Gray } else { Write-Host "[RGA] params.json: missing" -ForegroundColor Yellow }
    if (Test-Path -LiteralPath $r) { Write-Host "[RGA] backtest_report.json: OK" -ForegroundColor Green } else { Write-Host "[RGA] backtest_report.json: not yet" -ForegroundColor Yellow }
  } else {
    Write-Host "[RGA] waiting run_* folder..." -ForegroundColor Yellow
  }

  $g = TryReadJson $hb
  if ($g -and $g.ts_iso) {
    if ($g.ts_iso -ne $lastHbTs) {
      $lastHbTs = $g.ts_iso
      $pct = 0
      try { $pct = [double]$g.completion_percent } catch { $pct = 0 }
      $bi = 0; $bt = 0; $el = 0
      try { $bi = [int]$g.bar_i } catch {}
      try { $bt = [int]$g.bars_total } catch {}
      try { $el = [int]$g.elapsed_seconds } catch {}
      Write-Host ("[HB] {0} phase={1} pid={2} {3:n2}% ({4}/{5}) elapsed={6}s" -f $g.ts_iso, $g.phase, $g.pid, $pct, $bi, $bt, $el) -ForegroundColor Cyan
    } else {
      Write-Host "[HB] (no new heartbeat yet)" -ForegroundColor DarkGray
    }
  } else {
    Write-Host "[HB] heartbeat_global not ready/partial" -ForegroundColor DarkGray
  }

  Start-Sleep -Seconds 2
}