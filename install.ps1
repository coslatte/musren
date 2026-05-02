# MusRen Installer
# Run this script to install MusRen

param(
    [switch]$Uninstall,
    [switch]$Dev
)

$ErrorActionPreference = "Stop"

function Install-MusRen {
    Write-Host "Building MusRen..." -ForegroundColor Cyan

    # Build wheel
    python -m build

    # Find the wheel
    $wheel = Get-ChildItem dist/musren-*.whl | Select-Object -First 1
    if (-not $wheel) {
        Write-Host "Error: Wheel not found in dist/" -ForegroundColor Red
        exit 1
    }

    Write-Host "Installing $($wheel.Name)..." -ForegroundColor Cyan
    pip install $wheel.FullName

    Write-Host "`nMusRen installed successfully!" -ForegroundColor Green
    Write-Host "Run 'musren' to start." -ForegroundColor Yellow
}

function Uninstall-MusRen {
    Write-Host "Uninstalling MusRen..." -ForegroundColor Cyan
    pip uninstall musren -y
    Write-Host "MusRen uninstalled." -ForegroundColor Green
}

if ($Uninstall) {
    Uninstall-MusRen
} elseif ($Dev) {
    Write-Host "Installing in development mode..." -ForegroundColor Cyan
    pip install -e .
    Write-Host "Dev mode installed. Run 'musren' to start." -ForegroundColor Green
} else {
    Install-MusRen
}