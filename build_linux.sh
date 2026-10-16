#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-virtual_environment/bin/python}"
SETUP_NAME="ServiceNowDeveloperPanelSetup"

if [ ! -x "$PYTHON" ]; then
    echo "Python interpreter not found: $PYTHON" >&2
    echo "Create the virtual environment or set PYTHON to the interpreter to use." >&2
    exit 1
fi

if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
    echo "PyInstaller is missing, install the build requirements:" >&2
    echo "  $PYTHON -m pip install -r requirements.txt" >&2
    exit 1
fi

"$PYTHON" -m PyInstaller --noconfirm --clean packaging/panel.spec
"$PYTHON" -m PyInstaller --noconfirm --clean packaging/installer.spec

echo "Built dist/$SETUP_NAME"
