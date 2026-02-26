Set-StrictMode -Off
$ErrorActionPreference = "SilentlyContinue"

param(
  [Parameter(Mandatory=$true)][string]$Root,
  [Parameter(Mandatory=$true)][string[]]$Pairs,
  [int]$RefreshSec = 5
)

function ReadJson([string]$p){ try { Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $null } }

$results = Join-Path $Root "results_ga"
$indexDir = Join-Path $results "_index"

while($true){
  Clear-Host
  Write-Host ("FRANKEN TOP-3 MONITOR | " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
  Write-Host ("PAIRS: " + ($Pairs -join ","))
  Write-Host ("INDEX: " + $indexDir)
  Write-Host ""

  foreach($pair in $Pairs){
    $f = Join-Path $indexDir ("top3_{0}.json" -f $pair)
    Write-Host ("=== {0} ===" -f $pair)
    if(!(Test-Path -LiteralPath $f)){
      Write-Host "No top3 yet."
      Write-Host ""
      continue
    }
    $j = ReadJson $f
    if($null -eq $j){
      Write-Host "Failed to read json."
      Write-Host ""
      continue
    }
    $rows = @()
    foreach($r in $j){
      $rows += [PSCustomObject]@{
        Fitness   = [math]::Round([double]$r.fitness, 6)
        NetPnL    = [math]::Round([double]$r.net_pnl, 6)
        PnL_Day   = [math]::Round([double]$r.pnl_day, 6)
        PnL_Month = [math]::Round([double]$r.pnl_month, 6)
        Trades    = [int]$r.trades
        WinRate   = [math]::Round([double]$r.win_rate, 4)
        W         = [int]$r.win
        L         = [int]$r.loss
        AvgWin    = [math]::Round([double]$r.avg_win, 6)
        AvgLoss   = [math]::Round([double]$r.avg_loss, 6)
        Fees      = [math]::Round([double]$r.fees, 6)
        MaxDD     = [math]::Round([double]$r.max_dd, 6)
        TS        = [string]$r.ts
      }
    }
    $rows | Format-Table -AutoSize
    Write-Host ""
  }

  Start-Sleep -Seconds $RefreshSec
}