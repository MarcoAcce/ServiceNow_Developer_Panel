from collections.abc import Callable

from PySide6.QtCore import QObject

from core.table_description import description_request
from core.table_dictionary import (
    HIERARCHY_DEPTH,
    MAXIMUM_PARENTS,
    hierarchy_request,
    parent_names,
)
from services.service import RequestCall, RequestError, RequestResult, RequestService, RequestSpec

MISSING_TABLE_MESSAGE: str = "the table {table} does not exist on the instance"


class TableDescriptionCall(RequestCall):

    def __init__(
        self,
        request: RequestSpec,
        active_only: bool,
        service: RequestService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(request, parent)
        self._service: RequestService = service
        self._active_only: bool = active_only
        self._chain: list[str] = [request.table]
        self._cancelled: bool = False
        self._call: RequestCall | None = None
        self._send(hierarchy_request(request.table, request.target), self._on_hierarchy)

    def is_running(self) -> bool:
        return not self._cancelled and self._call is not None

    def cancel(self) -> None:
        self._cancelled = True
        self._release_call(cancel=True)

    def _send(self, request: RequestSpec, handler: Callable[[RequestResult], None]) -> None:
        call = self._service.send(request)
        self._call = call
        call.succeeded.connect(lambda result: self._on_succeeded(result, handler))
        call.failed.connect(self._on_failed)

    def _on_succeeded(
        self, result: RequestResult, handler: Callable[[RequestResult], None]
    ) -> None:
        self._release_call()
        if not self._cancelled:
            handler(result)

    def _on_hierarchy(self, result: RequestResult) -> None:
        if not result.records:
            if len(self._chain) == 1:
                self._fail(MISSING_TABLE_MESSAGE.format(table=self.request.table))
                return
            self._describe()
            return
        found = parent_names(result.records[0])
        self._chain.extend(found)
        if len(found) == HIERARCHY_DEPTH and len(self._chain) <= MAXIMUM_PARENTS:
            self._send(hierarchy_request(found[-1], self.request.target), self._on_hierarchy)
            return
        self._describe()

    def _describe(self) -> None:
        request = description_request(self._chain, self._active_only, self.request.target)
        self._send(request, self.succeeded.emit)

    def _on_failed(self, error: RequestError) -> None:
        self._release_call()
        if not self._cancelled:
            self._fail(error.message, error.status_code)

    def _fail(self, message: str, status_code: int = 0) -> None:
        self.failed.emit(
            RequestError(request=self.request, message=message, status_code=status_code)
        )

    def _release_call(self, cancel: bool = False) -> None:
        call = self._call
        self._call = None
        if call is None:
            return
        if cancel:
            call.cancel()
        call.deleteLater()
