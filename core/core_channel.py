import getpass
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from multiprocessing.connection import AuthenticationError, Client, Connection
from pathlib import Path

from core.app_paths import (
    APPLICATION_DIRECTORY_NAME,
    data_directory,
    installation_directory,
    is_frozen,
)

CORE_PROTOCOL_VERSION: int = 1
HEADLESS_ARGUMENT: str = "--headless"
MCP_CLIENT: str = "mcp"
WINDOW_CLIENT: str = "window"
CLIENT_KINDS: frozenset[str] = frozenset({MCP_CLIENT, WINDOW_CLIENT})
KIND_KEY: str = "kind"
VERSION_KEY: str = "version"
ACCEPTED_KEY: str = "accepted"
MESSAGE_KEY: str = "message"
LOCK_FILE_NAME: str = "core.lock"
ENDPOINT_FILE_NAME: str = "core.endpoint"
ADDRESS_FIELD: str = "address"
KEY_FIELD: str = "key"
KEY_BYTES: int = 32
ENDPOINT_FILE_MODE: int = 0o600
SOCKET_DIRECTORY_MODE: int = 0o700
ADDRESS_HASH_LENGTH: int = 16
PIPE_FAMILY: str = "AF_PIPE"
SOCKET_FAMILY: str = "AF_UNIX"
PIPE_TEMPLATE: str = r"\\.\pipe\{name}"
SOCKET_SUFFIX: str = ".sock"
RUNTIME_DIRECTORY_VARIABLE: str = "XDG_RUNTIME_DIR"
APPLICATION_SCRIPT_NAME: str = "app.py"
WINDOWS_EXECUTABLE_SUFFIX: str = ".exe"
HANDSHAKE_TIMEOUT_SECONDS: float = 15.0
STARTUP_TIMEOUT_SECONDS: float = 30.0
RETRY_INTERVAL_SECONDS: float = 0.1
UNAVAILABLE_MESSAGE: str = "the ServiceNow Developer Panel core could not be reached"
NO_ANSWER_MESSAGE: str = "the ServiceNow Developer Panel core did not answer"
VERSION_MESSAGE: str = (
    "a different version of the ServiceNow Developer Panel core is running: close the "
    "application and the MCP clients connected to it, then try again"
)
UNKNOWN_CLIENT_MESSAGE: str = "unknown client kind {kind}"


@dataclass(frozen=True)
class Endpoint:
    address: str
    key: bytes


class CoreUnavailable(Exception):
    pass


class CoreRejected(Exception):
    pass


def is_windows() -> bool:
    return sys.platform.startswith("win")


def lock_path() -> Path:
    return data_directory() / LOCK_FILE_NAME


def endpoint_path() -> Path:
    return data_directory() / ENDPOINT_FILE_NAME


def address_family() -> str:
    return PIPE_FAMILY if is_windows() else SOCKET_FAMILY


def core_address() -> str:
    owner = f"{data_directory().resolve()}|{getpass.getuser()}"
    digest = hashlib.sha256(owner.encode("utf-8")).hexdigest()[:ADDRESS_HASH_LENGTH]
    name = f"{APPLICATION_DIRECTORY_NAME}-{digest}"
    if is_windows():
        return PIPE_TEMPLATE.format(name=name)
    return str(socket_directory() / f"{name}{SOCKET_SUFFIX}")


def socket_directory() -> Path:
    runtime = os.environ.get(RUNTIME_DIRECTORY_VARIABLE, "")
    if runtime and Path(runtime).is_dir():
        return Path(runtime)
    directory = Path(tempfile.gettempdir()) / f"{APPLICATION_DIRECTORY_NAME}-{os.getuid()}"
    directory.mkdir(mode=SOCKET_DIRECTORY_MODE, exist_ok=True)
    directory.chmod(SOCKET_DIRECTORY_MODE)
    return directory


def create_endpoint() -> Endpoint:
    endpoint = Endpoint(address=core_address(), key=secrets.token_bytes(KEY_BYTES))
    content = {ADDRESS_FIELD: endpoint.address, KEY_FIELD: endpoint.key.hex()}
    path = endpoint_path()
    path.unlink(missing_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, ENDPOINT_FILE_MODE)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encode_message(content))
    return endpoint


def read_endpoint() -> Endpoint | None:
    try:
        content = decode_message(endpoint_path().read_bytes())
        key = bytes.fromhex(str(content.get(KEY_FIELD, "")))
    except (OSError, ValueError):
        return None
    address = str(content.get(ADDRESS_FIELD, ""))
    if not address or len(key) != KEY_BYTES:
        return None
    return Endpoint(address=address, key=key)


def remove_endpoint() -> None:
    try:
        endpoint_path().unlink(missing_ok=True)
    except OSError:
        return


def encode_message(message: dict[str, object]) -> bytes:
    return json.dumps(message, separators=(",", ":")).encode("utf-8")


def decode_message(data: bytes) -> dict[str, object]:
    try:
        message = json.loads(data.decode("utf-8"))
    except ValueError:
        return {}
    return message if isinstance(message, dict) else {}


def connect(kind: str) -> Connection:
    endpoint = read_endpoint()
    if endpoint is None:
        raise CoreUnavailable(UNAVAILABLE_MESSAGE)
    try:
        connection = Client(endpoint.address, address_family(), authkey=endpoint.key)
    except (OSError, EOFError, AuthenticationError) as error:
        raise CoreUnavailable(UNAVAILABLE_MESSAGE) from error
    try:
        greet(connection, kind)
    except BaseException:
        connection.close()
        raise
    return connection


def greet(connection: Connection, kind: str) -> None:
    try:
        connection.send_bytes(
            encode_message({KIND_KEY: kind, VERSION_KEY: CORE_PROTOCOL_VERSION})
        )
        if not connection.poll(HANDSHAKE_TIMEOUT_SECONDS):
            raise CoreUnavailable(NO_ANSWER_MESSAGE)
        answer = decode_message(connection.recv_bytes())
    except (OSError, EOFError) as error:
        raise CoreUnavailable(UNAVAILABLE_MESSAGE) from error
    if answer.get(ACCEPTED_KEY) is not True:
        raise CoreRejected(str(answer.get(MESSAGE_KEY) or UNAVAILABLE_MESSAGE))


def open_core(kind: str, timeout: float = STARTUP_TIMEOUT_SECONDS) -> Connection:
    deadline = time.monotonic() + timeout
    process: subprocess.Popen[bytes] | None = None
    while True:
        try:
            return connect(kind)
        except CoreUnavailable:
            if time.monotonic() > deadline:
                raise
        if process is None or process.poll() is not None:
            process = start_core()
        time.sleep(RETRY_INTERVAL_SECONDS)


def core_command() -> list[str]:
    if is_frozen():
        suffix = WINDOWS_EXECUTABLE_SUFFIX if is_windows() else ""
        executable = installation_directory() / f"{APPLICATION_DIRECTORY_NAME}{suffix}"
        return [str(executable), HEADLESS_ARGUMENT]
    script = installation_directory() / APPLICATION_SCRIPT_NAME
    return [sys.executable, str(script), HEADLESS_ARGUMENT]


def start_core() -> subprocess.Popen[bytes]:
    if not is_windows():
        return detached_process(start_new_session=True)
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        return detached_process(creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB)
    except OSError:
        return detached_process(creationflags=flags)


def detached_process(
    creationflags: int = 0, start_new_session: bool = False
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        core_command(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(installation_directory()),
        creationflags=creationflags,
        start_new_session=start_new_session,
    )
