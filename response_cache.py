import hashlib
import re
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path

from app_paths import cache_directory, cache_path
from record_columns import ordered_columns

CACHE_SUFFIX: str = ".db"
NAME_SEPARATOR: str = "_"
HASH_LENGTH: int = 12
UNNAMED_PATTERN: re.Pattern[str] = re.compile(r"[^A-Za-z0-9]+")
DEFAULT_NAME: str = "unnamed"
DEFAULT_TABLE_NAME: str = "response"
DEFAULT_COLUMN_NAME: str = "value"
TABLE_NAME_QUERY: str = "SELECT name FROM sqlite_master WHERE type = 'table' LIMIT 1"


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


def write_cache(
    name: str, table: str, columns: Sequence[str], records: Sequence[dict[str, str]]
) -> Path:
    path = cache_path(name)
    table_name = table.strip() or DEFAULT_TABLE_NAME
    names = column_names(columns, records)
    connection = sqlite3.connect(path)
    try:
        with connection:
            connection.execute(create_statement(table_name, names))
            connection.executemany(
                insert_statement(table_name, names),
                [tuple(record.get(name, "") for name in names) for record in records],
            )
    finally:
        connection.close()
    return path


def read_cache(name: str) -> list[dict[str, str]] | None:
    if not name:
        return None
    path = cache_path(name)
    if not path.is_file():
        return None
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        table = connection.execute(TABLE_NAME_QUERY).fetchone()
        if table is None:
            return None
        rows = connection.execute(f"SELECT * FROM {quoted(str(table[0]))}").fetchall()
    finally:
        connection.close()
    return [{column: text_of(row[column]) for column in row.keys()} for row in rows]


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
