$ErrorActionPreference='SilentlyContinue'
function Log($m){ Add-Content -Path 'C:\Users\user\Desktop\Франкинштэйн\watchdog.log' -Value (('[{0}] {1}' -f (Get-Date).ToString('HH:mm:ss'), $m)) }

$RUN_ID = 16304
$PYTHON = 'C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe'
$RUNNER = 'C:\Users\user\Desktop\Франкинштэйн\backtest_runner_v3.py'
$PROJ   = 'C:\Users\user\Desktop\Франкинштэйн'
$CHECK  = 15
$STALL  = 60

function Restart-Run {
  Log "RESTART requested"
  try { Stop-Process -Id $RUN_ID -Force } catch {}
  Start-Sleep -Seconds 1

  $StdoutLog = Join-Path $PROJ 'stdout.log'
  $StderrLog = Join-Path $PROJ 'stderr.log'
  "" | Set-Content -Path $StdoutLog -Encoding UTF8
  "" | Set-Content -Path $StderrLog -Encoding UTF8

  $ResultsDir = Join-Path $PROJ 'results_ga'
  if (!(Test-Path $ResultsDir)) { New-Item -ItemType Directory -Path $ResultsDir | Out-Null }
  $ts = (Get-Date).ToString('yyyyMMdd_HHmmss')
  $OutJson = Join-Path $ResultsDir ("run_{0}.json" -f $ts)

  # дефолт (если не удалось вытащить из старого cmd)
  $pairs='BTCUSDT'; $equity=100; $train=0.7; $maxbars=50000; $mintr=50; $notional=50; $entry=1; $L=15; $K=0.1

  # пытаемся вытащить параметры из командной строки старого RUN (если CIM ещё отдаёт)
  try {
    $p = Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -eq $RUN_ID }
    if ($p -and $p.CommandLine) {
      function Grab([string]$name, $def){
        if ($p.CommandLine -match ("--{0}\s+([^\s""]+|""[^""]+"")" -f [regex]::Escape($name))) {
          $v = $Matches[1]
          if ($v.StartsWith('"') -and $v.EndsWith('"')) { $v = $v.Substring(1,$v.Length-2) }
          return $v
        }
        return $def
      }
      $pairs    = Grab 'pairs' $pairs
      $equity   = [double](Grab 'starting_equity' $equity)
      $train    = [double](Grab 'train_ratio' $train)
      $maxbars  = [int](Grab 'max_bars' $maxbars)
      $mintr    = [int](Grab 'min_trades' $mintr)
      $notional = [double](Grab 'notional_usdt' $notional)
      $entry    = [int](Grab 'entry_variant' $entry)
      $L        = [int](Grab 'breakout_lookback' $L)
      $K        = [double](Grab 'breakout_atr_k' $K)
    }
  } catch {}

  $Args = @(
    $RUNNER,
    '--pairs', $pairs,
    '--starting_equity', $equity,
    '--train_ratio', $train,
    '--max_bars', $maxbars,
    '--min_trades', $mintr,
    '--notional_usdt', $notional,
    '--entry_variant', $entry,
    '--breakout_lookback', $L,
    '--breakout_atr_k', $K,
    '--output', $OutJson
  )

  $WorkDir = Split-Path -Parent $RUNNER
  $np = Start-Process -FilePath $PYTHON -ArgumentList $Args -WorkingDirectory $WorkDir 
    -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -NoNewWindow -PassThru

  $RUN_ID = $np.Id
  Set-Content -Path (Join-Path $PROJ 'run.pid') -Value $RUN_ID -Encoding ASCII
  Log ("RESTARTED new RUN_ID=" + $RUN_ID)
}

Log ("WATCHDOG started for RUN_ID=" + $RUN_ID)

$lastCpu = 0.0
$lastMove = Get-Date

while ($true) {
  $gp = Get-Process -Id $RUN_ID -ErrorAction SilentlyContinue
  if (-not $gp) {
    Log "Process missing -> restart"
    Restart-Run
    Start-Sleep -Seconds $CHECK
    continue
  }

  $cpu = [double]$gp.CPU
  if ($cpu -gt $lastCpu) {
    $lastCpu = $cpu
    $lastMove = Get-Date
  }

  $stall = ((Get-Date) - $lastMove).TotalSeconds
  if ($stall -ge $STALL) {
    Log ("STALL detected (" + [int]$stall + "s) -> restart")
    Restart-Run
  }

  Start-Sleep -Seconds $CHECK
}
