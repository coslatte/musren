# Install from a checkout into the active Python environment.
# Run: .\scripts\install.ps1 [-Dev] [-Uninstall] [-CliOnly]
param(
    [switch]$Dev,
    [switch]$Uninstall,
    [switch]$CliOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$null = Get-Command python -ErrorAction Stop

if ($Uninstall) {
    python -m pip uninstall musren -y
} else {
    $installTarget = if ($CliOnly) { $projectRoot } else { "${projectRoot}[tui]" }
    if ($Dev) {
        python -m pip install -e $installTarget
    } else {
        python -m pip install $installTarget
    }
}

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not $Uninstall) {
    if ($CliOnly) { Write-Host 'Installed. Run musren --help.' }
    else { Write-Host 'Installed. Run musren-tui or musren --help.' }
}
