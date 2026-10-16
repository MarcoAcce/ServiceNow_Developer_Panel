from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu, QVBoxLayout, QWidget

from ui.icons import (
    DELETE_ICON,
    HOME_ICON,
    REFRESH_ICON,
    SETTINGS_ICON,
    IconButton,
    Tone,
    themed_icon,
)
from ui.tab import Tab
from ui.theme import ITEM_EXTRA_HEIGHT, Role, refresh_role

SIDEBAR_WIDTH: int = 260
TAB_ROLE: int = int(Qt.ItemDataRole.UserRole)
ICON_ROLE: int = int(Qt.ItemDataRole.UserRole) + 1
REFRESH_TOOLTIP: str = "Run this request again"
DELETE_TOOLTIP: str = "Delete this response"
DELETE_ACTION_LABEL: str = "Delete response"
ROW_SPACING: int = 0
BUTTON_SPACING: int = 2


class SidebarRow(QWidget):

    clicked = Signal(object)
    refreshRequested = Signal(object)
    deleteRequested = Signal(object)

    def __init__(self, tab: Tab) -> None:
        super().__init__()
        self.tab: Tab = tab
        self.title_label: QLabel = QLabel()
        self.table_label: QLabel = QLabel()
        self.detail_label: QLabel = QLabel()
        self.refresh_button: IconButton = IconButton(REFRESH_ICON, REFRESH_TOOLTIP)
        self.delete_button: IconButton = IconButton(DELETE_ICON, DELETE_TOOLTIP, Tone.DANGER)
        self._selected: bool = False
        self._build_ui()
        self.refresh_text()

    def refresh_text(self) -> None:
        self.title_label.setText(self.tab.menu_title)
        self.table_label.setText(self.tab.menu_table)
        self.table_label.setVisible(bool(self.tab.menu_table))
        self.detail_label.setText(self.tab.menu_detail)
        self.setToolTip(self.tab.menu_tooltip)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        refresh_role(
            self.title_label, Role.ITEM_TITLE_SELECTED if selected else Role.ITEM_TITLE
        )
        for label in (self.table_label, self.detail_label):
            refresh_role(label, Role.ITEM_HINT_SELECTED if selected else Role.ITEM_HINT)
        self.refresh_button.set_tone(Tone.ON_ACCENT if selected else Tone.PRIMARY)
        self.delete_button.set_tone(Tone.ON_ACCENT if selected else Tone.DANGER)

    def set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ROW_SPACING)
        refresh_role(self.title_label, Role.ITEM_TITLE)
        refresh_role(self.table_label, Role.ITEM_HINT)
        refresh_role(self.detail_label, Role.ITEM_HINT)
        self.refresh_button.clicked.connect(lambda: self.refreshRequested.emit(self.tab))
        self.delete_button.clicked.connect(lambda: self.deleteRequested.emit(self.tab))
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(BUTTON_SPACING)
        header.addWidget(self.title_label, 1)
        header.addWidget(self.refresh_button)
        header.addWidget(self.delete_button)
        layout.addLayout(header)
        layout.addWidget(self.table_label)
        layout.addWidget(self.detail_label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicked.emit(self.tab)
        super().mousePressEvent(event)


class Sidebar(QListWidget):

    pageSelected = Signal(object)
    pageClosed = Signal(object)
    pageRefreshed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._fixed_count: int = 0
        self._busy: bool = False
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.currentItemChanged.connect(self._on_current_item_changed)
        self.itemClicked.connect(self._on_item_clicked)

    def add_fixed_page(self, tab: Tab) -> None:
        self.insertItem(self._fixed_count, self._build_item(tab, HOME_ICON))
        self._fixed_count += 1

    def add_config_page(self, tab: Tab) -> None:
        self.addItem(self._build_item(tab, SETTINGS_ICON))

    def add_response_page(self, tab: Tab) -> None:
        item = QListWidgetItem()
        item.setData(TAB_ROLE, tab)
        self.insertItem(self._fixed_count, item)
        row = SidebarRow(tab)
        row.clicked.connect(self._on_row_clicked)
        row.refreshRequested.connect(self.pageRefreshed.emit)
        row.deleteRequested.connect(self.pageClosed.emit)
        row.set_busy(self._busy)
        self._resize_item(item, row)
        self.setItemWidget(item, row)
        tab.menuTitleChanged.connect(self._on_menu_title_changed)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        for row in self._rows():
            row.set_busy(busy)

    def refresh_icons(self) -> None:
        for index in range(self.count()):
            item = self.item(index)
            if item is None:
                continue
            name = item.data(ICON_ROLE)
            if isinstance(name, str):
                item.setIcon(themed_icon(name))

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

    def _build_item(self, tab: Tab, icon_name: str) -> QListWidgetItem:
        item = QListWidgetItem(tab.menu_title)
        item.setData(TAB_ROLE, tab)
        item.setData(ICON_ROLE, icon_name)
        item.setIcon(themed_icon(icon_name))
        item.setToolTip(tab.menu_title)
        return item

    def _resize_item(self, item: QListWidgetItem, row: SidebarRow) -> None:
        hint = row.sizeHint()
        item.setSizeHint(QSize(hint.width(), hint.height() + ITEM_EXTRA_HEIGHT))

    def _resize_row(self, tab: Tab, row: SidebarRow) -> None:
        item = self._item_of_tab(tab)
        if item is not None:
            self._resize_item(item, row)

    def _rows(self) -> list[SidebarRow]:
        rows: list[SidebarRow] = []
        for index in range(self.count()):
            item = self.item(index)
            widget = self.itemWidget(item) if item is not None else None
            if isinstance(widget, SidebarRow):
                rows.append(widget)
        return rows

    def _row_of_tab(self, tab: Tab) -> SidebarRow | None:
        for row in self._rows():
            if row.tab is tab:
                return row
        return None

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
        self._apply_selection(current)
        tab = self._tab_of_item(current)
        if tab is not None:
            self.pageSelected.emit(tab)

    def _apply_selection(self, current: QListWidgetItem | None) -> None:
        selected = self._tab_of_item(current)
        for row in self._rows():
            row.set_selected(row.tab is selected)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        tab = self._tab_of_item(item)
        if tab is not None:
            self.pageSelected.emit(tab)

    def _on_row_clicked(self, tab: Tab) -> None:
        item = self._item_of_tab(tab)
        if item is None:
            return
        self.setCurrentItem(item)
        self.pageSelected.emit(tab)

    def _on_menu_title_changed(self, tab: Tab) -> None:
        row = self._row_of_tab(tab)
        if row is not None:
            row.refresh_text()
            self._resize_row(tab, row)
            return
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
        close_action = QAction(DELETE_ACTION_LABEL, self)
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
