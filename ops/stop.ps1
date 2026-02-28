$ErrorActionPreference='SilentlyContinue'
$ROOT='C:\Users\user\Desktop\Франкинштэйн'
$OpsDir=Join-Path $ROOT 'ops'
$Stop=Join-Path $OpsDir 'STOP_FACTORY'
$Pid=Join-Path $OpsDir 'factory_247_launcher.pid'

# create stop file
type nul > $Stop

# kill launcher if pid known
if(Test-Path $Pid){
  $lp = (Get-Content $Pid | Select-Object -First 1)
  if($lp -match '^\d+$'){
    $proc = Get-Process -Id ([int]$lp) -ErrorAction SilentlyContinue
    if($proc){ Stop-Process -Id $proc.Id -Force }
  }
}
Write-Host "STOP requested. File created: $Stop" -ForegroundColor Yellow
