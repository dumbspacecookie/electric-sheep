# Quick local launcher. Stdio by default; pass -Http to switch.
param(
    [switch]$Http,
    [switch]$Test
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Setting up venv (one-time)..."
    python -m venv (Join-Path $root ".venv")
    & $py -m pip install --upgrade pip
    & $py -m pip install -e (Join-Path $root ".[dev]")
}

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

if ($Test) {
    & $py -m pytest
    exit $LASTEXITCODE
}

if ($Http) {
    $env:ELECTRIC_SHEEP_TRANSPORT = "http"
    Write-Host "Starting on streamable HTTP..."
} else {
    Write-Host "Starting on stdio (default)..."
}

& $py -m electric_sheep.server
