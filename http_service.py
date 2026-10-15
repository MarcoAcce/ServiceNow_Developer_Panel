import json
import time
from typing import Any

from PySide6.QtCore import QObject, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from service import (
    LIMIT_PARAMETER,
    OFFSET_PARAMETER,
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

REQUEST_TIMEOUT_MS: int = 30000
MAXIMUM_PAGE_SIZE: int = 10000
SERVICE_NAME: str = "ServiceNow instance"
SERVICE_DESCRIPTION: str = "a live call to the selected instance"
HTTP_ERROR_STATUS: int = 400
RESULT_KEY: str = "result"
ERROR_KEY: str = "error"
MESSAGE_KEY: str = "message"
DETAIL_KEY: str = "detail"
VALUE_KEY: str = "value"
DISPLAY_VALUE_KEY: str = "display_value"
MESSAGE_SEPARATOR: str = ": "
TRUE_VALUE: str = "true"
FALSE_VALUE: str = "false"
INVALID_PAYLOAD_MESSAGE: str = "the instance answered with a body that is not valid json"
UNEXPECTED_PAYLOAD_MESSAGE: str = "the instance answered without a result list"
STATUS_MESSAGE: str = "the instance answered with the status {status}"
NO_RESPONSE_MESSAGE: str = "the instance did not answer"


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

    @property
    def _paged(self) -> bool:
        return self._wanted > MAXIMUM_PAGE_SIZE

    def _fetch_page(self) -> None:
        try:
            prepared = prepare_request(self.request, self._page_parameters())
        except ServiceConfigurationError as error:
            self._emit_error(str(error), 0)
            return
        self._reply = self._manager.get(network_request(prepared))
        self._reply.finished.connect(self._on_finished)

    def _page_parameters(self) -> dict[str, str]:
        if not self._paged:
            return {}
        self._page_size = min(MAXIMUM_PAGE_SIZE, self._wanted - len(self._records))
        return {
            LIMIT_PARAMETER: str(self._page_size),
            OFFSET_PARAMETER: str(self._offset + len(self._records)),
        }

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
        if not self._paged or received < self._page_size:
            return False
        return len(self._records) < self._wanted

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
        try:
            prepare_request(request)
        except ServiceConfigurationError as error:
            return FailedRequestCall(request, str(error), self)
        return HttpRequestCall(request, self._manager, self)

    def describe(self) -> str:
        return SERVICE_DESCRIPTION


def parameter_value(request: RequestSpec, name: str) -> int:
    value = request.parameters.get(name, "").strip()
    return int(value) if value.isdigit() else 0


def network_request(prepared: PreparedRequest) -> QNetworkRequest:
    request = QNetworkRequest(QUrl(prepared.url))
    request.setTransferTimeout(REQUEST_TIMEOUT_MS)
    for name, value in prepared.headers.items():
        request.setRawHeader(name.encode("utf-8"), value.encode("utf-8"))
    return request


def response_records(payload: bytes) -> list[dict[str, str]]:
    result = response_document(payload).get(RESULT_KEY)
    if isinstance(result, dict):
        result = [result]
    if not isinstance(result, list):
        raise ValueError(UNEXPECTED_PAYLOAD_MESSAGE)
    return [record_of(entry) for entry in result if isinstance(entry, dict)]


def response_document(payload: bytes) -> dict[str, Any]:
    if not payload:
        raise ValueError(NO_RESPONSE_MESSAGE)
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(INVALID_PAYLOAD_MESSAGE) from error
    if not isinstance(document, dict):
        raise ValueError(UNEXPECTED_PAYLOAD_MESSAGE)
    return document


def error_message(payload: bytes, reason: str, status: int) -> str:
    details = payload_error(payload)
    if details and reason:
        return f"{reason}{MESSAGE_SEPARATOR}{details}"
    return details or reason or STATUS_MESSAGE.format(status=status)


def payload_error(payload: bytes) -> str:
    try:
        document = response_document(payload)
    except ValueError:
        return ""
    details = document.get(ERROR_KEY)
    if not isinstance(details, dict):
        return ""
    parts = [
        str(details.get(key, "")).strip()
        for key in (MESSAGE_KEY, DETAIL_KEY)
        if str(details.get(key, "")).strip()
    ]
    return MESSAGE_SEPARATOR.join(parts)


def record_of(entry: dict[str, Any]) -> dict[str, str]:
    return {str(key): value_of(value) for key, value in entry.items()}


def value_of(value: Any) -> str:
    if isinstance(value, dict):
        for key in (DISPLAY_VALUE_KEY, VALUE_KEY):
            if key in value:
                return value_of(value[key])
        return ""
    if value is None:
        return ""
    if isinstance(value, bool):
        return TRUE_VALUE if value else FALSE_VALUE
    return str(value)
