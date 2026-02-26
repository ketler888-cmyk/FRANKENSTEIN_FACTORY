# franken_env.ps1
Set-StrictMode -Off
$ErrorActionPreference = "SilentlyContinue"

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# SAFE: stop BLAS/NumExpr oversubscription when 5 workers run in parallel
$env:OMP_NUM_THREADS="1"
$env:MKL_NUM_THREADS="1"
$env:OPENBLAS_NUM_THREADS="1"
$env:VECLIB_MAXIMUM_THREADS="1"
$env:NUMEXPR_MAX_THREADS="1"

$env:PYTHONHASHSEED="0"