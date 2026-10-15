import base64
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from urllib.parse import urlencode

from PySide6.QtCore import QObject, QTimer, Signal

from authentication_types import (
    BASIC_AUTHENTICATION,
    JWT_AUTHENTICATION,
    OAUTH_AUTHENTICATION,
    type_label,
)
from config_repository import Authentication, Instance
from request_types import RequestType

TABLE_API_PATH: str = "/api/now/table"
LIMIT_PARAMETER: str = "sysparm_limit"
OFFSET_PARAMETER: str = "sysparm_offset"
FIELDS_PARAMETER: str = "sysparm_fields"
ORDER_PARAMETER: str = "sysparm_order_by"
QUERY_PARAMETER: str = "sysparm_query"
NO_INSTANCE_LABEL: str = "no instance"
NO_AUTHENTICATION_LABEL: str = "no active authentication method"
DEFAULT_SCHEME: str = "https://"
SCHEME_SEPARATOR: str = "://"
AUTHORIZATION_HEADER: str = "Authorization"
BASIC_PREFIX: str = "Basic "
BEARER_PREFIX: str = "Bearer "
DEFAULT_HEADERS: dict[str, str] = {"Accept": "application/json"}
MISSING_INSTANCE_MESSAGE: str = "no instance selected for this request"
MISSING_AUTHENTICATION_MESSAGE: str = "the selected instance has no active authentication method"
UNREADABLE_AUTHENTICATION_MESSAGE: str = (
    "the stored authentication details cannot be read on this machine"
)
MISSING_ADDRESS_MESSAGE: str = "the selected instance has no address"
MISSING_TOKEN_MESSAGE: str = "the active authentication method has no usable token"
UNSUPPORTED_AUTHENTICATION_MESSAGE: str = "the authentication method {label} is not supported yet"
PART_ERROR_MESSAGE: str = "{table}: {message}"
PARAMETER_SEPARATOR: str = "&"
PARAMETER_TEMPLATE: str = "{name}={value}"
COMPOSITE_STATUS_CODE: int = 200


class ServiceConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class RequestTarget:
    instance: Instance | None = None
    authentication: Authentication | None = None

    @property
    def label(self) -> str:
        return self.instance.name if self.instance is not None else NO_INSTANCE_LABEL

    @property
    def address(self) -> str:
        return self.instance.address if self.instance is not None else ""

    @property
    def authentication_label(self) -> str:
        if self.authentication is None:
            return NO_AUTHENTICATION_LABEL
        return type_label(self.authentication.authentication_type)


@dataclass(frozen=True)
class RequestPart:
    table: str
    parameters: dict[str, str]
    columns: tuple[str, ...] = ()

    @property
    def query_string(self) -> str:
        return query_string(self.parameters)


@dataclass(frozen=True)
class RequestSpec:
    request_type: RequestType
    table: str
    parameters: dict[str, str]
    columns: tuple[str, ...]
    target: RequestTarget = field(default_factory=RequestTarget)
    skip_cache: bool = False
    stored: bool = True
    parts: tuple[RequestPart, ...] = ()

    def refreshed(self) -> "RequestSpec":
        return replace(self, skip_cache=True)

    def transient(self) -> "RequestSpec":
        return replace(self, skip_cache=True, stored=False)

    def extended(self, part: RequestPart) -> "RequestSpec":
        return replace(self, parts=self.parts + (part,))

    @property
    def composite(self) -> bool:
        return bool(self.parts)

    def part_specs(self) -> tuple["RequestSpec", ...]:
        return tuple(
            replace(
                self,
                table=part.table,
                parameters=part.parameters,
                columns=part.columns,
                parts=(),
            )
            for part in self.parts
        )

    @property
    def path(self) -> str:
        return f"{TABLE_API_PATH}/{self.table}" if self.table else TABLE_API_PATH

    @property
    def query_string(self) -> str:
        return query_string(self.parameters)


@dataclass(frozen=True)
class ResultSection:
    table: str
    parameters: dict[str, str]
    columns: tuple[str, ...]
    records: list[dict[str, str]]

    @property
    def query_string(self) -> str:
        return query_string(self.parameters)


@dataclass(frozen=True)
class RequestResult:
    request: RequestSpec
    records: list[dict[str, str]]
    status_code: int
    elapsed_ms: int
    source: str
    executed_at: datetime = field(default_factory=datetime.now)
    sections: tuple[ResultSection, ...] = ()
    cache_name: str = ""

    @property
    def request_type(self) -> RequestType:
        return self.request.request_type

    @property
    def table(self) -> str:
        return self.request.table

    @property
    def parameters(self) -> dict[str, str]:
        return self.request.parameters

    @property
    def columns(self) -> tuple[str, ...]:
        return self.request.columns

    @property
    def endpoint(self) -> str:
        return self.request.path

    @property
    def query_string(self) -> str:
        return self.request.query_string

    @property
    def target(self) -> RequestTarget:
        return self.request.target


@dataclass(frozen=True)
class RequestError:
    request: RequestSpec
    message: str
    status_code: int = 0


@dataclass(frozen=True)
class PreparedRequest:
    url: str
    headers: dict[str, str]


def query_string(parameters: dict[str, str]) -> str:
    return PARAMETER_SEPARATOR.join(
        PARAMETER_TEMPLATE.format(name=name, value=value)
        for name, value in parameters.items()
    )


def section_of(result: RequestResult) -> ResultSection:
    return ResultSection(
        table=result.table,
        parameters=result.parameters,
        columns=result.columns,
        records=result.records,
    )


def part_of(section: ResultSection) -> RequestPart:
    return RequestPart(
        table=section.table, parameters=section.parameters, columns=section.columns
    )


def instance_url(address: str) -> str:
    base = address.strip().rstrip("/")
    if not base:
        raise ServiceConfigurationError(MISSING_ADDRESS_MESSAGE)
    if SCHEME_SEPARATOR in base:
        return base
    return f"{DEFAULT_SCHEME}{base}"


def authentication_header(authentication: Authentication) -> str:
    if not authentication.readable:
        raise ServiceConfigurationError(UNREADABLE_AUTHENTICATION_MESSAGE)
    details = authentication.details
    if authentication.authentication_type == BASIC_AUTHENTICATION.key:
        pair = f"{details.get('username', '')}:{details.get('password', '')}"
        return BASIC_PREFIX + base64.b64encode(pair.encode("utf-8")).decode("ascii")
    if authentication.authentication_type == OAUTH_AUTHENTICATION.key:
        return BEARER_PREFIX + _required_detail(details, "access_token")
    if authentication.authentication_type == JWT_AUTHENTICATION.key:
        return BEARER_PREFIX + _required_detail(details, "token")
    raise ServiceConfigurationError(
        UNSUPPORTED_AUTHENTICATION_MESSAGE.format(
            label=type_label(authentication.authentication_type)
        )
    )


def prepare_request(
    request: RequestSpec, overrides: dict[str, str] | None = None
) -> PreparedRequest:
    instance = request.target.instance
    authentication = request.target.authentication
    if instance is None:
        raise ServiceConfigurationError(MISSING_INSTANCE_MESSAGE)
    if authentication is None:
        raise ServiceConfigurationError(MISSING_AUTHENTICATION_MESSAGE)
    headers = dict(DEFAULT_HEADERS)
    headers[AUTHORIZATION_HEADER] = authentication_header(authentication)
    parameters = dict(request.parameters)
    parameters.update(overrides or {})
    query = urlencode(parameters)
    url = f"{instance_url(instance.address)}{request.path}"
    return PreparedRequest(url=f"{url}?{query}" if query else url, headers=headers)


def _required_detail(details: dict[str, str], key: str) -> str:
    value = details.get(key, "").strip()
    if not value:
        raise ServiceConfigurationError(MISSING_TOKEN_MESSAGE)
    return value


class RequestCall(QObject):

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, request: RequestSpec, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.request: RequestSpec = request

    def is_running(self) -> bool:
        raise NotImplementedError

    def cancel(self) -> None:
        raise NotImplementedError


class FailedRequestCall(RequestCall):

    def __init__(self, request: RequestSpec, message: str, parent: QObject | None = None) -> None:
        super().__init__(request, parent)
        self._error: RequestError = RequestError(request=request, message=message)
        self._timer: QTimer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._emit_error)
        self._timer.start()

    def is_running(self) -> bool:
        return self._timer.isActive()

    def cancel(self) -> None:
        self._timer.stop()

    def _emit_error(self) -> None:
        self.failed.emit(self._error)


class CompositeRequestCall(RequestCall):

    def __init__(
        self,
        request: RequestSpec,
        service: "RequestService",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(request, parent)
        self._service: "RequestService" = service
        self._pending: list[RequestSpec] = list(request.part_specs())
        self._sections: list[ResultSection] = []
        self._status: int = COMPOSITE_STATUS_CODE
        self._started: float = time.monotonic()
        self._cancelled: bool = False
        self._call: RequestCall | None = None
        self._send_next()

    def is_running(self) -> bool:
        if self._cancelled:
            return False
        return bool(self._pending) or self._call is not None

    def cancel(self) -> None:
        self._cancelled = True
        self._pending.clear()
        self._release_call(cancel=True)

    def _send_next(self) -> None:
        if not self._pending:
            self._emit_result()
            return
        call = self._service.send(self._pending.pop(0))
        self._call = call
        call.succeeded.connect(self._on_succeeded)
        call.failed.connect(self._on_failed)

    def _on_succeeded(self, result: RequestResult) -> None:
        self._release_call()
        if self._cancelled:
            return
        self._status = result.status_code
        self._sections.append(section_of(result))
        self._send_next()

    def _on_failed(self, error: RequestError) -> None:
        self._release_call()
        if self._cancelled:
            return
        self._pending.clear()
        self.failed.emit(
            RequestError(
                request=self.request,
                message=PART_ERROR_MESSAGE.format(
                    table=error.request.table, message=error.message
                ),
                status_code=error.status_code,
            )
        )

    def _emit_result(self) -> None:
        sections = tuple(self._sections)
        self.succeeded.emit(
            RequestResult(
                request=self.request,
                records=[record for section in sections for record in section.records],
                status_code=self._status,
                elapsed_ms=int((time.monotonic() - self._started) * 1000),
                source=self.request.target.address,
                sections=sections,
            )
        )

    def _release_call(self, cancel: bool = False) -> None:
        call = self._call
        self._call = None
        if call is None:
            return
        if cancel:
            call.cancel()
        call.deleteLater()


class RequestService(QObject):

    name: str = "service"

    def send(self, request: RequestSpec) -> RequestCall:
        raise NotImplementedError

    def describe(self) -> str:
        return self.name
