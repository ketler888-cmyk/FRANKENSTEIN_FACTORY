$ErrorActionPreference='Stop'
$ROOT='C:\Users\user\Desktop\Франкинштэйн'
$PY='C:\Users\user\Desktop\Франкинштэйн\.venv\Scripts\python.exe'
$MODE='grid'
$PAIRS='BTCUSDT,ETHUSDT,ADAUSDT,SOLUSDT,AVAXUSDT'
$WORKERS=4
$SCREEN_FRAC=0.18
$SCREEN_KEEP=60
$TOP_N_DB=200

$OpsDir=Join-Path $ROOT 'ops'
$LogsDir=Join-Path $ROOT 'logs'
$StopFile=Join-Path $OpsDir 'STOP_FACTORY'
$Heartbeat=Join-Path $OpsDir 'heartbeat.json'
$RunLog=Join-Path $LogsDir 'factory_247_run.log'

if(!(Test-Path -LiteralPath $LogsDir)){ New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null }
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'

function HB([string]$state, [string]$note){
  try{
    ('{""ok"":true,""state"":""' + $state + '"",""ts"":""' + (Get-Date).ToString('s') + '"",""note"":' + (ConvertTo-Json $note -Compress) + '}') |
      Set-Content -LiteralPath $Heartbeat -Encoding UTF8
  } catch {}
}

while($true){
  if(Test-Path -LiteralPath $StopFile){ HB 'STOP_FILE_DETECTED' 'stopping'; exit 0 }

  try{
    Add-Content -LiteralPath $RunLog -Encoding UTF8 -Value ("
[" + (Get-Date).ToString('s') + "] START mode=$MODE pairs=$PAIRS w=$WORKERS screen=$SCREEN_FRAC keep=$SCREEN_KEEP top=$TOP_N_DB")
    HB 'STARTING' 'boot'
    & $PY (Join-Path $ROOT 'ops\factory_247.py') --mode $MODE --pairs $PAIRS --workers $WORKERS --screen_frac $SCREEN_FRAC --screen_keep $SCREEN_KEEP --top_n_db $TOP_N_DB | Out-Null
    Add-Content -LiteralPath $RunLog -Encoding UTF8 -Value ("[" + (Get-Date).ToString('s') + "] EXIT normal")
    HB 'EXIT_NORMAL' 'factory finished'
    Start-Sleep -Seconds 3
  } catch {
    Add-Content -LiteralPath $RunLog -Encoding UTF8 -Value ("[" + (Get-Date).ToString('s') + "] CRASH: " + $_)
    HB 'CRASH' ($_ | Out-String)
    Start-Sleep -Seconds 10
  }
}
