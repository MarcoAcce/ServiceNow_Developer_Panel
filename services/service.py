import time

from PySide6.QtCore import QObject, QTimer, Signal

from core.request_model import (
    AUTHORIZATION_HEADER,
    BASIC_PREFIX,
    BEARER_PREFIX,
    COMPOSITE_STATUS_CODE,
    DEFAULT_HEADERS,
    DEFAULT_SCHEME,
    FIELDS_PARAMETER,
    LIMIT_PARAMETER,
    MISSING_ADDRESS_MESSAGE,
    MISSING_AUTHENTICATION_MESSAGE,
    MISSING_INSTANCE_MESSAGE,
    MISSING_TOKEN_MESSAGE,
    NO_AUTHENTICATION_LABEL,
    NO_INSTANCE_LABEL,
    OFFSET_PARAMETER,
    ORDER_PARAMETER,
    PARAMETER_SEPARATOR,
    PARAMETER_TEMPLATE,
    PART_ERROR_MESSAGE,
    QUERY_PARAMETER,
    SCHEME_SEPARATOR,
    TABLE_API_PATH,
    UNREADABLE_AUTHENTICATION_MESSAGE,
    UNSUPPORTED_AUTHENTICATION_MESSAGE,
    PreparedRequest,
    RequestError,
    RequestPart,
    RequestResult,
    RequestSpec,
    RequestTarget,
    ResultSection,
    ServiceConfigurationError,
    authentication_header,
    composite_result,
    instance_url,
    part_of,
    prepare_request,
    query_string,
    section_of,
)

__all__ = [
    "AUTHORIZATION_HEADER",
    "BASIC_PREFIX",
    "BEARER_PREFIX",
    "COMPOSITE_STATUS_CODE",
    "DEFAULT_HEADERS",
    "DEFAULT_SCHEME",
    "FIELDS_PARAMETER",
    "LIMIT_PARAMETER",
    "MISSING_ADDRESS_MESSAGE",
    "MISSING_AUTHENTICATION_MESSAGE",
    "MISSING_INSTANCE_MESSAGE",
    "MISSING_TOKEN_MESSAGE",
    "NO_AUTHENTICATION_LABEL",
    "NO_INSTANCE_LABEL",
    "OFFSET_PARAMETER",
    "ORDER_PARAMETER",
    "PARAMETER_SEPARATOR",
    "PARAMETER_TEMPLATE",
    "PART_ERROR_MESSAGE",
    "QUERY_PARAMETER",
    "SCHEME_SEPARATOR",
    "TABLE_API_PATH",
    "UNREADABLE_AUTHENTICATION_MESSAGE",
    "UNSUPPORTED_AUTHENTICATION_MESSAGE",
    "CompositeRequestCall",
    "FailedRequestCall",
    "PreparedRequest",
    "RequestCall",
    "RequestError",
    "RequestPart",
    "RequestResult",
    "RequestService",
    "RequestSpec",
    "RequestTarget",
    "ResultSection",
    "ServiceConfigurationError",
    "authentication_header",
    "composite_result",
    "instance_url",
    "part_of",
    "prepare_request",
    "query_string",
    "section_of",
]

SERVICE_NAME: str = "service"


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
        self.succeeded.emit(
            composite_result(
                request=self.request,
                sections=self._sections,
                status_code=self._status,
                elapsed_ms=int((time.monotonic() - self._started) * 1000),
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

    name: str = SERVICE_NAME

    def send(self, request: RequestSpec) -> RequestCall:
        raise NotImplementedError

    def describe(self) -> str:
        return self.name
