import hashlib
import re
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.app_paths import cache_directory, cache_path
from core.record_columns import ordered_columns

CACHE_SUFFIX: str = ".db"
NAME_SEPARATOR: str = "_"
HASH_LENGTH: int = 12
UNNAMED_PATTERN: re.Pattern[str] = re.compile(r"[^A-Za-z0-9]+")
DEFAULT_NAME: str = "unnamed"
DEFAULT_TABLE_NAME: str = "response"
DEFAULT_COLUMN_NAME: str = "value"
TABLE_NAMES_QUERY: str = "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"


@dataclass(frozen=True)
class CacheTable:
    name: str
    columns: tuple[str, ...]
    records: list[dict[str, str]]


def slug(value: str) -> str:
    cleaned = UNNAMED_PATTERN.sub(NAME_SEPARATOR, value).strip(NAME_SEPARATOR).lower()
    return cleaned or DEFAULT_NAME


def cache_name(instance: str, request_type: str, executed_at: datetime) -> str:
    digest = hashlib.sha256(executed_at.isoformat().encode("utf-8")).hexdigest()
    parts = (slug(instance), slug(request_type), digest[:HASH_LENGTH])
    return f"{NAME_SEPARATOR.join(parts)}{CACHE_SUFFIX}"


def column_names(
    columns: Sequence[str], records: Sequence[dict[str, str]]
) -> tuple[str, ...]:
    names = ordered_columns(columns, records)
    return names if names else (DEFAULT_COLUMN_NAME,)


def cache_table(
    table: str, columns: Sequence[str], records: Sequence[dict[str, str]]
) -> CacheTable:
    return CacheTable(
        name=table.strip() or DEFAULT_TABLE_NAME,
        columns=column_names(columns, records),
        records=list(records),
    )


def write_cache(
    name: str, table: str, columns: Sequence[str], records: Sequence[dict[str, str]]
) -> Path:
    return write_cache_tables(name, (cache_table(table, columns, records),))


def write_cache_tables(name: str, tables: Sequence[CacheTable]) -> Path:
    path = cache_path(name)
    connection = sqlite3.connect(path)
    try:
        with connection:
            for table in tables:
                fill_table(connection, table)
    finally:
        connection.close()
    return path


def append_cache_table(name: str, table: CacheTable) -> bool:
    if not cache_exists(name):
        return False
    connection = sqlite3.connect(cache_path(name))
    try:
        with connection:
            fill_table(connection, table)
    finally:
        connection.close()
    return True


def fill_table(connection: sqlite3.Connection, table: CacheTable) -> None:
    names = table.columns or (DEFAULT_COLUMN_NAME,)
    connection.execute(create_statement(table.name, names))
    connection.executemany(
        insert_statement(table.name, names),
        [tuple(record.get(column, "") for column in names) for record in table.records],
    )


def cache_exists(name: str) -> bool:
    return bool(name) and cache_path(name).is_file()


def read_cache(name: str) -> list[dict[str, str]] | None:
    tables = read_cache_tables(name)
    if not tables:
        return None
    return tables[0].records


def read_cache_tables(name: str) -> list[CacheTable] | None:
    if not cache_exists(name):
        return None
    connection = sqlite3.connect(cache_path(name))
    try:
        names = [str(row[0]) for row in connection.execute(TABLE_NAMES_QUERY).fetchall()]
        return [read_table(connection, table_name) for table_name in names]
    finally:
        connection.close()


def cache_row_counts(name: str) -> dict[str, int] | None:
    if not cache_exists(name):
        return None
    connection = sqlite3.connect(cache_path(name))
    try:
        names = [str(row[0]) for row in connection.execute(TABLE_NAMES_QUERY).fetchall()]
        return {table_name: count_rows(connection, table_name) for table_name in names}
    finally:
        connection.close()


def count_rows(connection: sqlite3.Connection, name: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) FROM {quoted(name)}").fetchone()
    return int(row[0]) if row is not None else 0


def read_table(connection: sqlite3.Connection, name: str) -> CacheTable:
    cursor = connection.execute(f"SELECT * FROM {quoted(name)}")
    columns = tuple(str(column[0]) for column in cursor.description or ())
    records = [
        {column: text_of(value) for column, value in zip(columns, row)}
        for row in cursor.fetchall()
    ]
    return CacheTable(name=name, columns=columns, records=records)


def text_of(value: object) -> str:
    return "" if value is None else str(value)


def delete_cache(name: str) -> bool:
    if not name:
        return False
    try:
        cache_path(name).unlink(missing_ok=True)
    except OSError:
        return False
    return True


def cache_names() -> tuple[str, ...]:
    try:
        entries = sorted(cache_directory().glob(f"*{CACHE_SUFFIX}"))
    except OSError:
        return ()
    return tuple(entry.name for entry in entries if entry.is_file())


def create_statement(table: str, names: Iterable[str]) -> str:
    columns = ", ".join(f"{quoted(name)} TEXT" for name in names)
    return f"CREATE TABLE IF NOT EXISTS {quoted(table)} ({columns})"


def insert_statement(table: str, names: Sequence[str]) -> str:
    columns = ", ".join(quoted(name) for name in names)
    placeholders = ", ".join("?" for _ in names)
    return f"INSERT INTO {quoted(table)} ({columns}) VALUES ({placeholders})"


def quoted(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'
