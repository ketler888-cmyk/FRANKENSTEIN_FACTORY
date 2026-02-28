$ErrorActionPreference='SilentlyContinue'
$ROOT='C:\Users\user\Desktop\Франкинштэйн'
$OpsDir=Join-Path $ROOT 'ops'
$LogsDir=Join-Path $ROOT 'logs'
$Hb=Join-Path $OpsDir 'heartbeat.json'
$Pid=Join-Path $OpsDir 'factory_247_launcher.pid'
$RunLog=Join-Path $LogsDir 'factory_247_run.log'
$Db=Join-Path $ROOT 'results_ga\pyramid.duckdb'

Write-Host "=== FRANKEN STATUS ===" -ForegroundColor Cyan
Write-Host ("root: " + $ROOT)
if(Test-Path $Pid){
  $lines = Get-Content $Pid -ErrorAction SilentlyContinue
  $lp = ($lines | Select-Object -First 1)
  if($lp -match '^\d+$'){
    $proc = Get-Process -Id ([int]$lp) -ErrorAction SilentlyContinue
    if($proc){ Write-Host ("launcher pid: " + $lp + " (RUNNING)") -ForegroundColor Green } else { Write-Host ("launcher pid: " + $lp + " (NOT RUNNING)") -ForegroundColor Yellow }
  }
}
if(Test-Path $Hb){
  Write-Host "
--- heartbeat.json ---" -ForegroundColor Cyan
  Get-Content $Hb -ErrorAction SilentlyContinue | Select-Object -First 200
}else{
  Write-Host "heartbeat.json missing" -ForegroundColor Yellow
}
if(Test-Path $RunLog){
  Write-Host "
--- tail run log (last 60) ---" -ForegroundColor Cyan
  Get-Content $RunLog -ErrorAction SilentlyContinue | Select-Object -Last 60
}else{
  Write-Host "run log missing" -ForegroundColor Yellow
}
if(Test-Path $Db){
  $fi = Get-Item $Db
  Write-Host "
--- DB ---" -ForegroundColor Cyan
  Write-Host ("duckdb: " + $fi.FullName)
  Write-Host ("size: " + [Math]::Round(($fi.Length/1MB),2) + " MB")
}else{
  Write-Host "duckdb missing" -ForegroundColor Yellow
}
