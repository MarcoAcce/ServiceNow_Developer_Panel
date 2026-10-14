#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-virtual_environment/Scripts/python.exe}"
APPLICATION_NAME="ServiceNowDeveloperPanel"

if [ ! -f "$PYTHON" ]; then
    echo "Python interpreter not found: $PYTHON" >&2
    echo "Create the virtual environment or set PYTHON to the interpreter to use." >&2
    exit 1
fi

if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
    echo "PyInstaller is missing, install the build requirements:" >&2
    echo "  $PYTHON -m pip install -r requirements.txt" >&2
    exit 1
fi

"$PYTHON" -m PyInstaller \
    --noconfirm \
    --clean \
    --onefile \
    --windowed \
    --name "$APPLICATION_NAME" \
    --add-data "fonts;fonts" \
    app.py

echo "Built dist/$APPLICATION_NAME.exe"
