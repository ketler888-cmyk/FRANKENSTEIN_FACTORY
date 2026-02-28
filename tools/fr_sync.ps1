# ================= FRANKEN | fr_sync (PS 5.1) - RELIABLE GIT EXEC =================
Set-StrictMode -Off
$ErrorActionPreference = "Stop"

$ROOT   = "C:\Users\user\Desktop\Франкинштэйн"
$REMOTE = "origin"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Host "[FAIL] $m" -ForegroundColor Red }
function Assert-Path([string]$p,[string]$h){ if(-not(Test-Path -LiteralPath $p)){ throw "NOT FOUND: $p | $h" } }

function Get-GitExe {
  $g = Get-Command git -ErrorAction SilentlyContinue
  if($g -and $g.Path){ return $g.Path }
  $candidates = @(
    "$env:ProgramFiles\Git\cmd\git.exe",
    "$env:ProgramFiles\Git\bin\git.exe",
    "${env:ProgramFiles(x86)}\Git\cmd\git.exe",
    "${env:ProgramFiles(x86)}\Git\bin\git.exe"
  )
  foreach($p in $candidates){ if(Test-Path -LiteralPath $p){ return $p } }
  throw "git not found."
}

function Invoke-Exe([string]$Exe, [string[]]$Args, [string]$Cwd){
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $Exe
  $psi.WorkingDirectory = $Cwd
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.CreateNoWindow = $true
  foreach($a in $Args){ [void]$psi.ArgumentList.Add($a) }

  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi
  [void]$p.Start()
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  return [pscustomobject]@{ Code=$p.ExitCode; Text=(($stdout + "
" + $stderr).Trim()) }
}

function Git([string[]]$Args){
  $r = Invoke-Exe $GIT $Args $ROOT
  return $r
}
function GitOrThrow([string[]]$Args, [string]$What){
  $r = Git $Args
  if($r.Code -ne 0){
    Fail "$What FAILED (exit=$($r.Code))"
    if($r.Text){ Write-Host $r.Text -ForegroundColor Red }
    throw "$What failed"
  }
  return $r
}

Assert-Path $ROOT "ROOT missing"
Assert-Path (Join-Path $ROOT ".git") ".git missing"
$GIT = Get-GitExe

$branch = (GitOrThrow @("rev-parse","--abbrev-ref","HEAD") "rev-parse branch").Text.Trim()
if(-not $branch){ $branch = "main" }

Info "Fetch origin..."
GitOrThrow @("fetch",$REMOTE,"--prune") "fetch --prune"

Info "Status:"
Write-Host (GitOrThrow @("status","-sb") "status -sb").Text -ForegroundColor Gray

Info "Push..."
$p = Git @("push",$REMOTE,$branch)
if($p.Code -ne 0){
  Warn "Normal push failed -> trying --force-with-lease ⚠️"
  if($p.Text){ Write-Host $p.Text -ForegroundColor Yellow }
  $p2 = GitOrThrow @("push","--force-with-lease",$REMOTE,$branch) "push --force-with-lease"
  Ok "Push OK (force-with-lease) ✅"
} else {
  Ok "Push OK ✅"
}

Info "Verify HEAD == origin/$branch"
GitOrThrow @("fetch",$REMOTE,$branch) "fetch branch"
$head = (GitOrThrow @("rev-parse","HEAD") "rev-parse HEAD").Text.Trim()
$up   = (GitOrThrow @("rev-parse",("$REMOTE/$branch")) "rev-parse upstream").Text.Trim()
if($head -ne $up){ throw "MIRROR FAIL: HEAD != $REMOTE/$branch
HEAD=$head
UP  =$up" }
Ok "Mirror synced ✅"