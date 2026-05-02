#!/bin/bash
# MusRen Installer

set -e

install() {
    echo "Building MusRen..."
    python -m build

    wheel=$(ls dist/musren-*.whl | head -1)
    echo "Installing $wheel..."
    pip install "$wheel"
    echo "MusRen installed! Run 'musren' to start."
}

uninstall() {
    echo "Uninstalling MusRen..."
    pip uninstall musren -y
}

dev() {
    echo "Installing in development mode..."
    pip install -e .
    echo "Dev mode installed. Run 'musren' to start."
}

case "${1:-install}" in
    install) install ;;
    uninstall) uninstall ;;
    dev) dev ;;
    *) echo "Usage: $0 {install|uninstall|dev}" ;;
esac