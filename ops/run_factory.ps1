param(
  [int]$MaxMinutes = 60
)
Set-StrictMode -Off
$ErrorActionPreference="Stop"
$ROOT = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
$PY = Join-Path $ROOT ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $PY)) { $PY = "python" }

# Force UTF-8 everywhere (fixes UnicodeEncodeError on Cyrillic paths)
try { chcp 65001 > $null } catch {}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONLEGACYWINDOWSSTDIO = "0"

Set-Location $ROOT
Write-Host "[RUN] $PY .\factory_master_247.py" -ForegroundColor Cyan

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $PY
$psi.Arguments = ".\factory_master_247.py"
$psi.WorkingDirectory = $ROOT
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $false

$p = New-Object System.Diagnostics.Process
$p.StartInfo = $psi
$null = $p.Start()

$sw = [Diagnostics.Stopwatch]::StartNew()
$maxMs = [int64]($MaxMinutes * 60 * 1000)
while (-not $p.HasExited -and $sw.ElapsedMilliseconds -lt $maxMs) { Start-Sleep -Milliseconds 500 }
if (-not $p.HasExited) { try { $p.Kill() } catch {} }

Write-Host "[EXIT] HasExited=$($p.HasExited) Code=$($p.ExitCode) Elapsed=$([Math]::Round($sw.Elapsed.TotalSeconds,1))s" -ForegroundColor Yellow