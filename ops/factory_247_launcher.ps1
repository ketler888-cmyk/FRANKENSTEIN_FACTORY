$ErrorActionPreference = 'Stop'
$ROOT = 'C:\Users\user\Desktop\Франкинштэйн'
$PY = 'C:\Users\user\Desktop\Франкинштэйн\.venv\Scripts\python.exe'
$MODE = 'grid'
$PAIRS = 'BTCUSDT,ETHUSDT,ADAUSDT,SOLUSDT,AVAXUSDT'
$WORKERS = 4
$SCREEN_FRAC = 0.18
$SCREEN_KEEP = 60
$TOP_N_DB = 200

$OpsDir = Join-Path $ROOT 'ops'
$LogsDir = Join-Path $ROOT 'logs'
$StopFile = Join-Path $OpsDir 'STOP_FACTORY'
$Heartbeat = Join-Path $OpsDir 'heartbeat.json'
$PidFile = Join-Path $OpsDir 'factory_247.pid'
$RunLog = Join-Path $LogsDir 'factory_247_run.log'

if(!(Test-Path -LiteralPath $LogsDir)){ New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null }
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'

while($true){
  if(Test-Path -LiteralPath $StopFile){
    # mark stop in heartbeat (best effort)
    try{
      '{""ok"":true,""state"":""STOP_FILE_DETECTED"",""ts"":""' + (Get-Date).ToString('s') + '""}' |
        Set-Content -LiteralPath $Heartbeat -Encoding UTF8
    } catch {}
    exit 0
  }

  try{
    Add-Content -LiteralPath $RunLog -Encoding UTF8 -Value ("
[" + (Get-Date).ToString('s') + "] START factory_247.py mode=$MODE pairs=$PAIRS")
    & $PY (Join-Path $ROOT 'ops\factory_247.py') 
      --mode $MODE 
      --pairs $PAIRS 
      --workers $WORKERS 
      --screen_frac $SCREEN_FRAC 
      --screen_keep $SCREEN_KEEP 
      --top_n_db $TOP_N_DB 
      | Out-Null

    Add-Content -LiteralPath $RunLog -Encoding UTF8 -Value ("[" + (Get-Date).ToString('s') + "] EXIT normal")
    Start-Sleep -Seconds 3
  } catch {
    Add-Content -LiteralPath $RunLog -Encoding UTF8 -Value ("[" + (Get-Date).ToString('s') + "] CRASH: " + $_)
    Start-Sleep -Seconds 10
  }
}
