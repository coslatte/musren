#!/usr/bin/env bash
# Install from a checkout into the active Python environment.
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

case "${1:-install}" in
    install) python3 -m pip install "${project_root}[tui]" ;;
    dev) python3 -m pip install -e "${project_root}[tui]" ;;
    cli) python3 -m pip install "$project_root" ;;
    uninstall) python3 -m pip uninstall musren -y ;;
    *) echo 'Usage: bash scripts/install.sh {install|dev|cli|uninstall}'; exit 1 ;;
esac
