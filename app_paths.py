import os
import sys
from pathlib import Path

APPLICATION_DIRECTORY_NAME: str = "ServiceNowDeveloperPanel"
DATA_DIRECTORY_NAME: str = "data"
DATABASE_FILE_NAME: str = "panel.store"
WRITE_PROBE_NAME: str = ".write_probe"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def installation_directory() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


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


def _is_writable(directory: Path) -> bool:
    probe = directory / WRITE_PROBE_NAME
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe.touch()
        probe.unlink()
    except OSError:
        return False
    return True
