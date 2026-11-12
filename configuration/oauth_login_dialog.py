from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from configuration.config_repository import Instance
from core.background_task import BackgroundTask
from core.oauth import (
    NO_CODE_MESSAGE,
    SCHEME_SEPARATOR,
    STATE_MISMATCH_MESSAGE,
    authorization_url,
    new_state,
    parse_callback,
    serving_redirect_uri,
)
from services.callback_server import CallbackServer, CallbackServerError
from services.oauth_tokens import LoginState, OAuthTokenClient, complete_login
from ui.dialogs import CANCEL_LABEL, FramelessDialog
from ui.ui_widgets import hint_label, show_status

LOGIN_TITLE: str = "Log in to {name}"
LOGIN_HINT: str = (
    "Sign in to {address} in the browser that just opened and allow the access. The instance "
    "then sends the browser to {redirect_uri}, where the panel receives the authorization "
    "code and completes the login on its own. If that page cannot be reached, copy the code "
    "or the address from the browser and paste it below."
)
LINK_TEXT: str = 'If the browser did not open, <a href="{open}">open the login page</a> again.'
OPEN_LINK: str = "open"
CODE_PLACEHOLDER: str = "Authorization code, or the address of the page you landed on"
USE_CODE_LABEL: str = "Use code"
WAITING_MESSAGE: str = "Waiting for the login to complete in your browser..."
BROWSER_FAILED_MESSAGE: str = "The browser could not be opened: use the link above."
SERVER_UNAVAILABLE_MESSAGE: str = (
    "The panel cannot receive the answer on its own ({reason}): after the login, copy the "
    "code from the page you land on and paste it below."
)
EXCHANGING_MESSAGE: str = "Exchanging the authorization code for the tokens..."
LOGIN_FAILED_MESSAGE: str = "The login failed: {message}."
STALE_TOKENS_MESSAGE: str = "A new login is needed: {reason}."
DIALOG_WIDTH: int = 640
CODE_SPACING: int = 8
PATH_PREFIXES: tuple[str, ...] = ("/", "?")


def open_in_browser(url: str) -> bool:
    return QDesktopServices.openUrl(QUrl(url))


class CallbackRelay(QObject):

    received = Signal(str)

    def notify(self, url: str) -> None:
        self.received.emit(url)


class OAuthLoginDialog(FramelessDialog):

    def __init__(
        self,
        instance: Instance,
        details: dict[str, str],
        parent: QWidget | None = None,
        reason: str = "",
        client: OAuthTokenClient | None = None,
    ) -> None:
        super().__init__(LOGIN_TITLE.format(name=instance.name), parent)
        self.setMinimumWidth(DIALOG_WIDTH)
        self._instance: Instance = instance
        self._details: dict[str, str] = dict(details)
        self._client: OAuthTokenClient = client or OAuthTokenClient()
        self._state: str = new_state()
        self._redirect_uri: str = serving_redirect_uri(details)
        self._url: str = authorization_url(instance.address, details, self._state)
        self._result: LoginState | None = None
        self._task: BackgroundTask | None = None
        self._server: CallbackServer | None = None
        self._server_problem: str = ""
        self._opened: bool = False
        self._relay: CallbackRelay = CallbackRelay(self)
        self._relay.received.connect(self._on_callback, Qt.ConnectionType.QueuedConnection)
        self.code_field: QLineEdit = QLineEdit()
        self.use_button: QPushButton = QPushButton(USE_CODE_LABEL)
        self.status_label: QLabel = QLabel()
        self._build_ui(reason)
        self._start_server()

    def details(self) -> dict[str, str]:
        if self._result is None:
            return dict(self._details)
        return dict(self._result.details)

    def user(self) -> str:
        return self._result.user if self._result is not None else ""

    def login_url(self) -> str:
        return self._url

    def redirect_uri(self) -> str:
        return self._redirect_uri

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._opened:
            self._opened = True
            self._open_browser()

    def done(self, result: int) -> None:
        self._release_task(cancel=True)
        self._stop_server()
        super().done(result)

    def _build_ui(self, reason: str) -> None:
        hint = LOGIN_HINT.format(address=self._instance.address, redirect_uri=self._redirect_uri)
        self.content_layout.addWidget(hint_label(hint))
        if reason:
            self.content_layout.addWidget(hint_label(STALE_TOKENS_MESSAGE.format(reason=reason)))
        link = QLabel(LINK_TEXT.format(open=OPEN_LINK))
        link.setTextFormat(Qt.TextFormat.RichText)
        link.setWordWrap(True)
        link.setOpenExternalLinks(False)
        link.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        link.linkActivated.connect(self._on_link)
        self.content_layout.addWidget(link)
        row = QHBoxLayout()
        row.setSpacing(CODE_SPACING)
        self.code_field.setPlaceholderText(CODE_PLACEHOLDER)
        self.code_field.returnPressed.connect(self._on_use_code)
        self.use_button.setAutoDefault(False)
        self.use_button.clicked.connect(self._on_use_code)
        row.addWidget(self.code_field, 1)
        row.addWidget(self.use_button)
        self.content_layout.addLayout(row)
        self.status_label.setWordWrap(True)
        self.content_layout.addWidget(self.status_label)
        cancel_button = QPushButton(CANCEL_LABEL)
        cancel_button.setAutoDefault(False)
        cancel_button.clicked.connect(self.reject)
        self.add_button_row(cancel_button)

    def _start_server(self) -> None:
        try:
            server = CallbackServer(self._redirect_uri, self._state, self._relay.notify)
            server.start()
        except CallbackServerError as error:
            self._server_problem = str(error)
            return
        self._server = server

    def _stop_server(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.stop()

    def _open_browser(self) -> None:
        if not open_in_browser(self._url):
            show_status(self.status_label, BROWSER_FAILED_MESSAGE, failed=True)
            return
        self._show_waiting()

    def _show_waiting(self) -> None:
        if self._server_problem:
            message = SERVER_UNAVAILABLE_MESSAGE.format(reason=self._server_problem)
        else:
            message = WAITING_MESSAGE
        show_status(self.status_label, message)

    def _on_link(self, name: str) -> None:
        if name == OPEN_LINK and self._task is None:
            self._open_browser()

    def _on_use_code(self) -> None:
        text = self.code_field.text().strip()
        if not text or self._task is not None:
            return
        if SCHEME_SEPARATOR in text or text.startswith(PATH_PREFIXES):
            self._on_callback(text)
            return
        self._exchange(text)

    def _on_callback(self, url: str) -> None:
        if self._task is not None:
            return
        callback = parse_callback(url)
        if callback is None:
            self._fail(NO_CODE_MESSAGE)
            return
        if callback.problem:
            self._fail(callback.problem)
            return
        if callback.state != self._state:
            self._fail(STATE_MISMATCH_MESSAGE)
            return
        self._exchange(callback.code)

    def _fail(self, message: str) -> None:
        show_status(self.status_label, LOGIN_FAILED_MESSAGE.format(message=message), failed=True)

    def _exchange(self, code: str) -> None:
        self.use_button.setEnabled(False)
        self.code_field.setEnabled(False)
        show_status(self.status_label, EXCHANGING_MESSAGE)
        client = self._client
        address = self._instance.address
        details = dict(self._details)
        task = BackgroundTask(lambda: complete_login(client, address, details, code), self)
        task.finished.connect(self._on_exchanged)
        task.failed.connect(self._on_exchange_failed)
        self._task = task
        task.start()

    def _on_exchanged(self, state: object) -> None:
        self._release_task()
        if not isinstance(state, LoginState):
            return
        if not state.logged_in:
            self._fail(state.message)
            return
        self._result = state
        self.accept()

    def _on_exchange_failed(self, message: str) -> None:
        self._release_task()
        self._fail(message)

    def _release_task(self, cancel: bool = False) -> None:
        task = self._task
        self._task = None
        self.use_button.setEnabled(True)
        self.code_field.setEnabled(True)
        if task is None:
            return
        if cancel:
            task.cancel()
        task.deleteLater()
