import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from storage.response_cache import text_of

MAXIMUM_ROWS: int = 2000
STATEMENT_END: str = ";"
READ_ONLY_MODE: str = "?mode=ro"
QUERY_TIMEOUT_SECONDS: float = 30.0
PROGRESS_INTERVAL: int = 10000
DENIED_ACTIONS: frozenset[int] = frozenset({sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH})
ALLOWED_PRAGMAS: frozenset[str] = frozenset(
    {
        "table_info",
        "table_xinfo",
        "table_list",
        "index_list",
        "index_info",
        "index_xinfo",
        "foreign_key_list",
    }
)
EMPTY_SCRIPT_MESSAGE: str = "write a query before running it"
MISSING_CACHE_MESSAGE: str = (
    "the local cache of this response is not available: refresh the request to build it again"
)


@dataclass(frozen=True)
class QueryOutcome:
    columns: tuple[str, ...]
    rows: list[tuple[str, ...]]
    truncated: bool
    changes: int

    @property
    def has_rows(self) -> bool:
        return bool(self.columns)


def split_statements(script: str) -> list[str]:
    statements: list[str] = []
    start: int = 0
    for index, character in enumerate(script):
        if character != STATEMENT_END:
            continue
        pending = script[start : index + 1]
        if not sqlite3.complete_statement(pending):
            continue
        start = index + 1
        if is_statement(pending):
            statements.append(pending.strip())
    remainder = script[start:]
    if is_statement(remainder):
        statements.append(remainder.strip())
    return statements


def is_statement(text: str) -> bool:
    return bool(text.strip().strip(STATEMENT_END).strip())


def run_script(path: Path, script: str, read_only: bool = False) -> QueryOutcome:
    statements = split_statements(script)
    if not statements:
        raise ValueError(EMPTY_SCRIPT_MESSAGE)
    if not path.is_file():
        raise ValueError(MISSING_CACHE_MESSAGE)
    connection = open_cache(path, read_only)
    try:
        return _run_statements(connection, statements)
    finally:
        connection.close()


def open_cache(path: Path, read_only: bool) -> sqlite3.Connection:
    if not read_only:
        return sqlite3.connect(path)
    connection = sqlite3.connect(f"{path.resolve().as_uri()}{READ_ONLY_MODE}", uri=True)
    connection.set_authorizer(sandbox_authorizer)
    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), PROGRESS_INTERVAL)
    return connection


def sandbox_authorizer(
    action: int,
    first: str | None,
    second: str | None,
    database: str | None,
    trigger: str | None,
) -> int:
    if action in DENIED_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_PRAGMA and (first or "").lower() not in ALLOWED_PRAGMAS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _run_statements(
    connection: sqlite3.Connection, statements: list[str]
) -> QueryOutcome:
    columns: tuple[str, ...] = ()
    rows: list[tuple[str, ...]] = []
    truncated: bool = False
    with connection:
        cursor = connection.cursor()
        for statement in statements:
            cursor.execute(statement)
            if cursor.description is None:
                continue
            columns = tuple(str(column[0]) for column in cursor.description)
            fetched = cursor.fetchmany(MAXIMUM_ROWS + 1)
            truncated = len(fetched) > MAXIMUM_ROWS
            rows = [
                tuple(text_of(value) for value in row) for row in fetched[:MAXIMUM_ROWS]
            ]
    return QueryOutcome(
        columns=columns,
        rows=rows,
        truncated=truncated,
        changes=connection.total_changes,
    )
