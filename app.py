import os
import sqlite3
import sys
import time
from functools import partial

from PySide6.QtCore import QLockFile, QObject, Qt, QThreadPool, QTimer
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from core.app_paths import APPLICATION_DIRECTORY_NAME, icon_path
from core.core_channel import (
    HEADLESS_ARGUMENT,
    RETRY_INTERVAL_SECONDS,
    STARTUP_TIMEOUT_SECONDS,
    UNAVAILABLE_MESSAGE,
    WINDOW_CLIENT,
    CoreRejected,
    CoreUnavailable,
    connect,
    lock_path,
)
from services.core_server import CoreServer
from services.mcp_session import McpSession
from services.mcp_tools import build_server
from services.mcp_transport import serve_connection
from ui.dialogs import ErrorDialog
from ui.icons import refresh_icon_widgets
from ui.sidebar import Sidebar
from ui.tab import Tab
from configuration.config_repository import ConfigRepository
from configuration.config_tab import ConfigTab
from core.database_manager import DatabaseError, DatabaseManager
from ui.home_tab import HomeTab

from core.request_types import RequestType
from storage.request_hints import RequestHintRepository
from request_tabs.request_tab import RequestTab
from request_tabs.table_request_tabs import create_request_tab

from response_tabs.response_context import ResponseContext
from storage.response_repository import ResponseRepository
from response_tabs.response_tab import ResponseTab

from services.service import RequestCall, RequestError, RequestResult, RequestService
from services.cached_service import CachedRequestService
from services.dummy_service import DummyRequestService
from services.http_service import HttpRequestService

from ui.theme import Theme, apply_theme, theme_of_key
from ui.window_frame import FramelessWindow

APPLICATION_NAME: str = "ServiceNow Developer Panel"
WINDOW_TITLE: str = "ServiceNow Developer Panel"
WINDOW_WIDTH: int = 1280
WINDOW_HEIGHT: int = 820
TASK_SHUTDOWN_TIMEOUT_MS: int = 15000
IDLE_GRACE_PERIOD_MS: int = 30000
USE_DUMMY_SERVICE: bool = False
STARTUP_ERROR_TITLE: str = "ServiceNow Developer Panel not started"
PLATFORM_VARIABLE: str = "QT_QPA_PLATFORM"
DISPLAY_VARIABLES: tuple[str, ...] = ("DISPLAY", "WAYLAND_DISPLAY")
OFFSCREEN_PLATFORM: str = "offscreen"


def instance_service(parent: QWidget) -> RequestService:
    if USE_DUMMY_SERVICE:
        return DummyRequestService(parent)
    return HttpRequestService(parent)


class MainWindow(FramelessWindow):

    def __init__(
        self, repository: ConfigRepository, database: DatabaseManager, theme: Theme
    ) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(QIcon(str(icon_path())))
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.apply_window_theme(theme)
        self.repository: ConfigRepository = repository
        self.hints: RequestHintRepository = RequestHintRepository(database)
        self.responses: ResponseRepository = ResponseRepository(database)
        self.service: RequestService = CachedRequestService(
            instance_service(self), self.responses, self
        )
        self.response_context: ResponseContext = ResponseContext(
            service=self.service, responses=self.responses, hints=self.hints
        )
        self.sidebar: Sidebar = Sidebar()
        self.home_tab: HomeTab = HomeTab("Home", repository)
        self.config_tab: ConfigTab = ConfigTab("Configuration", repository, database)
        self.response_tabs: list[ResponseTab] = []
        self._current_page: Tab | None = None
        self._request_page: Tab | None = None
        self._busy: bool = False
        self._refresh_call: RequestCall | None = None
        self._refresh_page: ResponseTab | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self._content: QWidget = QWidget()
        self._content_layout: QVBoxLayout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self._content, 1)
        self.set_body(container)

        self.config_tab.themeChanged.connect(self._on_theme_changed)
        self.config_tab.configurationChanged.connect(self._on_configuration_changed)
        self.sidebar.pageSelected.connect(self._on_page_selected)
        self.sidebar.pageClosed.connect(self.remove_response_page)
        self.sidebar.pageRefreshed.connect(self.refresh_response_page)
        self.home_tab.requestSelected.connect(self.open_new_request_page)

        self.sidebar.add_fixed_page(self.home_tab)
        self.sidebar.add_config_page(self.config_tab)
        self.sidebar.select_page(self.home_tab)

    def open_new_request_page(self, request_type: RequestType) -> None:
        self._discard_request_page()
        request_page = create_request_tab(
            request_type.key, self.service, self.repository, self.hints
        )
        request_page.set_instance_id(self.home_tab.current_instance_id())
        request_page.executed.connect(self.add_response_page)
        request_page.closed.connect(self.close_request_page)
        request_page.runningChanged.connect(self._set_busy)
        self._request_page = request_page
        self._display(request_page)

    def close_request_page(self) -> None:
        self._discard_request_page()
        self._display_sidebar_page()

    def add_response_page(self, page: ResponseTab) -> None:
        page.attach(self.response_context)
        page.refreshRequested.connect(self.refresh_response_page)
        page.runningChanged.connect(self._set_busy)
        page.set_refresh_enabled(not self._busy)
        self.response_tabs.append(page)
        self.sidebar.add_response_page(page)
        self.sidebar.select_page(page)

    def refresh_response_page(self, page: Tab) -> None:
        if self._busy or not isinstance(page, ResponseTab):
            return
        self._refresh_page = page
        self._refresh_call = self.service.send(page.result.request.refreshed())
        self._refresh_call.succeeded.connect(self._on_refresh_succeeded)
        self._refresh_call.failed.connect(self._on_refresh_failed)
        page.set_refreshing(True)
        self._set_busy(True)

    def remove_response_page(self, page: Tab) -> None:
        if not isinstance(page, ResponseTab):
            return
        if page is self._refresh_page:
            self._cancel_refresh()
        page.cancel()
        self.sidebar.remove_page(page)
        self.response_tabs.remove(page)
        self._detach(page)
        page.deleteLater()
        if self._current_page is None:
            self._display_sidebar_page()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._discard_request_page()
        self._cancel_refresh()
        for page in self.response_tabs:
            page.cancel()
        super().closeEvent(event)

    def _on_theme_changed(self, key: str) -> None:
        theme = theme_of_key(key)
        application = QApplication.instance()
        if isinstance(application, QApplication):
            apply_theme(application, theme)
            refresh_icon_widgets(application)
        self.sidebar.refresh_icons()
        self.apply_window_theme(theme)

    def _on_configuration_changed(self) -> None:
        self.home_tab.reload_instances()
        request_page = self._request_page
        if isinstance(request_page, RequestTab):
            request_page.reload_instances()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.sidebar.set_busy(busy)
        for page in self.response_tabs:
            page.set_refresh_enabled(not busy)

    def _on_refresh_succeeded(self, result: RequestResult) -> None:
        page = self._refresh_page
        self._release_refresh()
        if page is not None:
            page.update_result(result)

    def _on_refresh_failed(self, error: RequestError) -> None:
        page = self._refresh_page
        self._release_refresh()
        if page is not None:
            page.show_refresh_error(error.message)

    def _cancel_refresh(self) -> None:
        if self._refresh_call is not None:
            self._refresh_call.cancel()
        self._release_refresh()

    def _release_refresh(self) -> None:
        if self._refresh_call is not None:
            self._refresh_call.deleteLater()
            self._refresh_call = None
        self._refresh_page = None
        self._set_busy(False)

    def _on_page_selected(self, page: Tab) -> None:
        self._discard_request_page()
        self._display(page)

    def _display_sidebar_page(self) -> None:
        self._display(self.sidebar.current_page() or self.home_tab)

    def _display(self, page: Tab) -> None:
        if page is self.home_tab:
            self.home_tab.reload_instances()
        if self._current_page is page:
            return
        if self._current_page is not None:
            self._detach(self._current_page)
        self._current_page = page
        self._content_layout.addWidget(page)
        page.show()

    def _detach(self, page: Tab) -> None:
        if self._current_page is page:
            self._current_page = None
        self._content_layout.removeWidget(page)
        page.setParent(None)

    def _discard_request_page(self) -> None:
        request_page = self._request_page
        self._request_page = None
        if request_page is None:
            return
        request_page.cancel()
        self._detach(request_page)
        request_page.deleteLater()


class PanelCore(QObject):

    def __init__(
        self,
        repository: ConfigRepository,
        database: DatabaseManager,
        server: CoreServer,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository: ConfigRepository = repository
        self._database: DatabaseManager = database
        self._server: CoreServer = server
        self._window: MainWindow | None = None
        self._idle_timer: QTimer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(IDLE_GRACE_PERIOD_MS)
        self._idle_timer.timeout.connect(self._quit_if_idle)
        server.windowRequested.connect(self.show_window)
        server.clientsChanged.connect(self.check_idle)

    def show_window(self) -> None:
        window = self._window
        if window is None:
            theme = theme_of_key(self._repository.theme_key())
            window = MainWindow(self._repository, self._database, theme)
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            window.destroyed.connect(self._on_window_destroyed)
            self._window = window
        self._idle_timer.stop()
        if window.isMinimized():
            window.showNormal()
        else:
            window.show()
        window.raise_()
        window.activateWindow()

    def check_idle(self) -> None:
        if self._is_idle():
            self._idle_timer.start()
        else:
            self._idle_timer.stop()

    def _is_idle(self) -> bool:
        return self._window is None and self._server.client_count == 0

    def _on_window_destroyed(self) -> None:
        self._window = None
        self.check_idle()

    def _quit_if_idle(self) -> None:
        if self._is_idle():
            QApplication.quit()


def purge_expired_cache(database: DatabaseManager) -> None:
    try:
        database.purge_expired_responses()
        database.purge_orphan_caches()
    except (DatabaseError, OSError, TimeoutError, sqlite3.Error):
        return


def acquire_core_lock(headless: bool) -> QLockFile | None:
    lock = QLockFile(str(lock_path()))
    lock.setStaleLockTime(0)
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while True:
        if lock.tryLock(0):
            return lock
        if headless:
            return None
        try:
            connect(WINDOW_CLIENT).close()
            return None
        except CoreRejected as error:
            report_startup_error(str(error))
            return None
        except CoreUnavailable:
            if time.monotonic() > deadline:
                report_startup_error(UNAVAILABLE_MESSAGE)
                return None
        time.sleep(RETRY_INTERVAL_SECONDS)


def report_startup_error(message: str) -> None:
    application = QApplication.instance() or QApplication([])
    if isinstance(application, QApplication):
        apply_theme(application, theme_of_key(""))
    ErrorDialog(STARTUP_ERROR_TITLE, message).exec()


def use_offscreen_without_display() -> None:
    if sys.platform.startswith("linux") and not any(
        os.environ.get(name) for name in DISPLAY_VARIABLES
    ):
        os.environ.setdefault(PLATFORM_VARIABLE, OFFSCREEN_PLATFORM)


def create_application() -> QApplication:
    app = QApplication([])
    app.setApplicationName(APPLICATION_NAME)
    app.setApplicationDisplayName(APPLICATION_NAME)
    app.setDesktopFileName(APPLICATION_DIRECTORY_NAME)
    app.setWindowIcon(QIcon(str(icon_path())))
    app.setQuitOnLastWindowClosed(False)
    return app


def run_core(headless: bool) -> None:
    if headless:
        use_offscreen_without_display()
    database = DatabaseManager.instance()
    server: CoreServer | None = None
    try:
        purge_expired_cache(database)
        app = create_application()
        repository = ConfigRepository(database)
        apply_theme(app, theme_of_key(repository.theme_key()))
        mcp = build_server(McpSession(database))
        server = CoreServer(partial(serve_connection, mcp))
        core = PanelCore(repository, database, server)
        server.start()
        if not headless:
            core.show_window()
        core.check_idle()
        app.exec()
    finally:
        if server is not None:
            server.close()
        QThreadPool.globalInstance().waitForDone(TASK_SHUTDOWN_TIMEOUT_MS)
        database.close()


def main() -> None:
    headless = HEADLESS_ARGUMENT in sys.argv[1:]
    lock = acquire_core_lock(headless)
    if lock is None:
        return
    try:
        run_core(headless)
    finally:
        lock.unlock()


if __name__ == "__main__":
    main()
