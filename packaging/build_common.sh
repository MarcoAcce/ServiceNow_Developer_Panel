APP_NAME="ServiceNowDeveloperPanel"
SETUP_NAME="ServiceNowDeveloperPanelSetup"
APP_DIRECTORY="dist/$APP_NAME"
KEPT_DATA="dist/.$APP_NAME-data"
SETUP_PAYLOAD="build/payload"

require_python() {
    if ! command -v "$PYTHON" >/dev/null 2>&1; then
        echo "Python interpreter not found: $PYTHON" >&2
        echo "Create the virtual environment or set PYTHON to the interpreter to use." >&2
        exit 1
    fi
    if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
        echo "PyInstaller is missing, install the build requirements:" >&2
        echo "  $PYTHON -m pip install -r requirements.txt" >&2
        exit 1
    fi
}

pyinstaller() {
    "$PYTHON" -m PyInstaller --noconfirm --clean "$@"
}

restore_data() {
    if [ -d "$KEPT_DATA" ]; then
        mkdir -p "$APP_DIRECTORY"
        mv "$KEPT_DATA" "$APP_DIRECTORY/data"
    fi
}

build_app() {
    require_python
    if [ -e "$KEPT_DATA" ]; then
        echo "$KEPT_DATA is left from an interrupted build." >&2
        echo "Move it back to $APP_DIRECTORY/data, then build again." >&2
        exit 1
    fi
    if [ -d "$APP_DIRECTORY/data" ]; then
        mv "$APP_DIRECTORY/data" "$KEPT_DATA"
        trap restore_data EXIT
    fi
    pyinstaller --distpath dist packaging/panel.spec
}

build_setup() {
    require_python
    pyinstaller --distpath "$SETUP_PAYLOAD" packaging/panel.spec
    pyinstaller --distpath dist packaging/installer.spec
}
