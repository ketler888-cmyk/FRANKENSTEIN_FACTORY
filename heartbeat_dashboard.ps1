<#
Backtest Heartbeat Dashboard (PowerShell 5.1)
Reads heartbeat_global.json and all heartbeat_{PAIR}.json files from results folder.
Tolerates atomic JSON replace (os.replace): uses -Raw reads and ignores transient parse errors.
#>

param(
  [string]$ResultsDir = ".\results",
  [int]$RefreshSeconds = 2
)

function Read-JsonSafe([string]$FilePath) {
  try {
    if (!(Test-Path -LiteralPath $FilePath)) { return $null }
    $txt = Get-Content -LiteralPath $FilePath -Raw -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($txt)) { return $null }
    return ($txt | ConvertFrom-Json -ErrorAction Stop)
  } catch {
    return $null
  }
}

function Fmt-Dur([double]$sec) {
  if ($sec -lt 60) { return ("{0:N1}s" -f $sec) }
  if ($sec -lt 3600) {
    $m = [math]::Floor($sec / 60)
    $s = [math]::Floor($sec % 60)
    return ("{0}m {1}s" -f $m, $s)
  }
  $h = [math]::Floor($sec / 3600)
  $m2 = [math]::Floor(($sec % 3600) / 60)
  return ("{0}h {1}m" -f $h, $m2)
}

function Age-SecondsUtc([string]$iso) {
  try {
    if ([string]::IsNullOrWhiteSpace($iso)) { return 1e9 }
    $dt = [DateTime]::Parse($iso, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AdjustToUniversal)
    return ([DateTime]::UtcNow - $dt).TotalSeconds
  } catch {
    return 1e9
  }
}

while ($true) {
  Clear-Host
  $now = Get-Date
  Write-Host ("NOW: {0:yyyy-MM-dd HH:mm:ss}" -f $now)
  Write-Host ("ResultsDir: {0}" -f $ResultsDir)
  Write-Host ("Refresh: {0}s" -f $RefreshSeconds)
  Write-Host ""

  $globalPath = Join-Path $ResultsDir "heartbeat_global.json"
  $g = Read-JsonSafe $globalPath

  Write-Host "=== GLOBAL ==="
  if ($null -eq $g) {
    Write-Host "No global heartbeat (yet) or JSON unreadable."
  } else {
    $age = Age-SecondsUtc ([string]$g.last_update_iso)
    Write-Host ("phase: {0}" -f $g.phase)
    Write-Host ("current_pair: {0}" -f $g.current_pair)
    Write-Host ("elapsed: {0}" -f (Fmt-Dur ([double]$g.elapsed_seconds)))
    Write-Host ("last_update_iso: {0}" -f $g.last_update_iso)
    if ($age -gt ($RefreshSeconds * 3)) { Write-Host ("WARNING: stale ({0:N1}s old)" -f $age) }

    if ($g.phase -eq "optimize") {
      Write-Host ("opt: {0}/{1} valid:{2}" -f $g.opt_tested, $g.opt_total, $g.opt_valid_count)
      Write-Host ("cps: {0}  eta: {1}s" -f $g.opt_combos_per_sec, $g.opt_eta_seconds)
      Write-Host ("best_score: {0}" -f $g.opt_best_score)
    }
    if ($g.phase -in @("train","test","train_opt")) {
      Write-Host ("bars: {0}/{1} ({2}%)" -f $g.bar_i, $g.bars_total, $g.completion_percent)
      Write-Host ("equity: {0}  open: {1}  trades: {2}  bars_in_trade: {3}" -f $g.equity, $g.open_position, $g.trades_count, $g.bars_in_trade)
    }

    if ([int]$g.errors_count -gt 0) {
      Write-Host ("errors_count: {0}" -f $g.errors_count)
      Write-Host ("last_error: {0}" -f $g.last_error)
    }
  }

  Write-Host ""
  Write-Host "=== PAIRS ==="
  if (!(Test-Path -LiteralPath $ResultsDir)) {
    Write-Host "Results directory not found."
    Start-Sleep -Seconds $RefreshSeconds
    continue
  }

  $pairFiles = Get-ChildItem -LiteralPath $ResultsDir -Filter "heartbeat_*.json" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne "heartbeat_global.json" } |
    Sort-Object Name

  if ($pairFiles.Count -eq 0) {
    Write-Host "No pair heartbeat files (yet)."
  } else {
    foreach ($f in $pairFiles) {
      $o = Read-JsonSafe $f.FullName
      $pairName = ($f.BaseName -replace '^heartbeat_', '')
      Write-Host ""
      Write-Host ("-- {0} --" -f $pairName)
      if ($null -eq $o) {
        Write-Host "unreadable JSON (mid-replace) or empty."
        continue
      }
      $age = Age-SecondsUtc ([string]$o.last_update_iso)
      Write-Host ("phase: {0}" -f $o.phase)
      Write-Host ("elapsed: {0}" -f (Fmt-Dur ([double]$o.elapsed_seconds)))
      Write-Host ("last_update_iso: {0}" -f $o.last_update_iso)
      if ($age -gt ($RefreshSeconds * 3)) { Write-Host ("WARNING: stale ({0:N1}s old)" -f $age) }

      if ($o.phase -eq "optimize") {
        Write-Host ("opt: {0}/{1} valid:{2}" -f $o.opt_tested, $o.opt_total, $o.opt_valid_count)
        Write-Host ("cps: {0}  eta: {1}s" -f $o.opt_combos_per_sec, $o.opt_eta_seconds)
        Write-Host ("best_score: {0}" -f $o.opt_best_score)
      } elseif ($o.phase -in @("train","test","train_opt")) {
        Write-Host ("bars: {0}/{1} ({2}%)" -f $o.bar_i, $o.bars_total, $o.completion_percent)
        Write-Host ("equity: {0}  open: {1}  trades: {2}  bars_in_trade: {3}" -f $o.equity, $o.open_position, $o.trades_count, $o.bars_in_trade)
      } elseif ($o.phase -eq "error") {
        Write-Host ("last_error: {0}" -f $o.last_error)
      }

      if ([int]$o.errors_count -gt 0) { Write-Host ("errors_count: {0}" -f $o.errors_count) }
    }
  }

  Start-Sleep -Seconds $RefreshSeconds
}
