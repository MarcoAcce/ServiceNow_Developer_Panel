import time

from PySide6.QtCore import QObject, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from services.http_payload import (
    HTTP_ERROR_STATUS,
    MAXIMUM_PAGE_SIZE,
    REQUEST_TIMEOUT_MS,
    error_message,
    has_more,
    is_paged,
    page_overrides,
    page_size,
    parameter_value,
    record_of,
    response_document,
    response_records,
    value_of,
)
from services.service import (
    LIMIT_PARAMETER,
    OFFSET_PARAMETER,
    CompositeRequestCall,
    FailedRequestCall,
    PreparedRequest,
    RequestCall,
    RequestError,
    RequestResult,
    RequestService,
    RequestSpec,
    ServiceConfigurationError,
    prepare_request,
)

__all__ = [
    "HTTP_ERROR_STATUS",
    "MAXIMUM_PAGE_SIZE",
    "REQUEST_TIMEOUT_MS",
    "HttpRequestCall",
    "HttpRequestService",
    "error_message",
    "network_request",
    "parameter_value",
    "record_of",
    "response_document",
    "response_records",
    "value_of",
]

SERVICE_NAME: str = "ServiceNow instance"
SERVICE_DESCRIPTION: str = "a live call to the selected instance"


class HttpRequestCall(RequestCall):

    def __init__(
        self,
        request: RequestSpec,
        manager: QNetworkAccessManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(request, parent)
        self._manager: QNetworkAccessManager = manager
        self._cancelled: bool = False
        self._started: float = time.monotonic()
        self._records: list[dict[str, str]] = []
        self._wanted: int = parameter_value(request, LIMIT_PARAMETER)
        self._offset: int = parameter_value(request, OFFSET_PARAMETER)
        self._page_size: int = 0
        self._reply: QNetworkReply | None = None
        self._fetch_page()

    def is_running(self) -> bool:
        return self._reply is not None and self._reply.isRunning()

    def cancel(self) -> None:
        self._cancelled = True
        if self._reply is not None:
            self._reply.abort()

    def _fetch_page(self) -> None:
        try:
            prepared = prepare_request(self.request, self._page_parameters())
        except ServiceConfigurationError as error:
            self._emit_error(str(error), 0)
            return
        self._reply = self._manager.get(network_request(prepared))
        self._reply.finished.connect(self._on_finished)

    def _page_parameters(self) -> dict[str, str]:
        if not is_paged(self._wanted):
            return {}
        self._page_size = page_size(self._wanted, len(self._records))
        return page_overrides(self._page_size, self._offset, len(self._records))

    def _on_finished(self) -> None:
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        payload = bytes(reply.readAll().data())
        status = int(reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) or 0)
        failed = reply.error() != QNetworkReply.NetworkError.NoError
        reason = reply.errorString()
        reply.deleteLater()
        if self._cancelled:
            return
        if failed or status >= HTTP_ERROR_STATUS:
            self._emit_error(error_message(payload, reason, status), status)
            return
        try:
            records = response_records(payload)
        except ValueError as error:
            self._emit_error(str(error), status)
            return
        self._records.extend(records)
        if self._has_more(len(records)):
            self._fetch_page()
            return
        self.succeeded.emit(
            RequestResult(
                request=self.request,
                records=self._records,
                status_code=status,
                elapsed_ms=self._elapsed_ms(),
                source=self.request.target.address,
            )
        )

    def _has_more(self, received: int) -> bool:
        return has_more(self._wanted, len(self._records), received, self._page_size)

    def _emit_error(self, message: str, status: int) -> None:
        self.failed.emit(
            RequestError(request=self.request, message=message, status_code=status)
        )

    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self._started) * 1000)


class HttpRequestService(RequestService):

    name: str = SERVICE_NAME

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager: QNetworkAccessManager = QNetworkAccessManager(self)

    def send(self, request: RequestSpec) -> RequestCall:
        if request.composite:
            return CompositeRequestCall(request, self, self)
        try:
            prepare_request(request)
        except ServiceConfigurationError as error:
            return FailedRequestCall(request, str(error), self)
        return HttpRequestCall(request, self._manager, self)

    def describe(self) -> str:
        return SERVICE_DESCRIPTION


def network_request(prepared: PreparedRequest) -> QNetworkRequest:
    request = QNetworkRequest(QUrl(prepared.url))
    request.setTransferTimeout(REQUEST_TIMEOUT_MS)
    for name, value in prepared.headers.items():
        request.setRawHeader(name.encode("utf-8"), value.encode("utf-8"))
    return request
