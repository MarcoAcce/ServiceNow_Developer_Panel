from dataclasses import dataclass, field
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from request_types import RequestType

TABLE_API_PATH: str = "/api/now/table"


class ServiceConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class RequestSpec:
    request_type: RequestType
    table: str
    parameters: dict[str, str]
    columns: tuple[str, ...]

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
