import sqlite3
from datetime import datetime

from database_manager import DatabaseManager

HINT_TIME_FORMAT: str = "%Y-%m-%d %H:%M:%S.%f"
HINT_UPDATE: str = (
    "UPDATE request_suggestions SET last_sent_date = ? "
    "WHERE request_type = ? AND target_table_name = ? "
    "AND IFNULL(target_field_name, '') = IFNULL(?, '')"
)
HINT_INSERT: str = (
    "INSERT INTO request_suggestions "
    "(request_type, target_table_name, target_field_name, last_sent_date) "
    "VALUES (?, ?, ?, ?)"
)
CLEAR_STATEMENT: str = "DELETE FROM request_suggestions"
TABLE_QUERY: str = (
    "SELECT target_table_name AS name, "
    "MAX(CASE WHEN request_type = ? THEN 1 ELSE 0 END) AS matching, "
    "MAX(last_sent_date) AS last_sent "
    "FROM request_suggestions WHERE target_table_name <> '' "
    "GROUP BY target_table_name ORDER BY matching DESC, last_sent DESC LIMIT ?"
)
FIELD_QUERY: str = (
    "SELECT target_field_name AS name, "
    "MAX(CASE WHEN request_type = ? THEN 1 ELSE 0 END) AS matching, "
    "MAX(last_sent_date) AS last_sent "
    "FROM request_suggestions "
    "WHERE target_table_name = ? COLLATE NOCASE "
    "AND IFNULL(target_field_name, '') <> '' "
    "GROUP BY target_field_name ORDER BY matching DESC, last_sent DESC LIMIT ?"
)


class RequestHintRepository:

    def __init__(self, database: DatabaseManager) -> None:
        self._database: DatabaseManager = database

    def record(self, request_type: str, table: str, field: str | None = None) -> None:
        table_name = table.strip()
        if not table_name:
            return
        field_name = field.strip() if field else ""
        sent_at = datetime.now().strftime(HINT_TIME_FORMAT)

        def operation(connection: sqlite3.Connection) -> None:
            updated = connection.execute(
                HINT_UPDATE, (sent_at, request_type, table_name, field_name or None)
            ).rowcount
            if not updated:
                connection.execute(
                    HINT_INSERT, (request_type, table_name, field_name or None, sent_at)
                )

        self._database.write(operation)

    def clear(self) -> int:
        def operation(connection: sqlite3.Connection) -> int:
            return connection.execute(CLEAR_STATEMENT).rowcount

        return int(self._database.write_and_wait(operation))

    def table_names(self, request_type: str) -> list[str]:
        return self._names(TABLE_QUERY, (request_type, self._count()))

    def field_names(self, request_type: str, table: str) -> list[str]:
        table_name = table.strip()
        if not table_name:
            return []
        return self._names(FIELD_QUERY, (request_type, table_name, self._count()))

    def _count(self) -> int:
        return self._database.suggestion_count()

    def _names(self, statement: str, parameters: tuple[object, ...]) -> list[str]:
        return [str(row["name"]) for row in self._database.query(statement, parameters)]
