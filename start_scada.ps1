# SCADA Application Startup Script
# This script automatically activates the virtual environment and checks dependencies

$ErrorActionPreference = "Stop"

# Change to project directory
Set-Location "C:\Users\TUX\source\repos\HMI"

# Activate virtual environment
$venvPath = ".venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    & $venvPath
    Write-Host "Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "Warning: Virtual environment not found at $venvPath" -ForegroundColor Yellow
}

# Check if psutil is installed
try {
    python -c "import psutil" 2>$null
    Write-Host "psutil is already installed" -ForegroundColor Green
} catch {
    Write-Host "Installing psutil..." -ForegroundColor Yellow
    pip install psutil
    if ($LASTEXITCODE -eq 0) {
        Write-Host "psutil installed successfully" -ForegroundColor Green
    } else {
        Write-Host "Failed to install psutil" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Start the application
Write-Host "`nStarting SCADA Application..." -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
python run_scada.py

Write-Host "`nApplication closed" -ForegroundColor Yellow
Read-Host "Press Enter to exit"
