from typing import TYPE_CHECKING

from PySide6.QtCore import QRect, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from configuration.config_repository import Instance
from core.background_task import BackgroundTask
from core.oauth import (
    NO_CODE_MESSAGE,
    STATE_MISMATCH_MESSAGE,
    authorization_url,
    new_state,
    parse_callback,
)
from services.oauth_tokens import LoginState, OAuthTokenClient, complete_login
from ui.dialogs import CANCEL_LABEL, FramelessDialog
from ui.ui_widgets import hint_label, show_status

if TYPE_CHECKING:
    from ui.widgets.login_browser import LoginBrowser

LOGIN_TITLE: str = "Log in to {name}"
LOGIN_HINT: str = (
    "Sign in to {address} and allow the access. The built-in browser reads the answer of "
    "the instance as soon as it redirects to the redirect URL of the application registry "
    "entry, before that address is loaded, so nothing has to answer there."
)
LINKS_TEXT: str = (
    '<a href="{builtin}">Open the login page</a> in the built-in browser, or '
    '<a href="{system}">open it in your browser</a>: in that case the redirect URL '
    "receives the answer, paste below the address you land on."
)
BUILTIN_LINK: str = "builtin"
SYSTEM_LINK: str = "system"
ADDRESS_PLACEHOLDER: str = "The address you were redirected to, with its code and state"
USE_ADDRESS_LABEL: str = "Use address"
BROWSER_OPENED_MESSAGE: str = "Waiting for the login to complete in the built-in browser..."
SYSTEM_OPENED_MESSAGE: str = "Waiting for the redirected address to be pasted above..."
EXCHANGING_MESSAGE: str = "Exchanging the authorization code for the tokens..."
LOGIN_FAILED_MESSAGE: str = "The login failed: {message}."
BROWSER_UNAVAILABLE_MESSAGE: str = (
    "The built-in browser is not available ({error}): open the login page in your browser "
    "and paste the redirected address."
)
STALE_TOKENS_MESSAGE: str = "A new login is needed: {reason}."
DIALOG_WIDTH: int = 640
BROWSER_WIDTH: int = 960
BROWSER_HEIGHT: int = 680
HORIZONTAL_MARGIN: int = 80
VERTICAL_MARGIN: int = 280
ADDRESS_SPACING: int = 8


class OAuthLoginDialog(FramelessDialog):

    def __init__(
        self,
        instance: Instance,
        details: dict[str, str],
        parent: QWidget | None = None,
        reason: str = "",
        client: OAuthTokenClient | None = None,
    ) -> None:
        super().__init__(LOGIN_TITLE.format(name=instance.name), parent, resizable=True)
        self._instance: Instance = instance
        self._details: dict[str, str] = dict(details)
        self._client: OAuthTokenClient = client or OAuthTokenClient()
        self._state: str = new_state()
        self._url: str = authorization_url(instance.address, details, self._state)
        self._result: LoginState | None = None
        self._task: BackgroundTask | None = None
        self._browser: LoginBrowser | None = None
        self.address_field: QLineEdit = QLineEdit()
        self.use_button: QPushButton = QPushButton(USE_ADDRESS_LABEL)
        self.status_label: QLabel = QLabel()
        self._browser_layout: QVBoxLayout = QVBoxLayout()
        self._build_ui()
        if reason:
            show_status(self.status_label, STALE_TOKENS_MESSAGE.format(reason=reason))

    def details(self) -> dict[str, str]:
        if self._result is None:
            return dict(self._details)
        return dict(self._result.details)

    def user(self) -> str:
        return self._result.user if self._result is not None else ""

    def login_url(self) -> str:
        return self._url

    def done(self, result: int) -> None:
        self._release_task(cancel=True)
        if self._browser is not None:
            self._browser.reset()
        super().done(result)

    def _build_ui(self) -> None:
        hint = hint_label(LOGIN_HINT.format(address=self._instance.address))
        hint.setMinimumWidth(DIALOG_WIDTH)
        self.content_layout.addWidget(hint)
        links = QLabel(LINKS_TEXT.format(builtin=BUILTIN_LINK, system=SYSTEM_LINK))
        links.setTextFormat(Qt.TextFormat.RichText)
        links.setWordWrap(True)
        links.setOpenExternalLinks(False)
        links.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        links.linkActivated.connect(self._on_link)
        self.content_layout.addWidget(links)
        row = QHBoxLayout()
        row.setSpacing(ADDRESS_SPACING)
        self.address_field.setPlaceholderText(ADDRESS_PLACEHOLDER)
        self.address_field.returnPressed.connect(self._on_use_address)
        self.use_button.setAutoDefault(False)
        self.use_button.clicked.connect(self._on_use_address)
        row.addWidget(self.address_field, 1)
        row.addWidget(self.use_button)
        self.content_layout.addLayout(row)
        self._browser_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.addLayout(self._browser_layout, 1)
        self.status_label.setWordWrap(True)
        self.content_layout.addWidget(self.status_label)
        cancel_button = QPushButton(CANCEL_LABEL)
        cancel_button.setAutoDefault(False)
        cancel_button.clicked.connect(self.reject)
        self.add_button_row(cancel_button)

    def _on_link(self, name: str) -> None:
        if self._task is not None:
            return
        if name == BUILTIN_LINK:
            self._open_builtin()
        elif name == SYSTEM_LINK:
            self._open_system()

    def _open_builtin(self) -> None:
        browser = self._browser if self._browser is not None else self._create_browser()
        if browser is None:
            return
        width, height = self._browser_size()
        browser.setMinimumSize(width, height)
        browser.setVisible(True)
        self._grow()
        browser.open(self._url)
        show_status(self.status_label, BROWSER_OPENED_MESSAGE)

    def _create_browser(self) -> "LoginBrowser | None":
        try:
            from ui.widgets.login_browser import LoginBrowser
        except (ImportError, OSError) as error:
            show_status(
                self.status_label, BROWSER_UNAVAILABLE_MESSAGE.format(error=error), failed=True
            )
            return None
        browser = LoginBrowser(self._state, self)
        browser.callbackReached.connect(self._on_callback)
        self._browser_layout.addWidget(browser)
        self._browser = browser
        return browser

    def _browser_size(self) -> tuple[int, int]:
        available = self._available_geometry()
        return (
            min(BROWSER_WIDTH, available.width() - HORIZONTAL_MARGIN),
            min(BROWSER_HEIGHT, available.height() - VERTICAL_MARGIN),
        )

    def _available_geometry(self) -> QRect:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return QRect(0, 0, BROWSER_WIDTH, BROWSER_HEIGHT)
        return screen.availableGeometry()

    def _grow(self) -> None:
        self._activate_layout()
        self.adjustSize()
        frame = self.frameGeometry()
        frame.moveCenter(self._available_geometry().center())
        self.move(frame.topLeft())

    def _hide_browser(self) -> None:
        if self._browser is None:
            return
        self._browser.reset()
        self._browser.setVisible(False)
        self._browser.setMinimumSize(0, 0)
        self._activate_layout()
        self.adjustSize()

    def _activate_layout(self) -> None:
        layout = self.layout()
        if layout is not None:
            layout.activate()

    def _open_system(self) -> None:
        QDesktopServices.openUrl(QUrl(self._url))
        show_status(self.status_label, SYSTEM_OPENED_MESSAGE)

    def _on_use_address(self) -> None:
        self._on_callback(self.address_field.text())

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
        self._hide_browser()
        self._exchange(callback.code)

    def _fail(self, message: str) -> None:
        self._hide_browser()
        show_status(self.status_label, LOGIN_FAILED_MESSAGE.format(message=message), failed=True)

    def _exchange(self, code: str) -> None:
        self.use_button.setEnabled(False)
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
            show_status(
                self.status_label, LOGIN_FAILED_MESSAGE.format(message=state.message), failed=True
            )
            return
        self._result = state
        self.accept()

    def _on_exchange_failed(self, message: str) -> None:
        self._release_task()
        show_status(self.status_label, LOGIN_FAILED_MESSAGE.format(message=message), failed=True)

    def _release_task(self, cancel: bool = False) -> None:
        task = self._task
        self._task = None
        self.use_button.setEnabled(True)
        if task is None:
            return
        if cancel:
            task.cancel()
        task.deleteLater()
