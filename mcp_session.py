import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal, NotRequired, TypedDict

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from acl_controls import controls_of
from acl_report import VerificationPayload, outcome_payload
from acl_requests import verification_request
from acl_verification import FIELD_OPERATIONS, Verification, evaluate, normalized_profiles
from app_paths import cache_path, data_directory
from cache_query import run_script
from config_repository import ConfigRepository, Instance
from database_manager import RESPONSE_TIME_FORMAT, DatabaseError, DatabaseManager
from record_columns import ordered_columns
from request_model import (
    MAXIMUM_LIMIT,
    RequestPart,
    RequestResult,
    RequestSpec,
    RequestTarget,
    table_parameters,
    tables_problem,
)
from request_types import MULTIPLE_TABLES, TABLE_RECORDS
from response_cache import cache_names, cache_row_counts, read_cache_tables
from response_repository import ResponseRepository, received_at_of
from sync_service import RequestFailure, SyncRequestService, mcp_target
from table_export import CSV_FORMAT, XLSX_SUFFIX, export_csv, export_xlsx

TABLE_NAME_PATTERN: str = r"^[A-Za-z0-9_]+$"
FIELD_NAME_PATTERN: str = r"^[A-Za-z0-9_]*$"
DEFAULT_RECORD_LIMIT: int = 100
DEFAULT_SAMPLE_SIZE: int = 50
MAXIMUM_SAMPLE_SIZE: int = 1000
DEFAULT_RESPONSE_COUNT: int = 20
MAXIMUM_RESPONSE_COUNT: int = 200
EXPORTS_DIRECTORY_NAME: str = "exports"
NO_INSTANCES_LABEL: str = "none"
NAME_SEPARATOR: str = ", "

INSTANCE_DESCRIPTION: str = "Name of a configured instance, as returned by list_instances."
TABLE_DESCRIPTION: str = "ServiceNow table name, for example incident or sys_user."
QUERY_DESCRIPTION: str = (
    "Encoded query passed as sysparm_query, for example active=true^priority=1. "
    "Empty returns every record up to the limit."
)
FIELDS_DESCRIPTION: str = (
    "Field names passed as sysparm_fields. Dot-walking is allowed, for example caller_id.name. "
    "Empty returns every field."
)
ORDER_DESCRIPTION: str = "Field name passed as sysparm_order_by. Empty keeps the instance order."
LIMIT_DESCRIPTION: str = (
    "Maximum number of records to fetch. Above 10000 the request is split into several calls."
)
SAMPLE_DESCRIPTION: str = (
    "How many of the fetched records to return in this response. The full result stays in the "
    "local cache: use query_cache with the returned cache_name to read the rest."
)
REFRESH_DESCRIPTION: str = (
    "Skip the local cache and ask the instance again. Leave false to reuse a recent response."
)
TABLES_DESCRIPTION: str = "The tables to fetch, each with its own query, fields and limit."
CACHE_NAME_DESCRIPTION: str = (
    "The cache_name returned by a request tool or by list_cached_responses."
)
SQL_DESCRIPTION: str = (
    "SQLite statements, separated by semicolons. Every cached ServiceNow table is a SQLite table "
    "with the same name and TEXT columns; quote names containing dots, for example "
    "\"caller_id.name\". Only the last statement that returns rows is returned. The cache is "
    "read-only, TEMP tables are allowed."
)
FORMAT_DESCRIPTION: str = "csv writes one file per table, xlsx one workbook with a sheet per table."
DESTINATION_DESCRIPTION: str = (
    "Directory to write into. Empty uses the exports folder inside the panel data directory."
)
OPERATION_DESCRIPTION: str = "The operation to verify."
FIELD_DESCRIPTION: str = (
    "Optional field name, to verify field level controls. Only for the read and update operations."
)
PROFILES_DESCRIPTION: str = (
    "One list of role names per user to check, for example [[\"itil\"], [\"admin\"]]. A user "
    "passes a control when any of its roles is required by the control. Roles are compared "
    "locally and never sent to the instance."
)
RESPONSE_COUNT_DESCRIPTION: str = "Maximum number of cached responses to list, most recent first."

UNKNOWN_INSTANCE_MESSAGE: str = (
    "There is no instance named {name}. Configured instances: {available}."
)
NO_MCP_AUTHENTICATION_MESSAGE: str = (
    "The instance {name} has no active MCP authentication method. The user must add one under "
    "Configuration, MCP authentication, in the ServiceNow Developer Panel."
)
UNREADABLE_MCP_AUTHENTICATION_MESSAGE: str = (
    "The MCP authentication method of {name} cannot be decrypted here: it was saved on another "
    "machine or by another OS user. The MCP server must run as the same user, on the same "
    "machine, as the panel that saved it."
)
REQUEST_FAILED_MESSAGE: str = "The request to {instance} failed{status}: {message}"
STATUS_SUFFIX: str = " with HTTP status {status}"
UNKNOWN_CACHE_MESSAGE: str = (
    "There is no cached response named {name}. Use list_cached_responses to see the available ones."
)
FIELD_OPERATION_MESSAGE: str = "A field can only be verified for the read and update operations."
ROLES_REQUIRED_MESSAGE: str = "At least one profile with one role name is required."
QUERY_FAILED_MESSAGE: str = "The query failed: {error}"
LOCAL_FAILURE_MESSAGE: str = "The local database or cache could not be used: {error}"

Operation = Literal["create", "read", "update", "delete"]
ExportFormat = Literal["csv", "xlsx"]
InstanceName = Annotated[str, Field(description=INSTANCE_DESCRIPTION, min_length=1)]
TableName = Annotated[str, Field(description=TABLE_DESCRIPTION, pattern=TABLE_NAME_PATTERN)]
QueryText = Annotated[str, Field(description=QUERY_DESCRIPTION)]
FieldNames = Annotated[tuple[str, ...], Field(description=FIELDS_DESCRIPTION)]
OrderField = Annotated[str, Field(description=ORDER_DESCRIPTION)]
RecordLimit = Annotated[int, Field(description=LIMIT_DESCRIPTION, ge=1, le=MAXIMUM_LIMIT)]
Refresh = Annotated[bool, Field(description=REFRESH_DESCRIPTION)]
CacheName = Annotated[str, Field(description=CACHE_NAME_DESCRIPTION, min_length=1)]


class TableQuery(TypedDict):
    table: TableName
    query: NotRequired[QueryText]
    fields: NotRequired[FieldNames]
    order_by: NotRequired[OrderField]
    limit: NotRequired[RecordLimit]


class InstancePayload(TypedDict):
    name: str
    address: str
    mcp_authentication: bool
    authentication_type: str
    usable: bool


class TableResult(TypedDict):
    cache_name: str
    table: str
    source: str
    executed_at: str
    elapsed_ms: int
    row_count: int
    columns: list[str]
    records: list[dict[str, str]]
    truncated: bool


class SectionSummary(TypedDict):
    table: str
    row_count: int
    columns: list[str]


class TablesResult(TypedDict):
    cache_name: str
    source: str
    executed_at: str
    elapsed_ms: int
    row_count: int
    sections: list[SectionSummary]


class QueryResult(TypedDict):
    cache_name: str
    columns: list[str]
    rows: list[list[str]]
    row_count: int
    truncated: bool


class CachedTable(TypedDict):
    name: str
    rows: int


class ExportResult(TypedDict):
    cache_name: str
    format: str
    paths: list[str]
    tables: list[CachedTable]


class CachedResponsePayload(TypedDict):
    cache_name: str
    instance: str
    request_type: str
    received_at: str
    current: bool
    tables: list[CachedTable]


class AclResult(VerificationPayload):
    cache_name: str
    source: str


class McpSession:

    def __init__(self, database: DatabaseManager) -> None:
        self._database: DatabaseManager = database
        self._repository: ConfigRepository = ConfigRepository(database)
        self._responses: ResponseRepository = ResponseRepository(database)
        self._service: SyncRequestService = SyncRequestService(self._responses)

    def list_instances(self) -> list[InstancePayload]:
        with local_failures():
            payloads: list[InstancePayload] = []
            for instance in self._repository.list_instances():
                authentication = self._repository.active_mcp_authentication(instance.id)
                payloads.append(
                    InstancePayload(
                        name=instance.name,
                        address=instance.address,
                        mcp_authentication=authentication is not None,
                        authentication_type=(
                            authentication.authentication_type if authentication else ""
                        ),
                        usable=authentication is not None and authentication.readable,
                    )
                )
            return payloads

    def request_table(
        self,
        instance: InstanceName,
        table: TableName,
        query: QueryText = "",
        fields: FieldNames = (),
        order_by: OrderField = "",
        limit: RecordLimit = DEFAULT_RECORD_LIMIT,
        max_records: Annotated[
            int, Field(description=SAMPLE_DESCRIPTION, ge=0, le=MAXIMUM_SAMPLE_SIZE)
        ] = DEFAULT_SAMPLE_SIZE,
        refresh: Refresh = False,
    ) -> TableResult:
        with local_failures():
            columns = cleaned_names(fields)
            request = RequestSpec(
                request_type=TABLE_RECORDS,
                table=table,
                parameters=table_parameters(query.strip(), columns, order_by.strip(), limit),
                columns=columns,
                target=self._target(instance),
            )
            result = self._send(request.refreshed() if refresh else request)
            return table_result(result, max_records)

    def request_tables(
        self,
        instance: InstanceName,
        tables: Annotated[list[TableQuery], Field(description=TABLES_DESCRIPTION, min_length=1)],
        refresh: Refresh = False,
    ) -> TablesResult:
        with local_failures():
            problem = tables_problem([entry["table"] for entry in tables])
            if problem:
                raise ToolError(problem)
            request = RequestSpec(
                request_type=MULTIPLE_TABLES,
                table="",
                parameters={},
                columns=(),
                target=self._target(instance),
                parts=tuple(part_of_query(entry) for entry in tables),
            )
            result = self._send(request.refreshed() if refresh else request)
            return tables_result(result)

    def query_cache(
        self,
        cache_name: CacheName,
        sql: Annotated[str, Field(description=SQL_DESCRIPTION, min_length=1)],
    ) -> QueryResult:
        with local_failures():
            name = checked_cache_name(cache_name)
            try:
                outcome = run_script(cache_path(name), sql, read_only=True)
            except (ValueError, sqlite3.Error) as error:
                raise ToolError(QUERY_FAILED_MESSAGE.format(error=error)) from None
            return QueryResult(
                cache_name=name,
                columns=list(outcome.columns),
                rows=[list(row) for row in outcome.rows],
                row_count=len(outcome.rows),
                truncated=outcome.truncated,
            )

    def export_cache(
        self,
        cache_name: CacheName,
        format: Annotated[ExportFormat, Field(description=FORMAT_DESCRIPTION)] = CSV_FORMAT,
        destination: Annotated[str, Field(description=DESTINATION_DESCRIPTION)] = "",
    ) -> ExportResult:
        with local_failures():
            name = checked_cache_name(cache_name)
            tables = read_cache_tables(name) or []
            directory = export_directory(name, destination)
            if format == CSV_FORMAT:
                paths = export_csv(tables, directory)
            else:
                paths = [export_xlsx(tables, directory / f"{Path(name).stem}{XLSX_SUFFIX}")]
            return ExportResult(
                cache_name=name,
                format=format,
                paths=[str(path.resolve()) for path in paths],
                tables=[CachedTable(name=table.name, rows=len(table.records)) for table in tables],
            )

    def verify_acl(
        self,
        instance: InstanceName,
        table: TableName,
        operation: Annotated[Operation, Field(description=OPERATION_DESCRIPTION)],
        profiles: Annotated[
            list[list[str]], Field(description=PROFILES_DESCRIPTION, min_length=1)
        ],
        field: Annotated[
            str, Field(description=FIELD_DESCRIPTION, pattern=FIELD_NAME_PATTERN)
        ] = "",
        refresh: Refresh = False,
    ) -> AclResult:
        with local_failures():
            if field and operation not in FIELD_OPERATIONS:
                raise ToolError(FIELD_OPERATION_MESSAGE)
            roles = normalized_profiles(profiles)
            if not roles:
                raise ToolError(ROLES_REQUIRED_MESSAGE)
            verification = Verification(
                table=table, operation=operation, field=field, profiles=roles
            )
            request = verification_request(
                verification.names, verification.control_operation, self._target(instance)
            )
            result = self._send(request.refreshed() if refresh else request)
            payload = outcome_payload(evaluate(verification, controls_of(result)))
            return AclResult(**payload, cache_name=result.cache_name, source=result.source)

    def list_cached_responses(
        self,
        limit: Annotated[
            int, Field(description=RESPONSE_COUNT_DESCRIPTION, ge=1, le=MAXIMUM_RESPONSE_COUNT)
        ] = DEFAULT_RESPONSE_COUNT,
    ) -> list[CachedResponsePayload]:
        with local_failures():
            instances = {
                instance.id: instance.name for instance in self._repository.list_instances()
            }
            lifetime = timedelta(minutes=self._database.cache_lifetime_minutes())
            cutoff = datetime.now() - lifetime
            payloads: list[CachedResponsePayload] = []
            for row in self._responses.list_responses():
                if len(payloads) >= limit:
                    break
                name = str(row["cache_name"])
                counts = cache_row_counts(name)
                if counts is None:
                    continue
                received = received_at_of(row)
                payloads.append(
                    CachedResponsePayload(
                        cache_name=name,
                        instance=instances.get(int(row["instance_id"]), ""),
                        request_type=str(row["request_type"]),
                        received_at=received.strftime(RESPONSE_TIME_FORMAT),
                        current=received > cutoff,
                        tables=[CachedTable(name=key, rows=value) for key, value in counts.items()],
                    )
                )
            return payloads

    def _target(self, name: str) -> RequestTarget:
        instance = self._instance(name)
        target = mcp_target(self._repository, instance)
        authentication = target.authentication
        if authentication is None:
            raise ToolError(NO_MCP_AUTHENTICATION_MESSAGE.format(name=instance.name))
        if not authentication.readable:
            raise ToolError(UNREADABLE_MCP_AUTHENTICATION_MESSAGE.format(name=instance.name))
        return target

    def _instance(self, name: str) -> Instance:
        instances = self._repository.list_instances()
        wanted = name.strip().lower()
        for instance in instances:
            if instance.name.lower() == wanted:
                return instance
        available = NAME_SEPARATOR.join(instance.name for instance in instances)
        raise ToolError(
            UNKNOWN_INSTANCE_MESSAGE.format(name=name, available=available or NO_INSTANCES_LABEL)
        )

    def _send(self, request: RequestSpec) -> RequestResult:
        try:
            return self._service.send(request)
        except RequestFailure as failure:
            status = STATUS_SUFFIX.format(status=failure.status_code) if failure.status_code else ""
            raise ToolError(
                REQUEST_FAILED_MESSAGE.format(
                    instance=request.target.label, status=status, message=failure.message
                )
            ) from None


@contextmanager
def local_failures() -> Iterator[None]:
    try:
        yield
    except (sqlite3.Error, DatabaseError, OSError, TimeoutError) as error:
        raise ToolError(LOCAL_FAILURE_MESSAGE.format(error=error)) from None


def cleaned_names(names: Sequence[str]) -> tuple[str, ...]:
    return tuple(name.strip() for name in names if name.strip())


def part_of_query(entry: TableQuery) -> RequestPart:
    columns = cleaned_names(entry.get("fields", ()))
    return RequestPart(
        table=entry["table"],
        parameters=table_parameters(
            entry.get("query", "").strip(),
            columns,
            entry.get("order_by", "").strip(),
            entry.get("limit", DEFAULT_RECORD_LIMIT),
        ),
        columns=columns,
    )


def table_result(result: RequestResult, sample: int) -> TableResult:
    return TableResult(
        cache_name=result.cache_name,
        table=result.table,
        source=result.source,
        executed_at=result.executed_at.strftime(RESPONSE_TIME_FORMAT),
        elapsed_ms=result.elapsed_ms,
        row_count=len(result.records),
        columns=list(ordered_columns(result.columns, result.records)),
        records=result.records[:sample],
        truncated=len(result.records) > sample,
    )


def tables_result(result: RequestResult) -> TablesResult:
    return TablesResult(
        cache_name=result.cache_name,
        source=result.source,
        executed_at=result.executed_at.strftime(RESPONSE_TIME_FORMAT),
        elapsed_ms=result.elapsed_ms,
        row_count=len(result.records),
        sections=[
            SectionSummary(
                table=section.table,
                row_count=len(section.records),
                columns=list(ordered_columns(section.columns, section.records)),
            )
            for section in result.sections
        ],
    )


def checked_cache_name(name: str) -> str:
    cleaned = name.strip()
    if cleaned not in cache_names():
        raise ToolError(UNKNOWN_CACHE_MESSAGE.format(name=name))
    return cleaned


def export_directory(cache_name: str, destination: str) -> Path:
    if destination.strip():
        return Path(destination.strip()).expanduser()
    return data_directory() / EXPORTS_DIRECTORY_NAME / Path(cache_name).stem
