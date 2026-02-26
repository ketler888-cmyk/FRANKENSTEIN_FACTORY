Set-StrictMode -Off
$ErrorActionPreference = "Stop"

param(
  [Parameter(Mandatory=$true)][string]$Root,
  [Parameter(Mandatory=$true)][string]$PairsCsv,
  [int]$TopN = 100,
  [int]$TopK = 3,
  [int]$KeepErrPerPair = 10,
  [int]$MonRefreshSec = 5
)

function WriteCrash([string]$title, [object]$err){
  try {
    $desk = [Environment]::GetFolderPath("Desktop")
    $stamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
    $fp = Join-Path $desk ("FRANKEN_CRASH_{0}.txt" -f $stamp)
    $msg = @()
    $msg += ("TITLE: " + $title)
    $msg += ("TIME : " + (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))
    $msg += ("ROOT : " + $Root)
    $msg += ("PAIRS: " + $PairsCsv)
    $msg += ("TopN : " + $TopN)
    $msg += ("TopK : " + $TopK)
    $msg += ("KeepErrPerPair: " + $KeepErrPerPair)
    $msg += ""
    $msg += "==== ERROR ===="
    $msg += ($err | Out-String)
    $msg += ""
    $msg += "==== STACK ===="
    try { $msg += ($err.ScriptStackTrace | Out-String) } catch {}
    try { $msg += ($global:Error[0] | Format-List * -Force | Out-String) } catch {}
    [System.IO.File]::WriteAllText($fp, ($msg -join "`r`n"), (New-Object System.Text.UTF8Encoding($false)))
    return $fp
  } catch { return $null }
}

function ResolvePython([string]$Root){
  $cand = Join-Path $Root ".venv\Scripts\python.exe"
  if(Test-Path -LiteralPath $cand){ return $cand }
  $cand2 = Join-Path $Root "venv\Scripts\python.exe"
  if(Test-Path -LiteralPath $cand2){ return $cand2 }
  try { $cmd = Get-Command python.exe -ErrorAction SilentlyContinue; if($cmd -and $cmd.Source){ return $cmd.Source } } catch {}
  try { $cmd2 = Get-Command py.exe -ErrorAction SilentlyContinue; if($cmd2 -and $cmd2.Source){ return $cmd2.Source } } catch {}
  return $null
}

try {
  if(!(Test-Path -LiteralPath $Root)){ throw "Root folder not found: $Root" }

  $Pairs = $PairsCsv.Split(",") | ForEach-Object { $_.Trim().ToUpper() } | Where-Object { $_ -match "^[A-Z0-9]+USDT$" }
  if($Pairs.Count -ne 5){ throw "Runner expects exactly 5 pairs. Got: $($Pairs -join ',')" }

  $env:FR_PAIRS = ($Pairs -join ",")

  $factory = Join-Path $Root "factory_ga.py"
  if(!(Test-Path -LiteralPath $factory)){ throw "factory_ga.py not found: $factory" }

  $py = ResolvePython $Root
  if([string]::IsNullOrWhiteSpace($py)){ throw "Python not found (.venv or system python/py)." }

  $usePyLauncher = $false
  if($py.ToLower().EndsWith("\py.exe")){ $usePyLauncher = $true }

  $procs = New-Object System.Collections.ArrayList
  foreach($p in $Pairs){
    if($usePyLauncher){
      $proc = Start-Process -FilePath $py -WorkingDirectory $Root -ArgumentList @("-3", $factory, "--pair", $p) -WindowStyle Hidden -PassThru
    } else {
      $proc = Start-Process -FilePath $py -WorkingDirectory $Root -ArgumentList @($factory, "--pair", $p) -WindowStyle Hidden -PassThru
    }
    [void]$procs.Add($proc)
    Write-Host ("[START] {0} pid={1}" -f $p, $proc.Id)
  }

  Write-Host "[RUNNING] Ctrl+C stops everything."

  $cancelHandler = [ConsoleCancelEventHandler]{
    param($sender,$e)
    $e.Cancel = $true
    foreach($pp in $procs){
      try { if($pp -and -not $pp.HasExited){ Stop-Process -Id $pp.Id -Force -ErrorAction SilentlyContinue } } catch {}
    }
    Write-Host "[STOPPED]"
    exit 0
  }
  [Console]::add_CancelKeyPress($cancelHandler)

  while($true){ Start-Sleep -Seconds 2 }

} catch {
  $fp = WriteCrash "franken_runner.ps1 crashed" $_
  if($fp){ Write-Host ("CRASH REPORT -> " + $fp) }
  try { Write-Host $_.Exception.Message } catch {}
  try { Write-Host "Press Enter to close..." ; [void](Read-Host) } catch {}
  exit 1
}