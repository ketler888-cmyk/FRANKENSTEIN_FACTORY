param(
  [int]$TopN = 30
)
Set-StrictMode -Off
$ErrorActionPreference="Stop"

function NowTs { (Get-Date).ToString("yyyyMMdd_HHmmss") }
function W([string]$p,[string]$t){
  $enc=New-Object System.Text.UTF8Encoding($false)
  $d=Split-Path -Parent $p
  if($d -and !(Test-Path -LiteralPath $d)){ New-Item -ItemType Directory -Path $d -Force | Out-Null }
  [IO.File]::WriteAllText($p,$t,$enc)
}
function Zip-Folder([string]$Folder, [string]$ZipPath) {
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
  [System.IO.Compression.ZipFile]::CreateFromDirectory($Folder, $ZipPath)
}
function TryJson([string]$path){
  try { return (Get-Content -LiteralPath $path -Raw | ConvertFrom-Json) } catch { return $null }
}
function PickDouble($obj, $keys){
  foreach($k in $keys){
    try { $v = $obj.$k; if($null -ne $v -and $v -ne ""){ return [double]$v } } catch {}
  }
  return $null
}
function PickInt($obj, $keys){
  foreach($k in $keys){
    try { $v = $obj.$k; if($null -ne $v -and $v -ne ""){ return [int]$v } } catch {}
  }
  return $null
}
function NormPair([string]$s){
  if(-not $s){ return $s }
  return $s.Trim().ToUpper().Replace("/","").Replace("-","").Replace("_","")
}

$ROOT = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
$DESKTOP = [Environment]::GetFolderPath("Desktop")
$TS = NowTs
$OUT = Join-Path $DESKTOP ("FRANKEN_FINAL_AUDIT_" + $TS)
New-Item -ItemType Directory -Path $OUT -Force | Out-Null

$report = New-Object System.Collections.Generic.List[string]
$report.Add("FRANKEN FINAL AUDIT")
$report.Add("TS=$TS")
$report.Add("ROOT=$ROOT")
$report.Add("")

# --- env / python ---
$py = $null
$venvPy = Join-Path $ROOT ".venv\Scripts\python.exe"
if(Test-Path -LiteralPath $venvPy){ $py = $venvPy }
if(-not $py){
  try { $py = (Get-Command python -ErrorAction Stop).Source } catch {}
}
if($py){ $report.Add("PY=" + $py) } else { $report.Add("PY=NOT_FOUND") }
$report.Add("PSVersion=" + $PSVersionTable.PSVersion.ToString())
$report.Add("")

# --- required files presence ---
$must = @(
  "factory_master_247.py","factory_ga.py","ga_run.py","backtest_runner_v3.py",
  "configs\factory_config.json"
)
$report.Add("FILES (required):")
foreach($m in $must){
  $p = Join-Path $ROOT $m
  $ok = Test-Path -LiteralPath $p
  if($ok){
    $report.Add(("OK  " + $m))
  } else {
    $report.Add(("MISS  " + $m))
  }
}
$report.Add("")

# --- configs sanity ---
$cfgDir = Join-Path $ROOT "configs"
$cfgs = @("factory_config.json","default_config.json","ga_config.json","ga_config_v2.json")
$report.Add("CONFIGS (json parse):")
foreach($c in $cfgs){
  $p = Join-Path $cfgDir $c
  if(Test-Path -LiteralPath $p){
    $j = TryJson $p
    if($j){ $report.Add(("OK  configs\" + $c)) } else { $report.Add(("BAD_JSON  configs\" + $c)) }
  } else {
    $report.Add(("MISS  configs\" + $c))
  }
}
$report.Add("")

# --- data presence quick scan ---
$parq = Join-Path $ROOT "SCALPING_DATA_PARQUET"
$raw  = Join-Path $ROOT "SCALPING_DATA_RAW"
$report.Add("DATA:")
$report.Add("SCALPING_DATA_PARQUET=" + (Test-Path -LiteralPath $parq))
$report.Add("SCALPING_DATA_RAW=" + (Test-Path -LiteralPath $raw))
try {
  if(Test-Path -LiteralPath $parq){
    $pq = Get-ChildItem -LiteralPath $parq -File -ErrorAction SilentlyContinue | Select-Object -First 20
    $report.Add("parquet_files_sample=" + ($pq.Count))
    foreach($f in $pq){ $report.Add("  " + $f.Name + " (" + [Math]::Round($f.Length/1MB,2) + " MB)") }
  }
} catch {}
$report.Add("")

# --- runtime signals ---
$hb = Join-Path $ROOT "results\heartbeat_global.json"
$prog = Join-Path $ROOT "results\progress.jsonl"
$report.Add("RUNTIME SIGNALS:")
$report.Add("heartbeat_exists=" + (Test-Path -LiteralPath $hb))
if(Test-Path -LiteralPath $hb){
  $fi = Get-Item -LiteralPath $hb -ErrorAction SilentlyContinue
  if($fi){
    $age = (New-TimeSpan -Start $fi.LastWriteTime -End (Get-Date)).TotalSeconds
    $report.Add(("heartbeat_lastwrite=" + $fi.LastWriteTime))
    $report.Add(("heartbeat_age_sec={0:N1}" -f $age))
  }
}
$report.Add("progress_exists=" + (Test-Path -LiteralPath $prog))
if(Test-Path -LiteralPath $prog){
  $fi2 = Get-Item -LiteralPath $prog -ErrorAction SilentlyContinue
  if($fi2){ $report.Add("progress_lastwrite=" + $fi2.LastWriteTime) }
}
$report.Add("")

# --- results_ga top reports ---
$rg = Join-Path $ROOT "results_ga"
$rows = New-Object System.Collections.Generic.List[object]
if(Test-Path -LiteralPath $rg){
  $reports = Get-ChildItem -LiteralPath $rg -Recurse -Force -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ieq "backtest_report.json" } |
    Sort-Object LastWriteTime -Descending

  foreach($r in $reports){
    try {
      $j = TryJson $r.FullName
      if(-not $j){ continue }

      $pair = $null
      try { $pair = $j.pair } catch {}
      try { if(-not $pair){ $pair = $j.symbol } } catch {}
      if(-not $pair){
        $parts = $r.DirectoryName -split '[\\\/]'
        $guess = $parts | Where-Object { $_ -match '^[A-Z0-9]{3,}USDT$' } | Select-Object -Last 1
        $pair = $guess
      }
      $pair = NormPair $pair

      $pnl = PickDouble $j @("pnl","net_pnl","profit_usdt","pnl_usdt","total_pnl","final_pnl","final_pnl_usdt","net_profit")
      if($null -eq $pnl -and $j.summary){ $pnl = PickDouble $j.summary @("pnl","net_pnl","profit_usdt","pnl_usdt","total_pnl","net_profit") }

      $dd = PickDouble $j @("max_dd","max_drawdown","max_drawdown_pct","max_dd_pct")
      if($null -eq $dd -and $j.risk){ $dd = PickDouble $j.risk @("max_dd","max_drawdown","max_drawdown_pct") }

      $tr = PickInt $j @("trades","n_trades","trade_count","num_trades")
      if($null -eq $tr -and $j.summary){ $tr = PickInt $j.summary @("trades","n_trades","trade_count","num_trades") }

      $rows.Add([pscustomobject]@{
        lastWrite=$r.LastWriteTime
        pair=$pair
        pnl=$pnl
        dd=$dd
        trades=$tr
        path=$r.FullName
      })
    } catch {}
  }
}

$report.Add("RESULTS_GA:")
$report.Add("reports_parsed=" + $rows.Count)
$report.Add("TOP by pnl:")
$top = $rows | Where-Object { $null -ne $_.pnl } | Sort-Object pnl -Descending | Select-Object -First $TopN
foreach($x in $top){
  $report.Add(("{0}  pair={1} pnl={2} dd={3} trades={4}" -f $x.lastWrite, $x.pair, $x.pnl, $x.dd, $x.trades))
}
$report.Add("")
$report.Add("NEWEST reports:")
$newest = $rows | Sort-Object lastWrite -Descending | Select-Object -First $TopN
foreach($x in $newest){
  $report.Add(("{0}  pair={1} pnl={2} trades={3}" -f $x.lastWrite, $x.pair, $x.pnl, $x.trades))
}

# write outputs
W (Join-Path $OUT "final_audit_report.txt") ($report -join "`r`n")
try { $rows | Sort-Object lastWrite -Descending | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $OUT "reports_index.csv") } catch {}

# copy tails
if(Test-Path -LiteralPath $hb){ Copy-Item -LiteralPath $hb -Destination (Join-Path $OUT "heartbeat_global.json") -Force -ErrorAction SilentlyContinue }
if(Test-Path -LiteralPath $prog){ Get-Content -LiteralPath $prog -Tail 4000 | Set-Content -LiteralPath (Join-Path $OUT "progress_tail.jsonl") -Encoding UTF8 }

# zip
$ZIP = Join-Path $DESKTOP ("FRANKEN_FINAL_AUDIT_" + $TS + ".zip")
Zip-Folder $OUT $ZIP
Write-Host ("[FINAL_AUDIT] ZIP: " + $ZIP)
Write-Host ("[FINAL_AUDIT] OUT: " + $OUT)