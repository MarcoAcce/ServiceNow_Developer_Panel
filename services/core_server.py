import threading
from collections.abc import Callable
from multiprocessing.connection import AuthenticationError, Connection, Listener
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.core_channel import (
    ACCEPTED_KEY,
    CLIENT_KINDS,
    CORE_PROTOCOL_VERSION,
    HANDSHAKE_TIMEOUT_SECONDS,
    KIND_KEY,
    MCP_CLIENT,
    MESSAGE_KEY,
    UNKNOWN_CLIENT_MESSAGE,
    VERSION_KEY,
    VERSION_MESSAGE,
    WINDOW_CLIENT,
    address_family,
    create_endpoint,
    decode_message,
    encode_message,
    is_windows,
    remove_endpoint,
)

ACCEPT_THREAD_NAME: str = "core-accept"
CLIENT_THREAD_NAME: str = "core-client"

ConnectionHandler = Callable[[Connection], None]


class CoreServer(QObject):

    windowRequested = Signal()
    clientsChanged = Signal(int)

    def __init__(self, serve_mcp: ConnectionHandler, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._serve_mcp: ConnectionHandler = serve_mcp
        self._listener: Listener | None = None
        self._lock: threading.Lock = threading.Lock()
        self._clients: int = 0
        self._closed: bool = False

    @property
    def client_count(self) -> int:
        with self._lock:
            return self._clients

    def start(self) -> None:
        endpoint = create_endpoint()
        if not is_windows():
            Path(endpoint.address).unlink(missing_ok=True)
        self._listener = Listener(endpoint.address, address_family(), authkey=endpoint.key)
        threading.Thread(target=self._accept, name=ACCEPT_THREAD_NAME, daemon=True).start()

    def close(self) -> None:
        self._closed = True
        listener = self._listener
        self._listener = None
        remove_endpoint()
        if listener is not None:
            listener.close()

    def _accept(self) -> None:
        while not self._closed:
            listener = self._listener
            if listener is None:
                return
            try:
                connection = listener.accept()
            except (AuthenticationError, EOFError):
                continue
            except OSError:
                if self._closed:
                    return
                continue
            threading.Thread(
                target=self._handle,
                args=(connection,),
                name=CLIENT_THREAD_NAME,
                daemon=True,
            ).start()

    def _handle(self, connection: Connection) -> None:
        try:
            kind = self._greet(connection)
            if kind == WINDOW_CLIENT:
                self.windowRequested.emit()
            elif kind == MCP_CLIENT:
                self._run_client(connection)
        except (OSError, EOFError):
            return
        finally:
            connection.close()

    def _greet(self, connection: Connection) -> str:
        if not connection.poll(HANDSHAKE_TIMEOUT_SECONDS):
            return ""
        hello = decode_message(connection.recv_bytes())
        kind = str(hello.get(KIND_KEY, ""))
        problem = ""
        if hello.get(VERSION_KEY) != CORE_PROTOCOL_VERSION:
            problem = VERSION_MESSAGE
        elif kind not in CLIENT_KINDS:
            problem = UNKNOWN_CLIENT_MESSAGE.format(kind=kind)
        connection.send_bytes(encode_message({ACCEPTED_KEY: not problem, MESSAGE_KEY: problem}))
        return "" if problem else kind

    def _run_client(self, connection: Connection) -> None:
        self._change_clients(1)
        try:
            self._serve_mcp(connection)
        finally:
            self._change_clients(-1)

    def _change_clients(self, delta: int) -> None:
        with self._lock:
            self._clients += delta
            count = self._clients
        self.clientsChanged.emit(count)
