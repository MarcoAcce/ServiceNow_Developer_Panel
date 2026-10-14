import os
import sys
from pathlib import Path

APPLICATION_DIRECTORY_NAME: str = "ServiceNowDeveloperPanel"
DATA_DIRECTORY_NAME: str = "data"
CACHE_DIRECTORY_NAME: str = "cache"
DATABASE_FILE_NAME: str = "panel.store"
FONTS_DIRECTORY_NAME: str = "fonts"
ASSETS_DIRECTORY_NAME: str = "assets"
ICON_FILE_NAME: str = "icon.ico"
ICON_IMAGE_FILE_NAME: str = "icon.png"
WRITE_PROBE_NAME: str = ".write_probe"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def installation_directory() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_directory() -> Path:
    bundle = getattr(sys, "_MEIPASS", "")
    if is_frozen() and bundle:
        return Path(bundle)
    return Path(__file__).resolve().parent


def fonts_directory() -> Path:
    return resource_directory() / FONTS_DIRECTORY_NAME


def assets_directory() -> Path:
    return resource_directory() / ASSETS_DIRECTORY_NAME


def icon_path() -> Path:
    return assets_directory() / ICON_FILE_NAME


def icon_image_path() -> Path:
    return assets_directory() / ICON_IMAGE_FILE_NAME


def fallback_data_directory() -> Path:
    if sys.platform.startswith("win"):
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        root = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(root) / APPLICATION_DIRECTORY_NAME


def data_directory() -> Path:
    packaged = installation_directory() / DATA_DIRECTORY_NAME
    if _is_writable(packaged):
        return packaged
    fallback = fallback_data_directory()
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def database_path() -> Path:
    return data_directory() / DATABASE_FILE_NAME


def cache_directory() -> Path:
    directory = data_directory() / CACHE_DIRECTORY_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def cache_path(cache_name: str) -> Path:
    return cache_directory() / cache_name


def _is_writable(directory: Path) -> bool:
    probe = directory / WRITE_PROBE_NAME
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe.touch()
        probe.unlink()
    except OSError:
        return False
    return True
