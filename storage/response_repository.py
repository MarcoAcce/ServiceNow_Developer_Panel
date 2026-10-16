import json
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from core.database_manager import RESPONSE_TIME_FORMAT, DatabaseManager
from storage.response_cache import (
    CacheTable,
    append_cache_table,
    cache_exists,
    cache_name,
    cache_table,
    delete_cache,
    read_cache,
    read_cache_tables,
    write_cache_tables,
)
from core.request_model import (
    RequestPart,
    RequestResult,
    RequestSpec,
    ResultSection,
    part_of,
    requested_fields,
)

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
CURRENT_QUERY: str = (
    "SELECT id FROM response WHERE cache_name = ? AND received_at > ? LIMIT 1"
)
DETAILS_UPDATE: str = "UPDATE response SET request_details = ? WHERE cache_name = ?"
LATEST_QUERY: str = (
    "SELECT id, instance_id, request_type, received_at, request_details, cache_name "
    "FROM response WHERE instance_id = ? AND request_type = ? AND received_at > ? "
    "ORDER BY received_at DESC, id DESC"
)
NAMED_QUERY: str = (
    "SELECT id, instance_id, request_type, received_at, request_details, cache_name "
    "FROM response WHERE cache_name = ? ORDER BY received_at DESC, id DESC LIMIT 1"
)
TABLE_KEY: str = "table"
PARAMETERS_KEY: str = "parameters"
PARTS_KEY: str = "parts"
NO_RESPONSE_ID: int = 0
NO_ELAPSED_MS: int = 0
CACHE_STATUS_CODE: int = 200
CACHE_SOURCE: str = "local cache of {received_at}"
EXTEND_FAILED_MESSAGE: str = "the local cache of this response cannot be extended"


class ResponseCacheError(Exception):
    pass


def request_details(request: RequestSpec) -> str:
    details: dict[str, object] = {
        TABLE_KEY: request.table,
        PARAMETERS_KEY: request.parameters,
    }
    if request.parts:
        details[PARTS_KEY] = [
            {TABLE_KEY: part.table, PARAMETERS_KEY: part.parameters}
            for part in request.parts
        ]
    return json.dumps(details, separators=(",", ":"), sort_keys=True)


def stored_details(row: sqlite3.Row) -> dict[str, Any]:
    try:
        details = json.loads(str(row["request_details"]))
    except ValueError:
        return {}
    return details if isinstance(details, dict) else {}


def request_parts(row: sqlite3.Row) -> tuple[RequestPart, ...]:
    parts: list[RequestPart] = []
    for entry in stored_details(row).get(PARTS_KEY, ()):
        parameters = {
            str(name): str(value) for name, value in entry.get(PARAMETERS_KEY, {}).items()
        }
        parts.append(
            RequestPart(
                table=str(entry.get(TABLE_KEY, "")),
                parameters=parameters,
                columns=requested_fields(parameters),
            )
        )
    return tuple(parts)


def cache_tables_of(result: RequestResult) -> tuple[CacheTable, ...]:
    if result.sections:
        return tuple(
            cache_table(section.table, section.columns, section.records)
            for section in result.sections
        )
    return (cache_table(result.table, result.columns, result.records),)


@dataclass(frozen=True)
class CachedResponse:
    records: list[dict[str, str]]
    executed_at: datetime
    cache_name: str
    sections: tuple[ResultSection, ...] = ()


def cached_result(
    request: RequestSpec, cached: CachedResponse, elapsed_ms: int
) -> RequestResult:
    return RequestResult(
        request=request,
        records=cached.records,
        status_code=CACHE_STATUS_CODE,
        elapsed_ms=elapsed_ms,
        source=CACHE_SOURCE.format(
            received_at=cached.executed_at.strftime(RESPONSE_TIME_FORMAT)
        ),
        executed_at=cached.executed_at,
        sections=cached.sections,
        cache_name=cached.cache_name,
    )


class ResponseRepository:

    def __init__(self, database: DatabaseManager) -> None:
        self._database: DatabaseManager = database

    def named(self, result: RequestResult) -> RequestResult:
        instance = result.target.instance
        if instance is None or result.cache_name:
            return result
        name = cache_name(instance.name, result.request_type.key, result.executed_at)
        return replace(result, cache_name=name)

    def record(self, result: RequestResult) -> int:
        instance = result.target.instance
        name = result.cache_name
        if instance is None or not name:
            return NO_RESPONSE_ID
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
            write_cache_tables(name, cache_tables_of(result))
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
        name = str(row["cache_name"])
        if request.composite:
            return self._load_sections(request, name, received_at_of(row))
        records = read_cache(name)
        if records is None:
            return None
        return CachedResponse(
            records=records, executed_at=received_at_of(row), cache_name=name
        )

    def find(self, name: str) -> sqlite3.Row | None:
        return self._database.query_one(NAMED_QUERY, (name,))

    def load_named(
        self, request: RequestSpec, name: str, executed_at: datetime
    ) -> RequestResult | None:
        cached = self._load_sections(request, name, executed_at)
        if cached is None:
            return None
        return cached_result(request, cached, NO_ELAPSED_MS)

    def load_latest(self, request: RequestSpec) -> RequestResult | None:
        instance = request.target.instance
        if instance is None or request.skip_cache:
            return None
        rows = self._database.query(
            LATEST_QUERY,
            (instance.id, request.request_type.key, self._expiry_cutoff()),
        )
        for row in rows:
            details = stored_details(row)
            if details.get(TABLE_KEY) != request.table:
                continue
            if details.get(PARAMETERS_KEY) != request.parameters:
                continue
            parts = request_parts(row)
            if parts:
                name = str(row["cache_name"])
                return self.load_named(replace(request, parts=parts), name, received_at_of(row))
        return None

    def is_current(self, result: RequestResult) -> bool:
        name = result.cache_name
        if not cache_exists(name):
            return False
        row = self._database.query_one(CURRENT_QUERY, (name, self._expiry_cutoff()))
        return row is not None

    def extend(self, result: RequestResult, section: ResultSection) -> RequestResult:
        name = result.cache_name
        table = cache_table(section.table, section.columns, section.records)
        if not name or not append_cache_table(name, table):
            raise ResponseCacheError(EXTEND_FAILED_MESSAGE)
        request = result.request.extended(part_of(section))
        details = request_details(request)

        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(DETAILS_UPDATE, (details, name))

        self._database.write_and_wait(operation)
        return replace(
            result,
            request=request,
            records=result.records + section.records,
            sections=result.sections + (section,),
        )

    def _load_sections(
        self, request: RequestSpec, name: str, executed_at: datetime
    ) -> CachedResponse | None:
        tables = read_cache_tables(name)
        if tables is None:
            return None
        cached = {table.name: table for table in tables}
        sections: list[ResultSection] = []
        for part in request.parts:
            table = cached.get(part.table)
            if table is None:
                return None
            sections.append(
                ResultSection(
                    table=part.table,
                    parameters=part.parameters,
                    columns=table.columns,
                    records=table.records,
                )
            )
        return CachedResponse(
            records=[record for section in sections for record in section.records],
            executed_at=executed_at,
            cache_name=name,
            sections=tuple(sections),
        )

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
