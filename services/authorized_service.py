from dataclasses import replace

from PySide6.QtCore import QObject

from configuration.config_repository import Authentication
from core.background_task import BackgroundTask
from core.oauth import (
    LOGIN_CANCELLED_MESSAGE,
    LOGIN_REQUIRED_MESSAGE,
    LoginRequired,
    access_token_of,
)
from services.oauth_tokens import (
    UNAUTHORIZED_STATUS,
    LoginHandler,
    TokenManager,
    is_oauth_target,
)
from services.service import (
    RequestCall,
    RequestError,
    RequestResult,
    RequestService,
    RequestSpec,
    RequestTarget,
)

SERVICE_NAME: str = "authorized service"


class AuthorizedRequestCall(RequestCall):

    def __init__(
        self,
        request: RequestSpec,
        service: RequestService,
        tokens: TokenManager,
        login: LoginHandler | None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(request, parent)
        self._service: RequestService = service
        self._tokens: TokenManager = tokens
        self._login: LoginHandler | None = login
        self._cancelled: bool = False
        self._renewed: bool = False
        self._sent_token: str = ""
        self._task: BackgroundTask | None = None
        self._call: RequestCall | None = None
        self._resolve("")

    def is_running(self) -> bool:
        if self._cancelled:
            return False
        if self._call is not None:
            return self._call.is_running()
        return self._task is not None

    def cancel(self) -> None:
        self._cancelled = True
        self._release_task(cancel=True)
        self._release_call(cancel=True)

    def _resolve(self, rejected_token: str) -> None:
        target = self.request.target
        task = BackgroundTask(lambda: self._resolved(target, rejected_token), self)
        task.finished.connect(self._on_resolved)
        task.failed.connect(self._on_resolve_failed)
        self._task = task
        task.start()

    def _resolved(
        self, target: RequestTarget, rejected_token: str
    ) -> Authentication | LoginRequired:
        try:
            return self._tokens.resolve(target, rejected_token)
        except LoginRequired as error:
            return error

    def _on_resolved(self, value: object) -> None:
        self._release_task()
        if self._cancelled:
            return
        if isinstance(value, Authentication):
            self._send(value)
            return
        self._ask_login(str(value) if isinstance(value, LoginRequired) else "")

    def _on_resolve_failed(self, message: str) -> None:
        self._release_task()
        if not self._cancelled:
            self._emit_error(message)

    def _ask_login(self, reason: str) -> None:
        if self._login is None:
            self._emit_error(reason or LOGIN_REQUIRED_MESSAGE)
            return
        authentication = self._login(self.request.target, reason)
        if self._cancelled:
            return
        if authentication is None:
            self._emit_error(LOGIN_CANCELLED_MESSAGE)
            return
        self._send(authentication)

    def _send(self, authentication: Authentication) -> None:
        self._sent_token = access_token_of(authentication.details)
        target = replace(self.request.target, authentication=authentication)
        call = self._service.send(replace(self.request, target=target))
        self._call = call
        call.succeeded.connect(self._on_succeeded)
        call.failed.connect(self._on_failed)

    def _on_succeeded(self, result: RequestResult) -> None:
        self._release_call()
        if self._cancelled:
            return
        self.succeeded.emit(replace(result, request=self.request))

    def _on_failed(self, error: RequestError) -> None:
        self._release_call()
        if self._cancelled:
            return
        if error.status_code == UNAUTHORIZED_STATUS and not self._renewed:
            self._renewed = True
            self._resolve(self._sent_token)
            return
        self.failed.emit(replace(error, request=self.request))

    def _emit_error(self, message: str, status: int = 0) -> None:
        self.failed.emit(
            RequestError(request=self.request, message=message, status_code=status)
        )

    def _release_task(self, cancel: bool = False) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        if cancel:
            task.cancel()
        task.deleteLater()

    def _release_call(self, cancel: bool = False) -> None:
        call = self._call
        self._call = None
        if call is None:
            return
        if cancel:
            call.cancel()
        call.deleteLater()


class AuthorizedRequestService(RequestService):

    name: str = SERVICE_NAME

    def __init__(
        self,
        service: RequestService,
        tokens: TokenManager,
        login: LoginHandler | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service: RequestService = service
        self._tokens: TokenManager = tokens
        self._login: LoginHandler | None = login

    def send(self, request: RequestSpec) -> RequestCall:
        if not is_oauth_target(request.target):
            return self._service.send(request)
        return AuthorizedRequestCall(request, self._service, self._tokens, self._login, self)

    def describe(self) -> str:
        return self._service.describe()
