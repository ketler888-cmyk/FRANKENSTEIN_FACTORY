param([int]$Last=200)
Set-StrictMode -Off
$ErrorActionPreference="Stop"
$ROOT = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
$p = Join-Path $ROOT "results\progress.jsonl"
if(!(Test-Path -LiteralPath $p)){ Write-Host "[TAIL] missing: $p"; exit 1 }

Write-Host "[TAIL] $p (last $Last lines)" -ForegroundColor Cyan
Get-Content -LiteralPath $p -Tail $Last

Write-Host ""
Write-Host "[TAIL] errors only:" -ForegroundColor Yellow
Get-Content -LiteralPath $p -Tail $Last | Where-Object { $_ -match '"event"\s*:\s*"(error|exception|fail|master_error|ga_error)"' -or $_ -match '"level"\s*:\s*"(ERROR|CRITICAL)"' }