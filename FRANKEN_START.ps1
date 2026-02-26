Set-StrictMode -Off
$ErrorActionPreference = "Stop"

$Desktop = [Environment]::GetFolderPath("Desktop")
$Root = Join-Path $Desktop "Франкинштэйн"
$Log  = Join-Path $Desktop ("FRANKEN_START_LASTLOG_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".txt")

try {
  "=== FRANKEN START ===" | Out-File -Encoding UTF8 $Log
  ("Root=" + $Root) | Add-Content -Encoding UTF8 $Log

  if (!(Test-Path $Root)) { throw "No project root: " + $Root }
  Set-Location $Root
  ("PWD=" + (Get-Location)) | Add-Content -Encoding UTF8 $Log

  . (Join-Path $Root "franken_run.ps1")
}
catch {
  ("ERROR: " + $_.Exception.Message) | Add-Content -Encoding UTF8 $Log
  Write-Host "[FAIL] Startup error. Log on Desktop:" -ForegroundColor Red
  Write-Host $Log -ForegroundColor Yellow
  Write-Host ""
  Write-Host "Press ENTER to close..." -ForegroundColor Cyan
  [void](Read-Host)
}
