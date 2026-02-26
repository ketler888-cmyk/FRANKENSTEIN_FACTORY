Set-StrictMode -Off
$ErrorActionPreference="Stop"
$ROOT = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
$cfg = Join-Path $ROOT "configs\factory_config.json"
$keepRuns = 6
$maxEvalGlobal = 120

try {
  $j = Get-Content -LiteralPath $cfg -Raw | ConvertFrom-Json
  if($j.storage.keep_latest_runs_per_pair){ $keepRuns = [int]$j.storage.keep_latest_runs_per_pair }
  if($j.storage.max_eval_dirs_per_pair){ $maxEvalGlobal = [int]$j.storage.max_eval_dirs_per_pair }
} catch {}

$rg = Join-Path $ROOT "results_ga"
if(!(Test-Path -LiteralPath $rg)){ Write-Host "[GC] results_ga missing"; exit 0 }

# 1) Trim eval/<PAIR>/<TS> to global cap (fast, no deep ROOT recursion)
$evalRoot = Join-Path $rg "eval"
if(Test-Path -LiteralPath $evalRoot){
  $evalDirs = Get-ChildItem -LiteralPath $evalRoot -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -Directory -ErrorAction SilentlyContinue } |
    Sort-Object LastWriteTime -Descending
  if($evalDirs.Count -gt $maxEvalGlobal){
    $old = $evalDirs | Select-Object -Skip $maxEvalGlobal
    foreach($d in $old){ try { Remove-Item -LiteralPath $d.FullName -Recurse -Force -ErrorAction SilentlyContinue; Write-Host "[GC] DEL_EVAL $($d.FullName)" } catch {} }
  }
}

# 2) Trim run_*/manual_run_* in results_ga root by count
$runs = Get-ChildItem -LiteralPath $rg -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -like "run_*" -or $_.Name -like "manual_run_*" } |
  Sort-Object LastWriteTime -Descending
$limit = [Math]::Max(20, $keepRuns * 10)  # conservative
if($runs.Count -gt $limit){
  $old = $runs | Select-Object -Skip $limit
  foreach($d in $old){ try { Remove-Item -LiteralPath $d.FullName -Recurse -Force -ErrorAction SilentlyContinue; Write-Host "[GC] DEL_RUN $($d.Name)" } catch {} }
}

# 3) Trim ga_eval_* only inside results_ga (not whole disk)
$gaEval = Get-ChildItem -LiteralPath $rg -Recurse -Force -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -like "ga_eval_*" } | Sort-Object LastWriteTime -Descending
if($gaEval.Count -gt $maxEvalGlobal){
  $old = $gaEval | Select-Object -Skip $maxEvalGlobal
  foreach($d in $old){ try { Remove-Item -LiteralPath $d.FullName -Recurse -Force -ErrorAction SilentlyContinue; Write-Host "[GC] DEL_GA_EVAL $($d.FullName)" } catch {} }
}

Write-Host "[GC] done."