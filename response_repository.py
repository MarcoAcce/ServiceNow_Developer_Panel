import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from database_manager import RESPONSE_TIME_FORMAT, DatabaseManager
from response_cache import cache_name, delete_cache, read_cache, write_cache
from service import RequestResult, RequestSpec

RESPONSE_INSERT: str = (
    "INSERT INTO response "
    "(instance_id, request_type, received_at, request_details, cache_name) "
    "VALUES (?, ?, ?, ?, ?)"
)
RESPONSE_QUERY: str = (
    "SELECT id, instance_id, request_type, received_at, request_details, cache_name "
    "FROM response ORDER BY received_at DESC, id DESC"
)
RESPONSE_DELETE: str = "DELETE FROM response WHERE id = ?"
MATCH_QUERY: str = (
    "SELECT id, received_at, cache_name FROM response "
    "WHERE instance_id = ? AND request_type = ? AND request_details = ? AND received_at > ? "
    "ORDER BY received_at DESC, id DESC LIMIT 1"
)
TABLE_KEY: str = "table"
PARAMETERS_KEY: str = "parameters"
NO_RESPONSE_ID: int = 0


def request_details(request: RequestSpec) -> str:
    details = {TABLE_KEY: request.table, PARAMETERS_KEY: request.parameters}
    return json.dumps(details, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class CachedResponse:
    records: list[dict[str, str]]
    executed_at: datetime


class ResponseRepository:

    def __init__(self, database: DatabaseManager) -> None:
        self._database: DatabaseManager = database

    def record(self, result: RequestResult) -> int:
        instance = result.target.instance
        if instance is None:
            return NO_RESPONSE_ID
        name = cache_name(instance.name, result.request_type.key, result.executed_at)
        parameters = (
            instance.id,
            result.request_type.key,
            result.executed_at.strftime(RESPONSE_TIME_FORMAT),
            request_details(result.request),
            name,
        )

        def operation(connection: sqlite3.Connection) -> int:
            cursor = connection.execute(RESPONSE_INSERT, parameters)
            return int(cursor.lastrowid or NO_RESPONSE_ID)

        response_id = int(self._database.write_and_wait(operation))
        delete_cache(name)
        try:
            write_cache(name, result.table, result.columns, result.records)
        except (OSError, sqlite3.Error):
            self.delete(response_id)
            raise
        return response_id

    def load_cached(self, request: RequestSpec) -> CachedResponse | None:
        instance = request.target.instance
        if instance is None or request.skip_cache:
            return None
        row = self._database.query_one(
            MATCH_QUERY,
            (
                instance.id,
                request.request_type.key,
                request_details(request),
                self._expiry_cutoff(),
            ),
        )
        if row is None:
            return None
        records = read_cache(str(row["cache_name"]))
        if records is None:
            return None
        return CachedResponse(records=records, executed_at=received_at_of(row))

    def delete(self, response_id: int) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(RESPONSE_DELETE, (response_id,))

        self._database.write_and_wait(operation)

    def list_responses(self) -> list[sqlite3.Row]:
        return self._database.query(RESPONSE_QUERY)

    def _expiry_cutoff(self) -> str:
        lifetime = timedelta(minutes=self._database.cache_lifetime_minutes())
        return (datetime.now() - lifetime).strftime(RESPONSE_TIME_FORMAT)


def received_at_of(row: sqlite3.Row) -> datetime:
    try:
        return datetime.strptime(str(row["received_at"]), RESPONSE_TIME_FORMAT)
    except ValueError:
        return datetime.now()
