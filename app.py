import sqlite3

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from app_paths import icon_path
from icons import refresh_icon_widgets
from sidebar import Sidebar
from tab import Tab
from config_repository import ConfigRepository
from config_tab import ConfigTab
from database_manager import DatabaseError, DatabaseManager
from home_tab import HomeTab

from request_types import RequestType
from request_hints import RequestHintRepository
from request_tab import RequestTab
from request_tabs import create_request_tab

from response_repository import ResponseRepository
from response_tab import ResponseTab

from service import RequestCall, RequestError, RequestResult, RequestService
from cached_service import CachedRequestService
from dummy_service import DummyRequestService
from http_service import HttpRequestService

from theme import Theme, apply_theme, theme_of_key
from window_frame import FramelessWindow

APPLICATION_NAME: str = "ServiceNow Developer Panel"
WINDOW_TITLE: str = "ServiceNow Developer Panel"
WINDOW_WIDTH: int = 1280
WINDOW_HEIGHT: int = 820
TASK_SHUTDOWN_TIMEOUT_MS: int = 15000
USE_DUMMY_SERVICE: bool = False


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
        self.service: RequestService = CachedRequestService(
            instance_service(self), ResponseRepository(database), self
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
        page.refreshRequested.connect(self.refresh_response_page)
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
        self.sidebar.remove_page(page)
        self.response_tabs.remove(page)
        self._detach(page)
        page.deleteLater()
        if self._current_page is None:
            self._display_sidebar_page()

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


def purge_expired_cache(database: DatabaseManager) -> None:
    try:
        database.purge_expired_responses()
        database.purge_orphan_caches()
    except (DatabaseError, OSError, TimeoutError, sqlite3.Error):
        return


def main() -> None:
    database = DatabaseManager.instance()
    try:
        purge_expired_cache(database)
        app = QApplication([])
        app.setApplicationName(APPLICATION_NAME)
        app.setApplicationDisplayName(APPLICATION_NAME)
        app.setWindowIcon(QIcon(str(icon_path())))
        repository = ConfigRepository(database)
        theme = theme_of_key(repository.theme_key())
        apply_theme(app, theme)
        window = MainWindow(repository, database, theme)
        window.show()
        app.exec()
    finally:
        QThreadPool.globalInstance().waitForDone(TASK_SHUTDOWN_TIMEOUT_MS)
        database.close()


if __name__ == "__main__":
    main()
