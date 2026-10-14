from dataclasses import dataclass, field
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from request_types import RequestType

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


class RequestService(QObject):

    name: str = "service"

    def send(self, request: RequestSpec) -> RequestCall:
        raise NotImplementedError

    def describe(self) -> str:
        return self.name
