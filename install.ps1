# musren Installer
# Run: .\install.ps1 [-Dev] [-Uninstall]

param(
    [switch]$Uninstall,
    [switch]$Dev
)

$ErrorActionPreference = "Stop"

function Test-Python {
    try {
        $null = Get-Command python -ErrorAction Stop
    } catch {
        Write-Host "Error: Python not found. Install Python 3.8+ first." -ForegroundColor Red
        exit 1
    }
}

function Test-Pip {
    try {
        $null = Get-Command pip -ErrorAction Stop
    } catch {
        Write-Host "Error: pip not found. Install pip first." -ForegroundColor Red
        exit 1
    }
}

function Install-musren {
    Write-Host "Building musren..." -ForegroundColor Cyan

    python -m build

    $wheel = Get-ChildItem dist/musren-*.whl | Select-Object -First 1
    if (-not $wheel) {
        Write-Host "Error: Wheel not found. Run 'python -m build' first." -ForegroundColor Red
        exit 1
    }

    Write-Host "Installing $($wheel.Name)..." -ForegroundColor Cyan
    pip install $wheel.FullName

    Write-Host "`n[OK] musren installed successfully!" -ForegroundColor Green
    Write-Host "Run: python app.py" -ForegroundColor Yellow
}

function Uninstall-musren {
    Write-Host "Uninstalling musren..." -ForegroundColor Cyan
    pip uninstall musren -y -ErrorAction SilentlyContinue
    Write-Host "[OK] musren uninstalled." -ForegroundColor Green
}

Test-Python
Test-Pip

if ($Uninstall) {
    Uninstall-musren
} elseif ($Dev) {
    Write-Host "Installing in development mode..." -ForegroundColor Cyan
    pip install -e .
    Write-Host "[OK] Dev mode installed. Run: python app.py" -ForegroundColor Green
} else {
    Install-musren
}