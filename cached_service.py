import time

from PySide6.QtCore import QObject

from background_task import BackgroundTask
from response_repository import CachedResponse, ResponseRepository
from service import RequestCall, RequestError, RequestResult, RequestService, RequestSpec

CACHE_STATUS_CODE: int = 200
CACHE_TIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
CACHE_SOURCE: str = "local cache of {received_at}"
SERVICE_NAME: str = "cached service"
SERVICE_DESCRIPTION: str = "the local cache, or {source}"


class CachedRequestCall(RequestCall):

    def __init__(
        self,
        request: RequestSpec,
        service: RequestService,
        cache: "CachedRequestService",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(request, parent)
        self._service: RequestService = service
        self._cache: "CachedRequestService" = cache
        self._started: float = time.monotonic()
        self._cancelled: bool = False
        self._task: BackgroundTask | None = None
        self._call: RequestCall | None = None
        if request.skip_cache:
            self._send()
        else:
            self._lookup()

    def is_running(self) -> bool:
        if self._cancelled:
            return False
        if self._call is not None:
            return self._call.is_running()
        return self._task is not None

    def cancel(self) -> None:
        self._cancelled = True
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
        self._release_call(cancel=True)

    def _lookup(self) -> None:
        task = BackgroundTask(lambda: self._cache.lookup(self.request), self)
        task.finished.connect(self._on_lookup)
        task.failed.connect(self._on_lookup_failed)
        self._task = task
        task.start()

    def _on_lookup(self, cached: object) -> None:
        self._task = None
        if self._cancelled:
            return
        if not isinstance(cached, CachedResponse):
            self._send()
            return
        self.succeeded.emit(
            RequestResult(
                request=self.request,
                records=cached.records,
                status_code=CACHE_STATUS_CODE,
                elapsed_ms=self._elapsed_ms(),
                source=CACHE_SOURCE.format(
                    received_at=cached.executed_at.strftime(CACHE_TIME_FORMAT)
                ),
                executed_at=cached.executed_at,
            )
        )

    def _on_lookup_failed(self, message: str) -> None:
        self._task = None
        if not self._cancelled:
            self._send()

    def _send(self) -> None:
        call = self._service.send(self.request)
        self._call = call
        call.succeeded.connect(self._on_succeeded)
        call.failed.connect(self._on_failed)

    def _on_succeeded(self, result: RequestResult) -> None:
        self._release_call()
        if self._cancelled:
            return
        self._cache.store(result)
        self.succeeded.emit(result)

    def _on_failed(self, error: RequestError) -> None:
        self._release_call()
        if self._cancelled:
            return
        self.failed.emit(error)

    def _release_call(self, cancel: bool = False) -> None:
        call = self._call
        self._call = None
        if call is None:
            return
        if cancel:
            call.cancel()
        call.deleteLater()

    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self._started) * 1000)


class CachedRequestService(RequestService):

    name: str = SERVICE_NAME

    def __init__(
        self,
        service: RequestService,
        responses: ResponseRepository,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service: RequestService = service
        self._responses: ResponseRepository = responses

    def send(self, request: RequestSpec) -> RequestCall:
        return CachedRequestCall(request, self._service, self, self)

    def describe(self) -> str:
        return SERVICE_DESCRIPTION.format(source=self._service.describe())

    def lookup(self, request: RequestSpec) -> CachedResponse | None:
        return self._responses.load_cached(request)

    def store(self, result: RequestResult) -> None:
        task = BackgroundTask(lambda: self._responses.record(result), self)
        task.finished.connect(task.deleteLater)
        task.failed.connect(task.deleteLater)
        task.start()
