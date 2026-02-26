Set-StrictMode -Off
$ErrorActionPreference = "SilentlyContinue"

$Root = Join-Path $HOME "Desktop\Франкинштэйн"
$FactoryTop = Join-Path $Root "results_ga\factory_top"

function N2($obj, $flat, $nested){
  try { if ($null -ne $obj.$flat) { return [double]$obj.$flat } } catch {}
  try { if ($obj.metrics -and $null -ne $obj.metrics.$nested) { return [double]$obj.metrics.$nested } } catch {}
  return $null
}

function Load-Top3($pairDir){
  $top = Join-Path $pairDir "top_100.json"
  if (Test-Path $top){
    $j = (Get-Content $top -Raw) | ConvertFrom-Json
    if ($j -is [System.Collections.IEnumerable]) { return @($j | Select-Object -First 3) }
    return @($j)
  }
  $best = Get-ChildItem $pairDir -File -Filter "best_*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($best){
    $j = (Get-Content $best.FullName -Raw) | ConvertFrom-Json
    if ($j -is [System.Collections.IEnumerable]) { return @($j | Select-Object -First 3) }
    return @($j)
  }
  return @()
}

while($true){
  Clear-Host
  $rows = @()

  if (!(Test-Path $FactoryTop)){
    Write-Host "factory_top not found yet: $FactoryTop"
    Start-Sleep -Seconds 2
    continue
  }

  Get-ChildItem $FactoryTop -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $pair = $_.Name
    $rank = 0
    foreach($s in (Load-Top3 $_.FullName)){
      $rank++
      $rows += [pscustomobject]@{
        Pair    = $pair
        Rank    = $rank
        Net     = N2 $s "net" "net_after_fees"
        Fees    = N2 $s "fees" "fees"
        Fitness = N2 $s "fitness" "fitness"
        Trades  = N2 $s "trades" "trades"
        TPH     = N2 $s "tph" "tph"
        TPD     = N2 $s "tpd" "tpd"
        DD      = N2 $s "dd" "max_dd"
        Bars    = N2 $s "bars" "bars"
      }
    }
  }

  $rows | Sort-Object Pair,Rank | Format-Table -AutoSize Pair,Rank,Net,Fees,Fitness,Trades,TPH,TPD,DD,Bars
  Start-Sleep -Seconds 2
}
