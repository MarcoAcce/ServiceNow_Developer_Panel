from dataclasses import dataclass, field
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from authentication_types import type_label
from config_repository import Authentication, Instance
from request_types import RequestType

TABLE_API_PATH: str = "/api/now/table"
NO_INSTANCE_LABEL: str = "no instance"
NO_AUTHENTICATION_LABEL: str = "no active authentication method"


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
class RequestSpec:
    request_type: RequestType
    table: str
    parameters: dict[str, str]
    columns: tuple[str, ...]
    target: RequestTarget = field(default_factory=RequestTarget)

    @property
    def path(self) -> str:
        return f"{TABLE_API_PATH}/{self.table}" if self.table else TABLE_API_PATH

    @property
    def query_string(self) -> str:
        return "&".join(f"{name}={value}" for name, value in self.parameters.items())


@dataclass(frozen=True)
class RequestResult:
    request: RequestSpec
    records: list[dict[str, str]]
    status_code: int
    elapsed_ms: int
    source: str
    executed_at: datetime = field(default_factory=datetime.now)

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


class RequestService(QObject):

    name: str = "service"

    def send(self, request: RequestSpec) -> RequestCall:
        raise NotImplementedError

    def describe(self) -> str:
        return self.name
