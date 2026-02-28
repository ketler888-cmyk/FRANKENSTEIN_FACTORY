param(
  [Parameter(Mandatory=$true)][ValidateSet("start","stop","status","tail")][string]$cmd,
  [string]$mode = "grid",
  [string]$pairs = "BTCUSDT,ETHUSDT,ADAUSDT,SOLUSDT,AVAXUSDT",
  [int]$workers = 4,
  [double]$screen_frac = 0.18,
  [int]$screen_keep = 60,
  [int]$top_n_db = 200
)

Set-StrictMode -Off
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ROOT = Split-Path -Parent $PSScriptRoot
$PY = Join-Path $ROOT ".venv\Scripts\python.exe"
$OpsDir = Join-Path $ROOT "ops"
$LogsDir = Join-Path $ROOT "logs"
$Launcher = Join-Path $OpsDir "factory_247_launcher.ps1"
$LauncherPid = Join-Path $OpsDir "factory_247_launcher.pid"
$StopFile = Join-Path $OpsDir "STOP_FACTORY"
$Heartbeat = Join-Path $OpsDir "heartbeat.json"
$RunLog = Join-Path $LogsDir "factory_247_run.log"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Ensure-Dir([string]$p){ if(-not(Test-Path -LiteralPath $p)){ New-Item -ItemType Directory -Path $p -Force | Out-Null } }

Ensure-Dir $OpsDir
Ensure-Dir $LogsDir

$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"

if($cmd -eq "stop"){
  # soft stop
  if(!(Test-Path -LiteralPath $StopFile)){ New-Item -ItemType File -Path $StopFile -Force | Out-Null }
  Ok "STOP file created: $StopFile"

  # hard stop launcher if pid exists (avoid $PID constant!)
  if(Test-Path -LiteralPath $LauncherPid){
    $launcherPidVal = (Get-Content -LiteralPath $LauncherPid -ErrorAction SilentlyContinue | Select-Object -First 1)
    if($launcherPidVal -match '^\d+$'){
      $pp = Get-Process -Id ([int]$launcherPidVal) -ErrorAction SilentlyContinue
      if($pp){ Stop-Process -Id $pp.Id -Force; Ok "Killed launcher pid=$launcherPidVal" }
    }
  }
  exit 0
}

if($cmd -eq "status"){
  if(Test-Path -LiteralPath $Heartbeat){
    Get-Content -LiteralPath $Heartbeat -Raw
  } else {
    Warn "No heartbeat yet: $Heartbeat"
  }
  exit 0
}

if($cmd -eq "tail"){
  if(Test-Path -LiteralPath $RunLog){
    Get-Content -LiteralPath $RunLog -Tail 120
  } else {
    Warn "No run log yet: $RunLog"
  }
  exit 0
}

if($cmd -eq "start"){
  if(Test-Path -LiteralPath $StopFile){ Remove-Item -LiteralPath $StopFile -Force }

  if(-not (Test-Path -LiteralPath $Launcher)){
    throw "Missing launcher: $Launcher (run the main setup block first)"
  }

  # start detached
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = (Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe")
  $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Launcher`""
  $psi.WorkingDirectory = $ROOT
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true

  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi
  [void]$p.Start()

  ("{0}`n{1}" -f $p.Id, (Get-Date).ToString("s")) | Set-Content -LiteralPath $LauncherPid -Encoding UTF8
  Ok ("STARTED launcher_pid=" + $p.Id)

  Info "Commands:"
  Write-Host ("  STATUS: powershell -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" status") -ForegroundColor Yellow
  Write-Host ("  TAIL:   powershell -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" tail") -ForegroundColor Yellow
  Write-Host ("  STOP:   powershell -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" stop") -ForegroundColor Yellow
  exit 0
}
