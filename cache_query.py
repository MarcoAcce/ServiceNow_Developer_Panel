import sqlite3
from dataclasses import dataclass
from pathlib import Path

from response_cache import text_of

MAXIMUM_ROWS: int = 2000
STATEMENT_END: str = ";"
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


def run_script(path: Path, script: str) -> QueryOutcome:
    statements = split_statements(script)
    if not statements:
        raise ValueError(EMPTY_SCRIPT_MESSAGE)
    if not path.is_file():
        raise ValueError(MISSING_CACHE_MESSAGE)
    connection = sqlite3.connect(path)
    try:
        return _run_statements(connection, statements)
    finally:
        connection.close()


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
