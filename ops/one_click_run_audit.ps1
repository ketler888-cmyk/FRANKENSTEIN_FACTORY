param(
  [int]$MaxMinutes = 25,
  [int]$KillAfterStaleSeconds = 420
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
function Safe-Copy([string]$Src, [string]$Dst) {
  try {
    $d = Split-Path -Parent $Dst
    if ($d -and !(Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
    Copy-Item -LiteralPath $Src -Destination $Dst -Force -ErrorAction Stop
    return $true
  } catch { return $false }
}
function Tail-Text([string]$Path, [int]$MaxChars) {
  try {
    $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    if ($raw.Length -le $MaxChars) { return $raw }
    return $raw.Substring($raw.Length-$MaxChars, $MaxChars)
  } catch { return $null }
}

$ROOT = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
$DESKTOP = [Environment]::GetFolderPath("Desktop")
$TS = NowTs

$OUT = Join-Path $DESKTOP ("FRANKEN_RUN_AUDIT_" + $TS)
$LOG = Join-Path $OUT "logs"
$ART = Join-Path $OUT "artifacts"
New-Item -ItemType Directory -Path $OUT -Force | Out-Null
New-Item -ItemType Directory -Path $LOG -Force | Out-Null
New-Item -ItemType Directory -Path $ART -Force | Out-Null

$stdout = Join-Path $LOG "factory_stdout.txt"
$stderr = Join-Path $LOG "factory_stderr.txt"
$exitInfo = Join-Path $OUT "exit_info.txt"
$monitor = Join-Path $OUT "monitor.txt"

# locate python
$py = $null
$venvPy = Join-Path $ROOT ".venv\Scripts\python.exe"
if(Test-Path -LiteralPath $venvPy){ $py = $venvPy }
if(-not $py){
  try { $py = (Get-Command python -ErrorAction Stop).Source } catch {}
}
if(-not $py){
  W $exitInfo "Python not found (.venv preferred)."
  goto PACK
}

# compile check
$targets = @(
  "factory_master_247.py","factory_ga.py","ga_run.py","backtest_runner_v3.py",
  "runner_bridge.py","ga_adapters\runner_bridge.py"
) | ForEach-Object { Join-Path $ROOT $_ } | Where-Object { Test-Path -LiteralPath $_ }

$compileLog = Join-Path $OUT "py_compile.txt"
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("PY=$py")
$lines.Add("ROOT=$ROOT")
$okAll = $true
foreach($t in $targets){
  try {
    & $py -c "import py_compile; py_compile.compile(r'$t', doraise=True); print('OK:', r'$t')" 2>&1 | ForEach-Object { $lines.Add($_) }
  } catch {
    $okAll = $false
    $lines.Add("FAIL: $t")
    $lines.Add($_.Exception.Message)
  }
}
W $compileLog ($lines -join "`r`n")

if(!(Test-Path -LiteralPath (Join-Path $ROOT "factory_master_247.py"))){
  W $exitInfo "Missing factory_master_247.py"
  goto PACK
}

# RUN factory (non-blocking capture): poll with Peek()
Push-Location $ROOT
$p = $null
$timedOut = $false
$killedForStale = $false
$sw = [Diagnostics.Stopwatch]::StartNew()
try {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $py
  $psi.Arguments = ".\factory_master_247.py"
  $psi.WorkingDirectory = $ROOT
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true

  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi
  $null = $p.Start()

  $maxMs = [int64]($MaxMinutes * 60 * 1000)
  $outSb = New-Object System.Text.StringBuilder
  $errSb = New-Object System.Text.StringBuilder

  $hb = Join-Path $ROOT "results\heartbeat_global.json"
  $prog = Join-Path $ROOT "results\progress.jsonl"

  $lastPrint = Get-Date
  while (-not $p.HasExited -and $sw.ElapsedMilliseconds -lt $maxMs) {

    # stdout (Peek avoids ReadLine block)
    try {
      while ($p.StandardOutput -and $p.StandardOutput.Peek() -ge 0) {
        $line = $p.StandardOutput.ReadLine()
        if($line -ne $null){ [void]$outSb.AppendLine($line) }
      }
    } catch {}

    # stderr
    try {
      while ($p.StandardError -and $p.StandardError.Peek() -ge 0) {
        $line = $p.StandardError.ReadLine()
        if($line -ne $null){ [void]$errSb.AppendLine($line) }
      }
    } catch {}

    # heartbeat age kill switch
    if(Test-Path -LiteralPath $hb){
      $fi = Get-Item -LiteralPath $hb -ErrorAction SilentlyContinue
      if($fi){
        $age = (New-TimeSpan -Start $fi.LastWriteTime -End (Get-Date)).TotalSeconds
        if($age -gt $KillAfterStaleSeconds){
          $killedForStale = $true
          try { $p.Kill() } catch {}
          break
        }
      }
    }

    # live console ping every ~2 sec
    if(((Get-Date) - $lastPrint).TotalSeconds -ge 2){
      $lastPrint = Get-Date
      $hbAgeTxt = "hb=missing"
      if(Test-Path -LiteralPath $hb){
        $fi2 = Get-Item -LiteralPath $hb -ErrorAction SilentlyContinue
        if($fi2){
          $a2 = (New-TimeSpan -Start $fi2.LastWriteTime -End (Get-Date)).TotalSeconds
          $hbAgeTxt = ("hb_age={0:N1}s" -f $a2)
        }
      }
      $prTxt = "progress=missing"
      if(Test-Path -LiteralPath $prog){
        $fi3 = Get-Item -LiteralPath $prog -ErrorAction SilentlyContinue
        if($fi3){ $prTxt = "progress_lastwrite=" + $fi3.LastWriteTime.ToString("HH:mm:ss") }
      }
      Write-Host ("[RUN] pid={0} elapsed={1:N1}s {2} {3}" -f $p.Id, $sw.Elapsed.TotalSeconds, $hbAgeTxt, $prTxt) -ForegroundColor DarkCyan
    }

    Start-Sleep -Milliseconds 200
  }

  # final drains (safe)
  try { while ($p.StandardOutput -and $p.StandardOutput.Peek() -ge 0) { [void]$outSb.AppendLine($p.StandardOutput.ReadLine()) } } catch {}
  try { while ($p.StandardError  -and $p.StandardError.Peek()  -ge 0) { [void]$errSb.AppendLine($p.StandardError.ReadLine()) } } catch {}

  if(-not $p.HasExited -and $sw.ElapsedMilliseconds -ge $maxMs){
    $timedOut = $true
    try { $p.Kill() } catch {}
  }

  W $stdout $outSb.ToString()
  W $stderr $errSb.ToString()

  $info = New-Object System.Collections.Generic.List[string]
  $info.Add("ROOT=$ROOT")
  $info.Add("PY=$py")
  $info.Add("PID=$($p.Id)")
  $info.Add("MaxMinutes=$MaxMinutes")
  $info.Add(("ElapsedSec={0:N1}" -f $sw.Elapsed.TotalSeconds))
  $info.Add("TimedOut=$timedOut")
  $info.Add("KilledForStaleHeartbeat=$killedForStale")
  $info.Add("Exited=$($p.HasExited)")
  if($p.HasExited){ $info.Add("ExitCode=$($p.ExitCode)") }
  W $exitInfo ($info -join "`r`n")

  $m = New-Object System.Collections.Generic.List[string]
  $m.Add("heartbeat_exists=" + (Test-Path -LiteralPath $hb))
  if(Test-Path -LiteralPath $hb){
    $fi4 = Get-Item -LiteralPath $hb -ErrorAction SilentlyContinue
    if($fi4){ $m.Add("heartbeat_lastwrite=" + $fi4.LastWriteTime) }
    $m.Add("heartbeat_tail=")
    $m.Add((Tail-Text $hb 6000))
  }
  $m.Add("")
  $m.Add("progress_exists=" + (Test-Path -LiteralPath $prog))
  if(Test-Path -LiteralPath $prog){
    $m.Add("progress_tail=")
    $m.Add((Tail-Text $prog 8000))
  }
  W $monitor ($m -join "`r`n")
}
finally { Pop-Location }

:PACK
# collect key files
$k = @(
  "configs\default_config.json","configs\ga_config.json","configs\ga_config_v2.json","configs\factory_config.json",
  "results\heartbeat_global.json","results\progress.jsonl",
  "factory_master_247.py","factory_ga.py","ga_run.py","backtest_runner_v3.py","runner_bridge.py","ga_adapters\runner_bridge.py"
)
foreach($r in $k){
  $src = Join-Path $ROOT $r
  if(Test-Path -LiteralPath $src){
    Safe-Copy $src (Join-Path $ART ("files\" + ($r -replace "[:\\\/]","_"))) | Out-Null
  }
}

# latest results snapshot
$rg = Join-Path $ROOT "results_ga"
if(Test-Path -LiteralPath $rg){
  $lr = Get-ChildItem -LiteralPath $rg -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "run_*" -or $_.Name -like "manual_run_*" } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if($lr){
    $dst = Join-Path $ART "latest_results"
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    $take = @("backtest_report.json","params.json","stdout.txt","stderr.txt","run.log","heartbeat.json","trades.json","equity.csv","metrics.json")
    foreach($n in $take){
      $p2 = Join-Path $lr.FullName $n
      if(Test-Path -LiteralPath $p2){ Safe-Copy $p2 (Join-Path $dst $n) | Out-Null }
    }
  }
}

$ZIP = Join-Path $DESKTOP ("FRANKEN_RUN_AUDIT_" + $TS + ".zip")
Zip-Folder $OUT $ZIP

Write-Host ""
Write-Host "OK ✅ ONE-CLICK RUN + AUDIT PACKED (V2)" -ForegroundColor Green
Write-Host ("ZIP: " + $ZIP) -ForegroundColor Cyan
Write-Host ("OUT: " + $OUT) -ForegroundColor Cyan
Write-Host ("compile_ok: " + $okAll) -ForegroundColor Yellow