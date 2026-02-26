param(
  [int]$StaleSeconds = 180,
  [int]$KillAfterSeconds = 420
)
Set-StrictMode -Off
$ErrorActionPreference="Stop"

$ROOT = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
$hb = Join-Path $ROOT "results\heartbeat_global.json"
$runPs = Join-Path $ROOT "ops\run_factory.ps1"

Write-Host "[WD] ROOT=$ROOT"
Write-Host "[WD] heartbeat=$hb"
Write-Host "[WD] runner=$runPs"

if (!(Test-Path -LiteralPath $hb)) { Write-Host "[WD] heartbeat missing"; exit 2 }
$fi = Get-Item -LiteralPath $hb -ErrorAction Stop
$age = (New-TimeSpan -Start $fi.LastWriteTime -End (Get-Date)).TotalSeconds
Write-Host ("[WD] heartbeat age: {0:N1}s" -f $age)

if ($age -gt $KillAfterSeconds) {
  Write-Host "[WD] STALE>KillAfterSeconds -> recommend KILL+RESTART" -ForegroundColor Yellow
  exit 3
}
if ($age -gt $StaleSeconds) {
  Write-Host "[WD] STALE -> recommend RESTART" -ForegroundColor Yellow
  exit 1
}
Write-Host "[WD] OK" -ForegroundColor Green
exit 0