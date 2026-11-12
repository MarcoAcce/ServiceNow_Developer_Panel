from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from configuration.config_repository import Instance
from configuration.oauth_login_dialog import OAuthLoginDialog
from core.background_task import BackgroundTask
from services.oauth_tokens import LoginState, OAuthTokenClient, verify_login

LOGIN_FAILED_MESSAGE: str = "The login failed: {message}."


class LoginRunner(QObject):

    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, parent: QWidget, client: OAuthTokenClient | None = None) -> None:
        super().__init__(parent)
        self._parent_widget: QWidget = parent
        self._client: OAuthTokenClient = client or OAuthTokenClient()
        self._task: BackgroundTask | None = None
        self._instance: Instance | None = None

    def is_running(self) -> bool:
        return self._task is not None

    def start(self, instance: Instance, details: dict[str, str]) -> None:
        if self._task is not None:
            return
        self._instance = instance
        client = self._client
        address = instance.address
        snapshot = dict(details)
        task = BackgroundTask(lambda: verify_login(client, address, snapshot), self)
        task.finished.connect(self._on_checked)
        task.failed.connect(self._on_check_failed)
        self._task = task
        task.start()

    def _on_checked(self, state: object) -> None:
        self._release()
        instance = self._instance
        if not isinstance(state, LoginState) or instance is None:
            return
        if state.logged_in:
            self.succeeded.emit(state)
            return
        if not state.login_required:
            self.failed.emit(LOGIN_FAILED_MESSAGE.format(message=state.message))
            return
        dialog = OAuthLoginDialog(
            instance, state.details, self._parent_widget, state.message, self._client
        )
        if dialog.exec() != OAuthLoginDialog.DialogCode.Accepted:
            self.cancelled.emit()
            return
        self.succeeded.emit(LoginState(dialog.details(), logged_in=True, user=dialog.user()))

    def _on_check_failed(self, message: str) -> None:
        self._release()
        self.failed.emit(LOGIN_FAILED_MESSAGE.format(message=message))

    def _release(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.deleteLater()
