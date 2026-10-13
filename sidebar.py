from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMenu

from tab import Tab

SIDEBAR_WIDTH: int = 200
TAB_ROLE: int = int(Qt.ItemDataRole.UserRole)


class Sidebar(QListWidget):

    pageSelected = Signal(object)
    pageClosed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._fixed_count: int = 0
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.currentItemChanged.connect(self._on_current_item_changed)
        self.itemClicked.connect(self._on_item_clicked)

    def add_fixed_page(self, tab: Tab) -> None:
        self.insertItem(self._fixed_count, self._build_item(tab))
        self._fixed_count += 1

    def add_response_page(self, tab: Tab) -> None:
        self.insertItem(self._fixed_count, self._build_item(tab))
        tab.menuTitleChanged.connect(self._on_menu_title_changed)

    def current_page(self) -> Tab | None:
        return self._tab_of_item(self.currentItem())

    def select_page(self, tab: Tab) -> None:
        item = self._item_of_tab(tab)
        if item is not None:
            self.setCurrentItem(item)

    def remove_page(self, tab: Tab) -> None:
        item = self._item_of_tab(tab)
        if item is None:
            return
        self.takeItem(self.row(item))

    def _build_item(self, tab: Tab) -> QListWidgetItem:
        item = QListWidgetItem(tab.menu_title)
        item.setData(TAB_ROLE, tab)
        item.setToolTip(tab.menu_title)
        return item

    def _item_of_tab(self, tab: Tab) -> QListWidgetItem | None:
        for row in range(self.count()):
            item = self.item(row)
            if item is not None and item.data(TAB_ROLE) is tab:
                return item
        return None

    def _tab_of_item(self, item: QListWidgetItem | None) -> Tab | None:
        if item is None:
            return None
        tab = item.data(TAB_ROLE)
        return tab if isinstance(tab, Tab) else None

    def _on_current_item_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        tab = self._tab_of_item(current)
        if tab is not None:
            self.pageSelected.emit(tab)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        tab = self._tab_of_item(item)
        if tab is not None:
            self.pageSelected.emit(tab)

    def _on_menu_title_changed(self, tab: Tab) -> None:
        item = self._item_of_tab(tab)
        if item is not None:
            item.setText(tab.menu_title)
            item.setToolTip(tab.menu_title)

    def _show_context_menu(self, position: object) -> None:
        item = self.itemAt(position)
        tab = self._tab_of_item(item)
        if tab is None or not tab.is_closable():
            return
        menu = QMenu(self)
        close_action = QAction("Delete response", self)
        close_action.triggered.connect(lambda: self.pageClosed.emit(tab))
        menu.addAction(close_action)
        menu.exec(self.mapToGlobal(position))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            tab = self._tab_of_item(self.currentItem())
            if tab is not None and tab.is_closable():
                self.pageClosed.emit(tab)
                return
        super().keyPressEvent(event)
