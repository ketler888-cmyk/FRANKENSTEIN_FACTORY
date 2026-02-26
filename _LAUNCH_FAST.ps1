Set-StrictMode -Off
$ErrorActionPreference = "Stop"

$Root = "C:\Users\user\Desktop\Франкинштэйн"
$Py   = (Get-Command python -ErrorAction Stop).Source

$StdOut = "C:\Users\user\Desktop\Франкинштэйн\stdout.log"
$StdErr = "C:\Users\user\Desktop\Франкинштэйн\stderr.log"
$PidPath = "C:\Users\user\Desktop\Франкинштэйн\run.pid"

# Clean logs each run
"" | Out-File -Encoding UTF8 -FilePath $StdOut
"" | Out-File -Encoding UTF8 -FilePath $StdErr
if (Test-Path $PidPath) { Remove-Item $PidPath -Force -ErrorAction SilentlyContinue }

# Args as ONE string (PS 5.1 safe)
$ArgStr = ".\backtest_runner.py --pairs BTCUSDT --notional_usdt 50 --tp_pct 0.004 --sl_pct 0.003 --starting_equity 100 --output .\results\_tmp_report.json"

Write-Host "[*] WorkingDir = $Root"
Write-Host "[*] python     = $Py"
Write-Host "[*] ArgStr     = $ArgStr"

$p = Start-Process -FilePath $Py -WorkingDirectory $Root -ArgumentList $ArgStr 
     -RedirectStandardOutput $StdOut -RedirectStandardError $StdErr -PassThru

$p.Id | Out-File -Encoding ASCII -FilePath $PidPath
Write-Host "[OK] Started PID=$($p.Id)"

# Priority + affinity (leave CPU0 free => mask 62)
try { $p.PriorityClass = "AboveNormal" } catch {}
try { $p.ProcessorAffinity = [IntPtr]62 } catch {}

Write-Host "[*] Priority=$($p.PriorityClass) AffinityMask=$([int64]$p.ProcessorAffinity)"
