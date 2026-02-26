param([int]$MaxLogTail=3000)
Set-StrictMode -Off
$ErrorActionPreference="Stop"
$ROOT = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
$DESKTOP = [Environment]::GetFolderPath("Desktop")
$TS = (Get-Date).ToString("yyyyMMdd_HHmmss")
$OUT = Join-Path $DESKTOP ("FRANKEN_DOCTOR_" + $TS)
New-Item -ItemType Directory -Path $OUT -Force | Out-Null

function W([string]$p,[string]$t){ $enc=New-Object System.Text.UTF8Encoding($false); [IO.File]::WriteAllText($p,$t,$enc) }

$rep = New-Object System.Collections.Generic.List[string]
$rep.Add("ROOT=$ROOT")
$rep.Add("PS=$($PSVersionTable.PSVersion)")
$rep.Add("")

$py = Join-Path $ROOT ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $py)) { $py="python" }
$rep.Add("PY=$py")
try { $rep.Add((& $py -V 2>&1 | Out-String).Trim()) } catch {}

W (Join-Path $OUT "doctor_report.txt") ($rep -join "`r`n")

# pack essentials
$art = Join-Path $OUT "artifacts"
New-Item -ItemType Directory -Path $art -Force | Out-Null
$take = @("factory_master_247.py","factory_ga.py","ga_run.py","backtest_runner_v3.py","ga_adapters\runner_bridge.py","configs\factory_config.json","configs\default_config.json","configs\ga_config.json","configs\ga_config_v2.json","results\heartbeat_global.json")
foreach($r in $take){
  $p=Join-Path $ROOT $r
  if(Test-Path -LiteralPath $p){ Copy-Item -LiteralPath $p -Destination (Join-Path $art (($r -replace "[:\\\/]","_"))) -Force -ErrorAction SilentlyContinue }
}

# tail logs if exist
$logs = Get-ChildItem -LiteralPath $ROOT -Recurse -Force -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '\.log$|\.txt$' -and $_.Length -lt 50MB } |
  Sort-Object LastWriteTime -Descending | Select-Object -First 80
$err = New-Object System.Collections.Generic.List[string]
$pat="Traceback","ERROR","Exception","FAILED","SyntaxError","ImportError","ModuleNotFoundError","JSONDecodeError","KeyError","TypeError","UnicodeEncodeError"
foreach($f in $logs){
  $tail = Get-Content -LiteralPath $f.FullName -Tail $MaxLogTail -ErrorAction SilentlyContinue
  foreach($ln in $tail){
    foreach($k in $pat){ if($ln -like "*$k*"){ $err.Add("--- $($f.FullName)"); $err.Add($ln); break } }
  }
}
W (Join-Path $OUT "errors_keywords.txt") ($err -join "`r`n")

# zip
$zip = Join-Path $DESKTOP ("FRANKEN_DOCTOR_" + $TS + ".zip")
Add-Type -AssemblyName System.IO.Compression.FileSystem
if(Test-Path $zip){ Remove-Item $zip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($OUT,$zip)
Write-Host "[DOCTOR] ZIP: $zip" -ForegroundColor Cyan