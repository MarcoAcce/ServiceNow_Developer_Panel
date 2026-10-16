import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal, NotRequired, TypedDict

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from core.acl.acl_controls import controls_of
from core.acl.acl_report import VerificationPayload, outcome_payload
from core.acl.acl_requests import verification_request
from core.acl.acl_verification import FIELD_OPERATIONS, Verification, evaluate, normalized_profiles
from core.app_paths import cache_path, data_directory
from storage.cache_query import run_script
from configuration.config_repository import ConfigRepository, Instance
from core.database_manager import RESPONSE_TIME_FORMAT, DatabaseError, DatabaseManager
from core.query_conditions import query_fields
from core.record_columns import ordered_columns
from core.request_model import (
    LIMIT_PARAMETER,
    MAXIMUM_LIMIT,
    QUERY_PARAMETER,
    RequestPart,
    RequestResult,
    RequestSpec,
    RequestTarget,
    ResultSection,
    requested_fields,
    table_parameters,
    tables_problem,
)
from core.request_types import MULTIPLE_TABLES, TABLE_RECORDS
from core.table_dictionary import (
    HIERARCHY_DEPTH,
    MAXIMUM_PARENTS,
    NAME_FIELD,
    FieldDescription,
    description_request,
    description_root,
    field_descriptions,
    hierarchy_request,
    matches_description,
    parent_names,
    table_chain,
    table_label,
)
from storage.response_cache import cache_names, cache_row_counts, read_cache_tables
from storage.response_repository import (
    ResponseCacheError,
    ResponseRepository,
    received_at_of,
    request_parts,
)
from services.sync_service import RequestFailure, SyncRequestService, mcp_target
from storage.table_export import CSV_FORMAT, XLSX_SUFFIX, export_csv, export_xlsx

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
    "Empty returns every record up to the limit. ServiceNow ignores conditions on fields the "
    "table does not have and returns the records unfiltered, so use the exact field names, as "
    "listed by describe_table: for example business rules in sys_script name their table in "
    "collection, not table."
)
FIELDS_DESCRIPTION: str = (
    "Field names passed as sysparm_fields. Dot-walking is allowed, for example caller_id.name. "
    "Empty returns every field."
)
ORDER_DESCRIPTION: str = "Field name passed as sysparm_order_by. Empty keeps the instance order."
LIMIT_DESCRIPTION: str = (
    "Maximum number of records to fetch, 100 when omitted. When exactly this many records come "
    "back, limit_reached is true and more records probably match: ask again with a higher "
    "limit. Above 10000 the request is split into several calls."
)
SAMPLE_DESCRIPTION: str = (
    "How many of the fetched records to return in this response. The full result stays in the "
    "local cache: use query_cache with the returned cache_name to read the rest."
)
REFRESH_DESCRIPTION: str = (
    "Skip the local cache and ask the instance again. Leave false to reuse a recent response."
)
TABLES_DESCRIPTION: str = (
    "The tables to fetch, each with its own query, fields and limit. Each table can appear "
    "only once: combine conditions with ^OR or IN instead."
)
ADDED_TABLES_DESCRIPTION: str = (
    "The tables to add, each with its own query, fields and limit. A table already in the "
    "cached response cannot be added again."
)
CACHE_NAME_DESCRIPTION: str = (
    "The cache_name returned by a request tool or by list_cached_responses."
)
TABLES_CACHE_NAME_DESCRIPTION: str = (
    "The cache_name returned by request_tables or add_tables, or listed by "
    "list_cached_responses with request_type multiple_tables."
)
SQL_DESCRIPTION: str = (
    "SQLite statements, separated by semicolons. Every cached ServiceNow table is a SQLite table "
    "with the same name and TEXT columns. Reference fields hold the sys_id of the referenced "
    "record: join on it, or request dot-walked fields such as group.name. Double-quote column "
    "names that contain dots or are SQL keywords, for example \"caller_id.name\", \"group\", "
    "\"order\" and \"when\". Only the last statement that returns rows is returned. The cache "
    "is read-only, TEMP tables are allowed."
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
    "One list of role names per user to check, for example [[\"itil\", \"snc_internal\"], "
    "[\"admin\"]]. List every role the user holds, including snc_internal and the roles "
    "contained in other roles: none is added automatically. A user passes a control when any "
    "of its roles is required by the control. Empty lists are ignored. Roles are compared "
    "locally and never sent to the instance."
)
DESCRIBED_FIELDS_DESCRIPTION: str = (
    "Only describe these fields, for example [\"state\", \"caller_id\"]. Empty describes every "
    "field of the table."
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
NOT_MULTIPLE_TABLES_MESSAGE: str = (
    "The cached response {name} was not made by request_tables, so tables cannot be added to "
    "it. Use request_tables to fetch every table you need into one cached response."
)
MISSING_INSTANCE_MESSAGE: str = (
    "The instance of the cached response {name} is no longer configured."
)
EXPIRED_NOTE: str = (
    "The cached response {old} is no longer current, so every table was requested again into "
    "{new}. Use {new} from now on."
)
LIMIT_WARNING: str = (
    "{table}: {count} records were fetched, as many as the limit, so more records probably "
    "match. Ask again with a higher limit to get them all."
)
MISSING_FIELDS_WARNING: str = (
    "{table}: the requested fields {fields} are not in the response: the table does not have "
    "them, or they cannot be read. describe_table lists the fields of the table."
)
IGNORED_CONDITIONS_WARNING: str = (
    "{table}: the query uses {fields}, which the returned records do not have. ServiceNow "
    "ignores conditions on unknown fields, so these records are probably not filtered. Check "
    "the field names with describe_table and ask again."
)
UNKNOWN_FIELDS_WARNING: str = "{table}: there is no active field named {fields}."
UNKNOWN_TABLE_MESSAGE: str = (
    "There is no table named {table} on {instance}, or the MCP user cannot read sys_db_object. "
    "Table names are lowercase, and the tables of a custom application start with its scope, "
    "for example x_acme_app_request. To find a table by its label, use request_table on "
    "sys_db_object with a query such as labelLIKErequest."
)

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
    limit: int
    limit_reached: bool
    columns: list[str]
    records: list[dict[str, str]]
    sample_truncated: bool
    warnings: list[str]


class SectionSummary(TypedDict):
    table: str
    row_count: int
    limit: int
    limit_reached: bool
    columns: list[str]


class TablesResult(TypedDict):
    cache_name: str
    source: str
    executed_at: str
    elapsed_ms: int
    row_count: int
    sections: list[SectionSummary]
    warnings: list[str]


class TableDescription(TypedDict):
    cache_name: str
    source: str
    executed_at: str
    table: str
    label: str
    extends: list[str]
    field_count: int
    fields: list[FieldDescription]
    warnings: list[str]


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
            parts = tuple(part_of_query(entry) for entry in tables)
            request = tables_request(self._target(instance), parts)
            result = self._send(request.refreshed() if refresh else request)
            return tables_result(result)

    def add_tables(
        self,
        cache_name: Annotated[str, Field(description=TABLES_CACHE_NAME_DESCRIPTION, min_length=1)],
        tables: Annotated[
            list[TableQuery], Field(description=ADDED_TABLES_DESCRIPTION, min_length=1)
        ],
    ) -> TablesResult:
        with local_failures():
            name = checked_cache_name(cache_name)
            row = self._responses.find(name)
            existing = request_parts(row) if row is not None else ()
            if row is None or str(row["request_type"]) != MULTIPLE_TABLES.key or not existing:
                raise ToolError(NOT_MULTIPLE_TABLES_MESSAGE.format(name=name))
            added = tuple(part_of_query(entry) for entry in tables)
            problem = tables_problem([part.table for part in existing + added])
            if problem:
                raise ToolError(problem)
            instance = self._instance_with_id(int(row["instance_id"]), name)
            request = tables_request(self._checked_target(instance), existing)
            stored = self._responses.load_named(request, name, received_at_of(row))
            if stored is None or not self._responses.is_current(stored):
                result = self._send(tables_request(request.target, existing + added).refreshed())
                note = EXPIRED_NOTE.format(old=name, new=result.cache_name)
                return tables_result(result, (note,))
            fetched = self._send(tables_request(request.target, added).transient())
            for section in fetched.sections:
                stored = self._extended(stored, section)
            return tables_result(stored)

    def describe_table(
        self,
        instance: InstanceName,
        table: TableName,
        fields: Annotated[tuple[str, ...], Field(description=DESCRIBED_FIELDS_DESCRIPTION)] = (),
        refresh: Refresh = False,
    ) -> TableDescription:
        with local_failures():
            target = self._target(instance)
            name = table.strip().lower()
            root = description_root(name, target)
            result = None if refresh else self._responses.load_latest(root)
            if result is None or not matches_description(result):
                request = description_request(self._hierarchy(name, target), target)
                result = self._send(request.refreshed())
            wanted = cleaned_names(fields)
            described = field_descriptions(result, wanted)
            warnings = sections_warnings(result)
            found = {field["name"] for field in described}
            missing = [field for field in wanted if field not in found]
            if missing:
                warnings.append(
                    UNKNOWN_FIELDS_WARNING.format(
                        table=result.table, fields=NAME_SEPARATOR.join(missing)
                    )
                )
            return TableDescription(
                cache_name=result.cache_name,
                source=result.source,
                executed_at=result.executed_at.strftime(RESPONSE_TIME_FORMAT),
                table=result.table,
                label=table_label(result),
                extends=list(table_chain(result)[1:]),
                field_count=len(described),
                fields=described,
                warnings=warnings,
            )

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
        return self._checked_target(self._instance(name))

    def _checked_target(self, instance: Instance) -> RequestTarget:
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

    def _hierarchy(self, table: str, target: RequestTarget) -> tuple[str, ...]:
        records = self._send(hierarchy_request(table, target)).records
        if not records:
            raise ToolError(UNKNOWN_TABLE_MESSAGE.format(table=table, instance=target.label))
        found = parent_names(records[0])
        parents = list(found)
        while len(found) == HIERARCHY_DEPTH and len(parents) < MAXIMUM_PARENTS:
            ancestors = self._send(hierarchy_request(found[-1], target)).records
            found = parent_names(ancestors[0]) if ancestors else ()
            parents.extend(found)
        return (records[0].get(NAME_FIELD, "").strip() or table, *parents)

    def _instance_with_id(self, instance_id: int, cache_name: str) -> Instance:
        for instance in self._repository.list_instances():
            if instance.id == instance_id:
                return instance
        raise ToolError(MISSING_INSTANCE_MESSAGE.format(name=cache_name))

    def _extended(self, result: RequestResult, section: ResultSection) -> RequestResult:
        try:
            return self._responses.extend(result, section)
        except ResponseCacheError as error:
            raise ToolError(LOCAL_FAILURE_MESSAGE.format(error=error)) from None

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


def tables_request(target: RequestTarget, parts: tuple[RequestPart, ...]) -> RequestSpec:
    return RequestSpec(
        request_type=MULTIPLE_TABLES,
        table="",
        parameters={},
        columns=(),
        target=target,
        parts=parts,
    )


def table_result(result: RequestResult, sample: int) -> TableResult:
    return TableResult(
        cache_name=result.cache_name,
        table=result.table,
        source=result.source,
        executed_at=result.executed_at.strftime(RESPONSE_TIME_FORMAT),
        elapsed_ms=result.elapsed_ms,
        row_count=len(result.records),
        limit=limit_of(result.parameters),
        limit_reached=limit_reached(result.parameters, result.records),
        columns=list(ordered_columns(result.columns, result.records)),
        records=result.records[:sample],
        sample_truncated=len(result.records) > sample,
        warnings=record_warnings(result.table, result.parameters, result.records),
    )


def tables_result(result: RequestResult, notes: Sequence[str] = ()) -> TablesResult:
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
                limit=limit_of(section.parameters),
                limit_reached=limit_reached(section.parameters, section.records),
                columns=list(ordered_columns(section.columns, section.records)),
            )
            for section in result.sections
        ],
        warnings=[*notes, *sections_warnings(result)],
    )


def sections_warnings(result: RequestResult) -> list[str]:
    warnings: list[str] = []
    for section in result.sections:
        warnings.extend(record_warnings(section.table, section.parameters, section.records))
    return warnings


def limit_of(parameters: dict[str, str]) -> int:
    value = parameters.get(LIMIT_PARAMETER, "").strip()
    return int(value) if value.isdigit() else 0


def limit_reached(parameters: dict[str, str], records: Sequence[dict[str, str]]) -> bool:
    limit = limit_of(parameters)
    return 0 < limit <= len(records)


def record_warnings(
    table: str, parameters: dict[str, str], records: Sequence[dict[str, str]]
) -> list[str]:
    warnings: list[str] = []
    if limit_reached(parameters, records):
        warnings.append(LIMIT_WARNING.format(table=table, count=len(records)))
    if not records:
        return warnings
    received = {name for record in records for name in record}
    fields = requested_fields(parameters)
    missing = [name for name in fields if name not in received]
    if missing:
        warnings.append(
            MISSING_FIELDS_WARNING.format(table=table, fields=NAME_SEPARATOR.join(missing))
        )
    if not fields:
        query = parameters.get(QUERY_PARAMETER, "")
        unknown = [name for name in query_fields(query) if name not in received]
        if unknown:
            warnings.append(
                IGNORED_CONDITIONS_WARNING.format(
                    table=table, fields=NAME_SEPARATOR.join(unknown)
                )
            )
    return warnings


def checked_cache_name(name: str) -> str:
    cleaned = name.strip()
    if cleaned not in cache_names():
        raise ToolError(UNKNOWN_CACHE_MESSAGE.format(name=name))
    return cleaned


def export_directory(cache_name: str, destination: str) -> Path:
    if destination.strip():
        return Path(destination.strip()).expanduser()
    return data_directory() / EXPORTS_DIRECTORY_NAME / Path(cache_name).stem
