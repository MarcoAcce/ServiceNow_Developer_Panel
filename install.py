import argparse
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.app_paths import icon_path
from installer.installation import (
    DISPLAY_NAME,
    InstallError,
    InstallOptions,
    default_target,
    install,
    is_supported_platform,
    uninstall,
)
from installer.installer_window import WINDOW_TITLE, InstallerDialog
from ui.theme import DARK_THEME, LIGHT_THEME, apply_theme


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=f"Install {DISPLAY_NAME}. Without --silent the setup window opens."
    )
    result.add_argument(
        "--silent", action="store_true", help="install or uninstall without the window"
    )
    result.add_argument("--uninstall", action="store_true", help="remove an installation")
    result.add_argument(
        "--target", type=Path, help=f"install folder (default {default_target()})"
    )
    result.add_argument(
        "--menu",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="add an application menu entry (default yes)",
    )
    result.add_argument(
        "--desktop",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="add a desktop shortcut (default no)",
    )
    result.add_argument(
        "--import-data",
        type=Path,
        metavar="FOLDER",
        help="copy an existing data folder into a new installation",
    )
    result.add_argument(
        "--remove-data", action="store_true", help="also delete the data when uninstalling"
    )
    return result


def run_silent(arguments: argparse.Namespace, target: Path) -> None:
    try:
        if arguments.uninstall:
            uninstall(target, arguments.remove_data)
            print(f"Uninstalled from {target}")
            return
        import_data = arguments.import_data
        result = install(
            InstallOptions(
                target=target,
                menu=arguments.menu,
                desktop=arguments.desktop,
                import_data=import_data.expanduser().resolve() if import_data else None,
            )
        )
    except (InstallError, OSError) as error:
        sys.exit(str(error))
    print(f"Installed {result.executable}")
    print(f"MCP server {result.mcp_executable}")
    print(f"Data folder {result.data}")
    for shortcut in result.shortcuts:
        print(f"Shortcut {shortcut}")
    if result.desktop_missing:
        print("No desktop folder found, skipped the desktop shortcut")


def run_window(arguments: argparse.Namespace, target: Path) -> None:
    application = QApplication(sys.argv[:1])
    application.setApplicationName(WINDOW_TITLE)
    application.setWindowIcon(QIcon(str(icon_path())))
    dark = application.styleHints().colorScheme() == Qt.ColorScheme.Dark
    apply_theme(application, DARK_THEME if dark else LIGHT_THEME)
    InstallerDialog(target, arguments.menu, arguments.desktop).exec()


def main() -> None:
    if not is_supported_platform():
        sys.exit(f"Unsupported platform: {sys.platform}")
    arguments = parser().parse_args()
    target = (arguments.target or default_target()).expanduser().resolve()
    if arguments.silent:
        run_silent(arguments, target)
    else:
        run_window(arguments, target)


if __name__ == "__main__":
    main()
