function Invoke-Git([string[]]$Args){
  # Captures stderr+stdout, does NOT throw on progress noise; throws only if exitcode != 0
  $out = & git @Args 2>&1
  $code = $LASTEXITCODE
  if($code -ne 0){
    throw ("git " + ($Args -join " ") + " failed (exit=$code):
" + ($out -join "
"))
  }
  return $out
}

Set-StrictMode -Off
$ErrorActionPreference = 'SilentlyContinue'
$ROOT  = 'C:\Users\user\Desktop\Ð¤Ñ€Ð°Ð½ÐºÐ¸Ð½ÑˆÑ‚ÑÐ¹Ð½'
$TOOLS = Join-Path $ROOT 'tools'
$WATCH = Join-Path $TOOLS 'fr_autosync.ps1'

if(!(Test-Path -LiteralPath $WATCH)){ exit 0 }

$running = Get-WmiObject Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.CommandLine -and ($_.CommandLine -like "*fr_autosync.ps1*") }

if(-not $running){
  Start-Process -FilePath "powershell.exe" -ArgumentList @(
    '-NoProfile',
    '-ExecutionPolicy','Bypass',
    '-File', $WATCH
  ) -WindowStyle Hidden | Out-Null
}
