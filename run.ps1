# ================================================================
# run.ps1 -- everything2md launcher
# ================================================================
# Creates/activates venv, installs dependencies, launches GUI.
# Run from the project root: .\run.ps1
# ================================================================

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# Create venv if it doesn't exist (always use Python 3.12)
$Python312 = "D:\Python312\python.exe"
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (Python 3.12)..."
    & $Python312 -m venv .venv
}

# Activate venv
.\.venv\Scripts\Activate.ps1

# Install / sync dependencies
Write-Host "Installing dependencies..."
pip install -r requirements.txt --quiet

# Launch GUI
Write-Host "Launching everything2md..."
python -m src.gui
