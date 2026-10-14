from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from app_paths import icon_path
from sidebar import Sidebar
from tab import Tab
from config_repository import ConfigRepository
from config_tab import ConfigTab
from database_manager import DatabaseManager
from home_tab import HomeTab

from request_types import RequestType
from request_tabs import create_request_tab

from response_tab import ResponseTab

from service import RequestService
from dummy_service import DummyRequestService

from theme import Theme, apply_theme, theme_of_key
from window_frame import FramelessWindow

APPLICATION_NAME: str = "ServiceNow Developer Panel"
WINDOW_TITLE: str = "ServiceNow Developer Panel"
WINDOW_WIDTH: int = 1280
WINDOW_HEIGHT: int = 820


class MainWindow(FramelessWindow):

    def __init__(self, repository: ConfigRepository, theme: Theme) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(QIcon(str(icon_path())))
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.apply_window_theme(theme)
        self.repository: ConfigRepository = repository
        self.service: RequestService = DummyRequestService(self)
        self.sidebar: Sidebar = Sidebar()
        self.home_tab: HomeTab = HomeTab("Home")
        self.config_tab: ConfigTab = ConfigTab("Configuration", repository)
        self.response_tabs: list[ResponseTab] = []
        self._current_page: Tab | None = None
        self._request_page: Tab | None = None
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
        self.sidebar.pageSelected.connect(self._on_page_selected)
        self.sidebar.pageClosed.connect(self.remove_response_page)
        self.home_tab.requestSelected.connect(self.open_new_request_page)

        self.sidebar.add_fixed_page(self.home_tab)
        self.sidebar.add_config_page(self.config_tab)
        self.sidebar.select_page(self.home_tab)

    def open_new_request_page(self, request_type: RequestType) -> None:
        self._discard_request_page()
        request_page = create_request_tab(request_type.key, self.service)
        request_page.executed.connect(self.add_response_page)
        request_page.closed.connect(self.close_request_page)
        self._request_page = request_page
        self._display(request_page)

    def close_request_page(self) -> None:
        self._discard_request_page()
        self._display_sidebar_page()

    def add_response_page(self, page: ResponseTab) -> None:
        self.response_tabs.append(page)
        self.sidebar.add_response_page(page)
        self.sidebar.select_page(page)

    def remove_response_page(self, page: Tab) -> None:
        if not isinstance(page, ResponseTab):
            return
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
        self.apply_window_theme(theme)

    def _on_page_selected(self, page: Tab) -> None:
        self._discard_request_page()
        self._display(page)

    def _display_sidebar_page(self) -> None:
        self._display(self.sidebar.current_page() or self.home_tab)

    def _display(self, page: Tab) -> None:
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


def main() -> None:
    database = DatabaseManager.instance()
    try:
        app = QApplication([])
        app.setApplicationName(APPLICATION_NAME)
        app.setApplicationDisplayName(APPLICATION_NAME)
        app.setWindowIcon(QIcon(str(icon_path())))
        repository = ConfigRepository(database)
        theme = theme_of_key(repository.theme_key())
        apply_theme(app, theme)
        window = MainWindow(repository, theme)
        window.show()
        app.exec()
    finally:
        database.close()


if __name__ == "__main__":
    main()
