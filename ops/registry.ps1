Set-StrictMode -Off
$ErrorActionPreference="Stop"
$ROOT = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
$DESKTOP = [Environment]::GetFolderPath("Desktop")
$TS = (Get-Date).ToString("yyyyMMdd_HHmmss")
$outDir = Join-Path $DESKTOP ("FRANKEN_REGISTRY_" + $TS)
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

function W([string]$p,[string]$t){ $enc=New-Object System.Text.UTF8Encoding($false); [IO.File]::WriteAllText($p,$t,$enc) }

function NormPair([string]$s){
  if(-not $s){ return $s }
  $s = $s.Trim().ToUpper()
  return $s.Replace("/","").Replace("-","").Replace("_","")
}

function PickDouble($obj, $keys){
  foreach($k in $keys){
    try {
      $v = $obj.$k
      if($null -ne $v -and $v -ne ""){ return [double]$v }
    } catch {}
  }
  return $null
}

function PickInt($obj, $keys){
  foreach($k in $keys){
    try {
      $v = $obj.$k
      if($null -ne $v -and $v -ne ""){ return [int]$v }
    } catch {}
  }
  return $null
}

$rg = Join-Path $ROOT "results_ga"
$rows = New-Object System.Collections.Generic.List[object]

if (Test-Path -LiteralPath $rg) {
  $reports = Get-ChildItem -LiteralPath $rg -Recurse -Force -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ieq "backtest_report.json" } |
    Sort-Object LastWriteTime -Descending

  foreach ($r in $reports) {
    try {
      $raw = Get-Content -LiteralPath $r.FullName -Raw -ErrorAction Stop
      $j = $raw | ConvertFrom-Json -ErrorAction Stop

      $pair = $null
      try { $pair = $j.pair } catch {}
      try { if(-not $pair){ $pair = $j.symbol } } catch {}
      try { if(-not $pair -and $j.meta -and $j.meta.pair){ $pair = $j.meta.pair } } catch {}

      if(-not $pair){
        # infer from path (take last folder that looks like *USDT)
        $parts = $r.DirectoryName -split '[\\\/]'
        $guess = $parts | Where-Object { $_ -match '^[A-Z0-9]{3,}USDT$' } | Select-Object -Last 1
        $pair = $guess
      }
      $pair = NormPair $pair

      $pnl = PickDouble $j @("pnl","pnl_total","net_pnl","profit_usdt","total_profit_usdt","pnl_usdt","net_profit","netProfit","final_pnl","final_pnl_usdt","total_pnl")
      if($null -eq $pnl -and $j.summary){
        $pnl = PickDouble $j.summary @("pnl","net_pnl","profit_usdt","pnl_usdt","total_pnl","net_profit")
      }

      $dd = PickDouble $j @("max_dd","max_drawdown","dd_max","maxDD","max_drawdown_pct","max_dd_pct")
      if($null -eq $dd -and $j.risk){
        $dd = PickDouble $j.risk @("max_dd","max_drawdown","max_drawdown_pct")
      }

      $tr = PickInt $j @("trades","n_trades","trade_count","trades_total","num_trades")
      if($null -eq $tr -and $j.summary){
        $tr = PickInt $j.summary @("trades","n_trades","trade_count","num_trades")
      }

      $rows.Add([pscustomobject]@{
        lastWrite=$r.LastWriteTime
        pair=$pair
        pnl=$pnl
        max_dd=$dd
        trades=$tr
        report=$r.FullName
      })
    } catch {}
  }
}

$csv = Join-Path $outDir "registry.csv"
$rows | Sort-Object lastWrite -Descending | Export-Csv -NoTypeInformation -Encoding UTF8 $csv

$txt = Join-Path $outDir "registry_summary.txt"
$top = $rows | Where-Object { $null -ne $_.pnl } | Sort-Object pnl -Descending | Select-Object -First 30
$lines = @()
$lines += "ROOT=$ROOT"
$lines += "ROWS=$($rows.Count)"
$lines += ""
$lines += "TOP by pnl:"
foreach($x in $top){
  $lines += ("{0}  pair={1} pnl={2} dd={3} trades={4}" -f $x.lastWrite, $x.pair, $x.pnl, $x.max_dd, $x.trades)
}
W $txt ($lines -join "`r`n")

# zip
$zip = Join-Path $DESKTOP ("FRANKEN_REGISTRY_" + $TS + ".zip")
Add-Type -AssemblyName System.IO.Compression.FileSystem
if(Test-Path $zip){ Remove-Item $zip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($outDir,$zip)
Write-Host "[REGISTRY] ZIP: $zip" -ForegroundColor Cyan