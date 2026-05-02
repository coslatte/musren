#!/bin/bash
# musren Installer
# Run: ./install.sh [install|uninstall|dev]

set -e

check_python() {
    if ! command -v python &> /dev/null; then
        echo "Error: Python not found. Install Python 3.8+ first."
        exit 1
    fi
}

install() {
    echo "Building musren..."
    python -m build

    wheel=$(ls dist/musren-*.whl | head -1)
    if [ -z "$wheel" ]; then
        echo "Error: Wheel not found. Run 'python -m build' first."
        exit 1
    fi
    
    echo "Installing $wheel..."
    pip install "$wheel"
    echo "[OK] musren installed! Run: python app.py"
}

uninstall() {
    echo "Uninstalling musren..."
    pip uninstall musren -y || true
    echo "[OK] musren uninstalled."
}

dev() {
    echo "Installing in development mode..."
    pip install -e .
    echo "[OK] Dev mode installed. Run: python app.py"
}

check_python

case "${1:-install}" in
    install) install ;;
    uninstall) uninstall ;;
    dev) dev ;;
    *) echo "Usage: $0 {install|uninstall|dev}" ;;
esac