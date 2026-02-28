Set-StrictMode -Off
$ErrorActionPreference = "Stop"

$ROOT   = "C:\Users\user\Desktop\Франкинштэйн"
$REMOTE = "origin"
$BRANCH = "usage: git [-v | --version] [-h | --help] [-C <path>] [-c <name>=<value>]
           [--exec-path[=<path>]] [--html-path] [--man-path] [--info-path]
           [-p | --paginate | -P | --no-pager] [--no-replace-objects] [--no-lazy-fetch]
           [--no-optional-locks] [--no-advice] [--bare] [--git-dir=<path>]
           [--work-tree=<path>] [--namespace=<name>] [--config-env=<name>=<envvar>]
           <command> [<args>]

These are common Git commands used in various situations:

start a working area (see also: git help tutorial)
   clone      Clone a repository into a new directory
   init       Create an empty Git repository or reinitialize an existing one

work on the current change (see also: git help everyday)
   add        Add file contents to the index
   mv         Move or rename a file, a directory, or a symlink
   restore    Restore working tree files
   rm         Remove files from the working tree and from the index

examine the history and state (see also: git help revisions)
   bisect     Use binary search to find the commit that introduced a bug
   diff       Show changes between commits, commit and working tree, etc
   grep       Print lines matching a pattern
   log        Show commit logs
   show       Show various types of objects
   status     Show the working tree status

grow, mark and tweak your common history
   backfill   Download missing objects in a partial clone
   branch     List, create, or delete branches
   commit     Record changes to the repository
   merge      Join two or more development histories together
   rebase     Reapply commits on top of another base tip
   reset      Reset current HEAD to the specified state
   switch     Switch branches
   tag        Create, list, delete or verify a tag object signed with GPG

collaborate (see also: git help workflows)
   fetch      Download objects and refs from another repository
   pull       Fetch from and integrate with another repository or a local branch
   push       Update remote refs along with associated objects

'git help -a' and 'git help -g' list available subcommands and some
concept guides. See 'git help <command>' or 'git help <concept>'
to read about a specific subcommand or concept.
See 'git help git' for an overview of the system."
$MSG    = ("sync: " + (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK]   $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Host "[FAIL] $m" -ForegroundColor Red }

function Assert-Path([string]$p,[string]$h){ if(-not(Test-Path -LiteralPath $p)){ throw "NOT FOUND: $p | $h" } }
function Ensure-Dir([string]$p){ if(-not(Test-Path -LiteralPath $p)){ New-Item -ItemType Directory -Path $p -Force | Out-Null } }

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
  throw "git not found. Install Git for Windows and reopen PowerShell."
}

function Run-CmdCapture([string]$exe, [string]$args, [string]$cwd){
  $tmp = Join-Path $env:TEMP ("fr_cmd_" + [Guid]::NewGuid().ToString("N") + ".txt")
  $line = ""$exe" $args 1> "$tmp" 2>&1"
  Push-Location $cwd
  try { cmd.exe /d /c $line | Out-Null } finally { Pop-Location }
  $txt = ""
  if(Test-Path -LiteralPath $tmp){
    $txt = Get-Content -LiteralPath $tmp -Raw -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
  }
  return $txt
}

$GIT = Get-GitExe

Assert-Path $ROOT "Project root missing"
Assert-Path (Join-Path $ROOT ".git") ".git missing"

Info ("git: " + (Run-CmdCapture $GIT "--version" $ROOT).Trim())

Info "fetch --prune"
Run-CmdCapture $GIT ("fetch " + $REMOTE + " --prune") $ROOT | Out-Null

Info "status -sb"
Write-Host (Run-CmdCapture $GIT "status -sb" $ROOT) -ForegroundColor Gray

Info "add -A"
Run-CmdCapture $GIT "add -A" $ROOT | Out-Null

$por = (Run-CmdCapture $GIT "status --porcelain" $ROOT).Trim()
if(-not $por){
  Warn "Nothing to commit."
} else {
  Info "commit"
  Run-CmdCapture $GIT ("commit -m " + ""$MSG"") $ROOT | Out-Null
}

Info "push"
Write-Host (Run-CmdCapture $GIT ("push " + $REMOTE + " " + $BRANCH) $ROOT) -ForegroundColor Gray

Info "verify HEAD == origin/main"
Run-CmdCapture $GIT ("fetch " + $REMOTE + " " + $BRANCH) $ROOT | Out-Null
$head = (Run-CmdCapture $GIT "rev-parse HEAD" $ROOT).Trim()
$up   = (Run-CmdCapture $GIT ("rev-parse " + $REMOTE + "/" + $BRANCH) $ROOT).Trim()
if($head -ne $up){
  Fail "MIRROR MISMATCH"
  throw "Mirror mismatch: HEAD != $REMOTE/$BRANCH"
}
Ok "MIRROR PERFECT ✅  (HEAD == origin/main)"