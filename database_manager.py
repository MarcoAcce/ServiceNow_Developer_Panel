import queue
import sqlite3
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app_paths import database_path

THEME_SETTING: str = "theme"
CURRENT_INSTANCE_SETTING: str = "current_instance"
DEFAULT_THEME_KEY: str = "light"
SCHEMA_VERSION: int = 2
STARTUP_TIMEOUT_SECONDS: float = 15.0
WRITE_TIMEOUT_SECONDS: float = 15.0
SHUTDOWN_TIMEOUT_SECONDS: float = 15.0
BUSY_TIMEOUT_MS: int = 5000

WRITER_PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA synchronous = NORMAL",
    f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}",
)

READER_PRAGMAS: tuple[str, ...] = (
    "PRAGMA foreign_keys = ON",
    f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}",
)

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS instance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        address TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS authentication (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instance_id INTEGER NOT NULL
            REFERENCES instance (id) ON DELETE CASCADE ON UPDATE CASCADE,
        authentication_type TEXT NOT NULL,
        authentication_details TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS local_configuration (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        value TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_authentication_instance ON authentication (instance_id)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_authentication_active
        ON authentication (instance_id) WHERE active = 1
    """,
)

SEED_STATEMENTS: tuple[tuple[str, tuple[object, ...]], ...] = (
    (
        "INSERT OR IGNORE INTO local_configuration (id, name, value) VALUES (1, ?, ?)",
        (THEME_SETTING, DEFAULT_THEME_KEY),
    ),
)

Operation = Callable[[sqlite3.Connection], Any]


class DatabaseError(Exception):
    pass


@dataclass(frozen=True)
class _WriteTask:
    operation: Operation
    future: "Future[Any]"


class DatabaseManager:

    _singleton: "DatabaseManager | None" = None
    _singleton_lock: threading.Lock = threading.Lock()

    def __init__(self, path: Path | None = None) -> None:
        with DatabaseManager._singleton_lock:
            if DatabaseManager._singleton is not None:
                raise DatabaseError(
                    "the database manager is a singleton, use DatabaseManager.instance()"
                )
            DatabaseManager._singleton = self
        self._path: Path = path if path is not None else database_path()
        self._queue: "queue.Queue[_WriteTask | None]" = queue.Queue()
        self._local: threading.local = threading.local()
        self._startup: "Future[None]" = Future()
        self._closed: bool = False
        self._writer: threading.Thread = threading.Thread(
            target=self._process_queue, name="database-writer", daemon=True
        )
        self._writer.start()
        try:
            self._startup.result(timeout=STARTUP_TIMEOUT_SECONDS)
        except Exception as error:
            self.close()
            raise DatabaseError(f"the local database could not be opened: {error}") from error

    @classmethod
    def instance(cls, path: Path | None = None) -> "DatabaseManager":
        with cls._singleton_lock:
            existing = cls._singleton
        if existing is not None:
            return existing
        return cls(path)

    @property
    def path(self) -> Path:
        return self._path

    def write(self, operation: Operation) -> "Future[Any]":
        if self._closed:
            raise DatabaseError("the local database is closed")
        task = _WriteTask(operation=operation, future=Future())
        self._queue.put(task)
        return task.future

    def write_and_wait(self, operation: Operation, timeout: float = WRITE_TIMEOUT_SECONDS) -> Any:
        return self.write(operation).result(timeout=timeout)

    def execute(self, statement: str, parameters: Sequence[Any] = ()) -> "Future[int]":
        def operation(connection: sqlite3.Connection) -> int:
            return connection.execute(statement, parameters).rowcount

        return self.write(operation)

    def read(self, operation: Operation) -> Any:
        return operation(self._read_connection())

    def query(self, statement: str, parameters: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return self._read_connection().execute(statement, parameters).fetchall()

    def query_one(self, statement: str, parameters: Sequence[Any] = ()) -> sqlite3.Row | None:
        return self._read_connection().execute(statement, parameters).fetchone()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._queue.put(None)
            self._writer.join(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        self._close_read_connection()
        with DatabaseManager._singleton_lock:
            if DatabaseManager._singleton is self:
                DatabaseManager._singleton = None

    def _process_queue(self) -> None:
        try:
            connection = self._open_connection(WRITER_PRAGMAS)
            self._create_schema(connection)
        except BaseException as error:
            self._startup.set_exception(error)
            return
        self._startup.set_result(None)
        try:
            while True:
                task = self._queue.get()
                if task is None:
                    return
                self._run_task(connection, task)
        finally:
            self._checkpoint(connection)
            connection.close()

    def _run_task(self, connection: sqlite3.Connection, task: _WriteTask) -> None:
        if not task.future.set_running_or_notify_cancel():
            return
        try:
            with connection:
                result = task.operation(connection)
        except BaseException as error:
            task.future.set_exception(error)
        else:
            task.future.set_result(result)

    def _open_connection(self, pragmas: Sequence[str]) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=BUSY_TIMEOUT_MS / 1000)
        connection.row_factory = sqlite3.Row
        for pragma in pragmas:
            connection.execute(pragma)
        return connection

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        with connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            for statement, parameters in SEED_STATEMENTS:
                connection.execute(statement, parameters)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _read_connection(self) -> sqlite3.Connection:
        if self._closed:
            raise DatabaseError("the local database is closed")
        connection = getattr(self._local, "connection", None)
        if connection is None:
            connection = self._open_connection(READER_PRAGMAS)
            self._local.connection = connection
        return connection

    def _close_read_connection(self) -> None:
        connection = getattr(self._local, "connection", None)
        if connection is not None:
            self._local.connection = None
            connection.close()

    def _checkpoint(self, connection: sqlite3.Connection) -> None:
        try:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            return
