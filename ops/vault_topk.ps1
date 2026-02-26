param([int]$TopK=50)
Set-StrictMode -Off
$ErrorActionPreference="Stop"
$ROOT = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
$cfg = Join-Path $ROOT "configs\factory_config.json"
try { $j = Get-Content -LiteralPath $cfg -Raw | ConvertFrom-Json } catch { $j = $null }
try { if($j -and $j.storage -and $j.storage.keep_top_configs_per_pair){ $TopK = [int]$j.storage.keep_top_configs_per_pair } } catch {}

$rg = Join-Path $ROOT "results_ga"
$vault = Join-Path $ROOT "results_ga\vault_top"
New-Item -ItemType Directory -Path $vault -Force | Out-Null
if(!(Test-Path -LiteralPath $rg)){ Write-Host "[VAULT] results_ga missing"; exit 0 }

function NormPair([string]$s){
  if(-not $s){ return $s }
  return $s.Trim().ToUpper().Replace("/","").Replace("-","").Replace("_","")
}
function PickDouble($obj, $keys){
  foreach($k in $keys){
    try { $v = $obj.$k; if($null -ne $v -and $v -ne ""){ return [double]$v } } catch {}
  }
  return $null
}

$reports = Get-ChildItem -LiteralPath $rg -Recurse -Force -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -ieq "backtest_report.json" } |
  Sort-Object LastWriteTime -Descending

$items = New-Object System.Collections.Generic.List[object]
foreach($r in $reports){
  try {
    $raw = Get-Content -LiteralPath $r.FullName -Raw -ErrorAction Stop
    $jj = $raw | ConvertFrom-Json -ErrorAction Stop
    $pair = $null
    try { $pair = $jj.pair } catch {}
    try { if(-not $pair){ $pair = $jj.symbol } } catch {}
    if(-not $pair){
      $parts = $r.DirectoryName -split '[\\\/]'
      $guess = $parts | Where-Object { $_ -match '^[A-Z0-9]{3,}USDT$' } | Select-Object -Last 1
      $pair = $guess
    }
    $pair = NormPair $pair

    $pnl = PickDouble $jj @("pnl","net_pnl","profit_usdt","pnl_usdt","total_pnl","final_pnl","final_pnl_usdt","net_profit")
    if($null -eq $pnl -and $jj.summary){ $pnl = PickDouble $jj.summary @("pnl","net_pnl","profit_usdt","pnl_usdt","total_pnl","net_profit") }

    $items.Add([pscustomobject]@{ pair=$pair; pnl=$pnl; report=$r.FullName; lastWrite=$r.LastWriteTime })
  } catch {}
}

$byPair = $items | Group-Object pair
foreach($g in $byPair){
  $pair = $g.Name
  if(-not $pair){ $pair = "_NOPAIR" }
  $dst = Join-Path $vault $pair
  New-Item -ItemType Directory -Path $dst -Force | Out-Null

  $sorted = $g.Group | Where-Object { $null -ne $_.pnl } | Sort-Object pnl -Descending
  $top = $sorted | Select-Object -First $TopK

  foreach($x in $top){
    $src = $x.report
    $stamp = $x.lastWrite.ToString("yyyyMMdd_HHmmss")
    $out = Join-Path $dst ("backtest_report__" + $stamp + "__pnl_" + ($x.pnl) + ".json")
    try { Copy-Item -LiteralPath $src -Destination $out -Force -ErrorAction SilentlyContinue } catch {}
  }

  # trim vault to TopK
  $vv = Get-ChildItem -LiteralPath $dst -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
  if($vv.Count -gt $TopK){
    $old = $vv | Select-Object -Skip $TopK
    foreach($f in $old){ try { Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue } catch {} }
  }
  Write-Host ("[VAULT] {0}: kept {1}" -f $pair, $TopK)
}

Write-Host "[VAULT] done."