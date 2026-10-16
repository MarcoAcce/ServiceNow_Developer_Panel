import json
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from core.app_paths import (
    APPLICATION_DIRECTORY_NAME,
    ASSETS_DIRECTORY_NAME,
    DATA_DIRECTORY_NAME,
    DATABASE_FILE_NAME,
    ICON_IMAGE_FILE_NAME,
    is_frozen,
    resource_directory,
)

DISPLAY_NAME: str = "ServiceNow Developer Panel"
COMMENT: str = "Query ServiceNow instances through the Table API"
CATEGORIES: str = "Development;"
MCP_SERVER_NAME: str = "servicenow-panel"
MCP_EXECUTABLE_STEM: str = f"{APPLICATION_DIRECTORY_NAME}Mcp"
MCP_CONFIGURATION_FILE_NAME: str = "mcp.json"
MANIFEST_FILE_NAME: str = "installation.json"
MANIFEST_VERSION: int = 1
PAYLOAD_DIRECTORY_NAME: str = "payload"
INTERNAL_DIRECTORY_NAME: str = "_internal"
SOURCE_DIRECTORY: Path = Path(__file__).resolve().parent.parent
BUILD_PAYLOAD_DIRECTORY: Path = SOURCE_DIRECTORY / "dist" / APPLICATION_DIRECTORY_NAME
WINDOWS_SUFFIX: str = ".exe"
DESKTOP_ENTRY_SUFFIX: str = ".desktop"
WINDOWS_SHORTCUT_SUFFIX: str = ".lnk"
DESKTOP_ENTRY_ESCAPES: tuple[str, ...] = ("\\", '"', "`", "$")
EXECUTABLE_MODE: int = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
FILE_MODE: int = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
JSON_INDENT: int = 2
LIBRARY_PATH_VARIABLE: str = "LD_LIBRARY_PATH"
ORIGINAL_LIBRARY_PATH_VARIABLE: str = "LD_LIBRARY_PATH_ORIG"
RESET_ENVIRONMENT_VARIABLE: str = "PYINSTALLER_RESET_ENVIRONMENT"
POWERSHELL: tuple[str, ...] = ("powershell", "-NoProfile", "-NonInteractive", "-Command")
WINDOWS_FOLDER_SCRIPT: str = "[Environment]::GetFolderPath($env:PANEL_FOLDER)"
WINDOWS_SHORTCUT_SCRIPT: str = (
    "$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($env:PANEL_LINK); "
    "$shortcut.TargetPath = $env:PANEL_TARGET; "
    "$shortcut.WorkingDirectory = $env:PANEL_DIRECTORY; "
    "$shortcut.IconLocation = $env:PANEL_TARGET; "
    "$shortcut.Description = $env:PANEL_COMMENT; "
    "$shortcut.Save()"
)


class InstallError(Exception):
    pass


@dataclass(frozen=True)
class InstallOptions:
    target: Path
    menu: bool
    desktop: bool
    import_data: Path | None = None


@dataclass(frozen=True)
class InstallResult:
    target: Path
    executable: Path
    mcp_executable: Path
    data: Path
    menu_shortcut: Path | None
    desktop_shortcut: Path | None
    desktop_missing: bool

    @property
    def shortcuts(self) -> tuple[Path, ...]:
        candidates = (self.menu_shortcut, self.desktop_shortcut)
        return tuple(shortcut for shortcut in candidates if shortcut is not None)


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_supported_platform() -> bool:
    return is_windows() or sys.platform.startswith("linux")


def executable_name(stem: str) -> str:
    suffix = WINDOWS_SUFFIX if is_windows() else ""
    return f"{stem}{suffix}"


def application_executable(target: Path) -> Path:
    return target / executable_name(APPLICATION_DIRECTORY_NAME)


def mcp_executable(target: Path) -> Path:
    return target / executable_name(MCP_EXECUTABLE_STEM)


def data_directory(target: Path) -> Path:
    return target / DATA_DIRECTORY_NAME


def default_target() -> Path:
    if is_windows():
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(root) / "Programs" / APPLICATION_DIRECTORY_NAME
    return Path.home() / ".local" / "opt" / APPLICATION_DIRECTORY_NAME


def payload_directory() -> Path:
    if is_frozen():
        return resource_directory() / PAYLOAD_DIRECTORY_NAME
    return BUILD_PAYLOAD_DIRECTORY


def payload_entries() -> tuple[str, ...]:
    payload = payload_directory()
    if not application_executable(payload).is_file():
        raise InstallError(f"The application to install was not found in {payload}")
    return tuple(sorted(entry.name for entry in payload.iterdir()))


def external_environment() -> dict[str, str]:
    environment = dict(os.environ)
    if not is_frozen():
        return environment
    environment[RESET_ENVIRONMENT_VARIABLE] = "1"
    original = environment.pop(ORIGINAL_LIBRARY_PATH_VARIABLE, None)
    if original is None:
        environment.pop(LIBRARY_PATH_VARIABLE, None)
    else:
        environment[LIBRARY_PATH_VARIABLE] = original
    return environment


def run_quietly(command: list[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    try:
        completed = subprocess.run(
            command, env=external_environment(), capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip()


def run_powershell(script: str, variables: dict[str, str]) -> str:
    try:
        completed = subprocess.run(
            [*POWERSHELL, script],
            env={**external_environment(), **variables},
            capture_output=True,
            text=True,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise InstallError(f"PowerShell failed: {error}") from error
    return completed.stdout.strip()


def windows_folder(name: str) -> Path:
    return Path(run_powershell(WINDOWS_FOLDER_SCRIPT, {"PANEL_FOLDER": name}))


def linux_applications_directory() -> Path:
    root = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(root) / "applications"


def linux_desktop_directory() -> Path:
    answer = run_quietly(["xdg-user-dir", "DESKTOP"])
    return Path(answer) if answer else Path.home() / "Desktop"


def menu_shortcut_path() -> Path:
    if is_windows():
        return windows_folder("Programs") / f"{DISPLAY_NAME}{WINDOWS_SHORTCUT_SUFFIX}"
    name = f"{APPLICATION_DIRECTORY_NAME}{DESKTOP_ENTRY_SUFFIX}"
    return linux_applications_directory() / name


def desktop_shortcut_path() -> Path | None:
    if is_windows():
        return windows_folder("Desktop") / f"{DISPLAY_NAME}{WINDOWS_SHORTCUT_SUFFIX}"
    directory = linux_desktop_directory()
    if not directory.is_dir():
        return None
    return directory / f"{APPLICATION_DIRECTORY_NAME}{DESKTOP_ENTRY_SUFFIX}"


def desktop_entry_quote(value: str) -> str:
    for character in DESKTOP_ENTRY_ESCAPES:
        value = value.replace(character, f"\\{character}")
    return f'"{value}"'


def desktop_entry(target: Path) -> str:
    executable = application_executable(target)
    icon = target / INTERNAL_DIRECTORY_NAME / ASSETS_DIRECTORY_NAME / ICON_IMAGE_FILE_NAME
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={DISPLAY_NAME}",
        f"Comment={COMMENT}",
        f"Exec={desktop_entry_quote(str(executable))}",
        f"Path={target}",
        f"Icon={icon}",
        "Terminal=false",
        f"Categories={CATEGORIES}",
        f"StartupWMClass={APPLICATION_DIRECTORY_NAME}",
    ]
    return "\n".join(lines) + "\n"


def create_shortcut(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    executable = application_executable(target)
    if is_windows():
        run_powershell(
            WINDOWS_SHORTCUT_SCRIPT,
            {
                "PANEL_LINK": str(link),
                "PANEL_TARGET": str(executable),
                "PANEL_DIRECTORY": str(target),
                "PANEL_COMMENT": COMMENT,
            },
        )
        return
    link.write_text(desktop_entry(target), encoding="utf-8")
    link.chmod(EXECUTABLE_MODE)


def trust_desktop_shortcut(link: Path) -> None:
    if not is_windows():
        run_quietly(["gio", "set", str(link), "metadata::trusted", "true"])


def mcp_configuration(target: Path) -> str:
    configuration = {"mcpServers": {MCP_SERVER_NAME: {"command": str(mcp_executable(target))}}}
    return json.dumps(configuration, indent=JSON_INDENT)


def manifest_path(target: Path) -> Path:
    return target / MANIFEST_FILE_NAME


def is_installed(target: Path) -> bool:
    return manifest_path(target).is_file()


def read_manifest(target: Path) -> tuple[tuple[str, ...], tuple[Path, ...]]:
    try:
        manifest = json.loads(manifest_path(target).read_text(encoding="utf-8"))
        entries = tuple(str(entry) for entry in manifest["entries"])
        shortcuts = tuple(Path(str(shortcut)) for shortcut in manifest["shortcuts"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise InstallError(f"The installation in {target} is damaged: {error}") from error
    if any(Path(entry).name != entry or entry == DATA_DIRECTORY_NAME for entry in entries):
        raise InstallError(f"The installation in {target} lists unexpected files")
    return entries, shortcuts


def write_manifest(target: Path, entries: tuple[str, ...], shortcuts: tuple[Path, ...]) -> None:
    manifest = {
        "version": MANIFEST_VERSION,
        "entries": list(entries),
        "shortcuts": [str(shortcut) for shortcut in shortcuts],
    }
    manifest_path(target).write_text(json.dumps(manifest, indent=JSON_INDENT), encoding="utf-8")


def ensure_not_running(target: Path) -> None:
    for executable in (application_executable(target), mcp_executable(target)):
        if not executable.exists():
            continue
        try:
            with open(executable, "r+b"):
                pass
        except OSError as error:
            raise InstallError(
                f"{executable.name} is running, close the application and any MCP client "
                "using it, then try again"
            ) from error


def validate(options: InstallOptions) -> None:
    target = options.target
    if not target.is_absolute():
        raise InstallError("Choose an absolute install folder")
    if target.exists() and not target.is_dir():
        raise InstallError(f"{target} is not a folder")
    if target.is_dir() and not is_installed(target):
        if any(entry.name != DATA_DIRECTORY_NAME for entry in target.iterdir()):
            raise InstallError(f"{target} is not empty, choose an empty or new folder")
    if options.import_data is not None:
        if not (options.import_data / DATABASE_FILE_NAME).is_file():
            raise InstallError(f"No {DATABASE_FILE_NAME} found in {options.import_data}")
        if (data_directory(target) / DATABASE_FILE_NAME).exists():
            raise InstallError(f"{data_directory(target)} already contains data")
    payload_entries()


def remove_entry(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def remove_previous(target: Path) -> None:
    if not is_installed(target):
        return
    entries, shortcuts = read_manifest(target)
    ensure_not_running(target)
    for shortcut in shortcuts:
        remove_entry(shortcut)
    for entry in entries:
        remove_entry(target / entry)


def normalize_permissions(directory: Path) -> None:
    directory.chmod(EXECUTABLE_MODE)
    for root, directories, files in os.walk(directory):
        for name in (*directories, *files):
            path = Path(root) / name
            if path.is_symlink():
                continue
            if path.is_dir() or path.stat().st_mode & stat.S_IXUSR:
                path.chmod(EXECUTABLE_MODE)
            else:
                path.chmod(FILE_MODE)


def copy_payload(target: Path) -> tuple[str, ...]:
    payload = payload_directory()
    entries = payload_entries()
    for entry in entries:
        source = payload / entry
        if source.is_dir():
            shutil.copytree(source, target / entry, symlinks=True)
        else:
            shutil.copy2(source, target / entry)
    if not is_windows():
        application_executable(target).chmod(EXECUTABLE_MODE)
        mcp_executable(target).chmod(EXECUTABLE_MODE)
        for entry in entries:
            if (target / entry).is_dir():
                normalize_permissions(target / entry)
    return entries


def install(options: InstallOptions) -> InstallResult:
    validate(options)
    target = options.target
    remove_previous(target)
    target.mkdir(parents=True, exist_ok=True)
    entries = copy_payload(target)
    configuration = target / MCP_CONFIGURATION_FILE_NAME
    configuration.write_text(mcp_configuration(target) + "\n", encoding="utf-8")
    entries = (*entries, MCP_CONFIGURATION_FILE_NAME)

    data = data_directory(target)
    if options.import_data is not None:
        shutil.copytree(options.import_data, data, dirs_exist_ok=True)
    data.mkdir(exist_ok=True)

    menu = menu_shortcut_path() if options.menu else None
    if menu is not None:
        create_shortcut(menu, target)
    desktop = desktop_shortcut_path() if options.desktop else None
    if desktop is not None:
        create_shortcut(desktop, target)
        trust_desktop_shortcut(desktop)
    result = InstallResult(
        target=target,
        executable=application_executable(target),
        mcp_executable=mcp_executable(target),
        data=data,
        menu_shortcut=menu,
        desktop_shortcut=desktop,
        desktop_missing=options.desktop and desktop is None,
    )
    write_manifest(target, entries, result.shortcuts)
    return result


def uninstall(target: Path, remove_data: bool) -> None:
    if not is_installed(target):
        raise InstallError(f"No installation found in {target}")
    remove_previous(target)
    manifest_path(target).unlink()
    data = data_directory(target)
    if remove_data and data.exists():
        shutil.rmtree(data)
    if not any(target.iterdir()):
        target.rmdir()


def launch(target: Path) -> None:
    subprocess.Popen(
        [str(application_executable(target))],
        cwd=target,
        env=external_environment(),
        start_new_session=not is_windows(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
