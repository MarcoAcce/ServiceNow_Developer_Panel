from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget

from core.oauth import is_callback

BLANK_URL: str = "about:blank"


class CallbackInterceptor(QWebEngineUrlRequestInterceptor):

    def __init__(self, state: str, page: "CallbackPage") -> None:
        super().__init__(page)
        self._state: str = state
        self._page: CallbackPage = page

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        url = info.requestUrl().toString()
        if is_callback(url, self._state):
            info.block(True)
            self._page.callbackReached.emit(url)


class CallbackPage(QWebEnginePage):

    callbackReached = Signal(str)

    def __init__(self, state: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state: str = state
        self._interceptor: CallbackInterceptor = CallbackInterceptor(state, self)
        self.setUrlRequestInterceptor(self._interceptor)

    def acceptNavigationRequest(
        self, url: QUrl, navigation_type: QWebEnginePage.NavigationType, is_main_frame: bool
    ) -> bool:
        text = url.toString()
        if is_main_frame and is_callback(text, self._state):
            self.callbackReached.emit(text)
            return False
        return True

    def javaScriptConsoleMessage(
        self,
        level: QWebEnginePage.JavaScriptConsoleMessageLevel,
        message: str,
        line_number: int,
        source_id: str,
    ) -> None:
        return None


class LoginBrowser(QWebEngineView):

    callbackReached = Signal(str)

    def __init__(self, state: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: str = state
        self._page: CallbackPage = CallbackPage(state, self)
        self.setPage(self._page)
        self._page.callbackReached.connect(
            self.callbackReached, Qt.ConnectionType.QueuedConnection
        )
        self.urlChanged.connect(self._on_url_changed)

    def open(self, url: str) -> None:
        self.load(QUrl(url))

    def reset(self) -> None:
        self.stop()
        self.setUrl(QUrl(BLANK_URL))
        self._page.profile().cookieStore().deleteAllCookies()

    def _on_url_changed(self, url: QUrl) -> None:
        text = url.toString()
        if is_callback(text, self._state):
            self._page.callbackReached.emit(text)
