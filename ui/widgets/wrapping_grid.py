from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QGridLayout, QWidget

GRID_SPACING: int = 8


class WrappingGrid(QWidget):

    def __init__(self, item_width: int) -> None:
        super().__init__()
        self._item_width: int = item_width
        self._items: list[QWidget] = []
        self._columns: int = 0
        self._grid: QGridLayout = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(GRID_SPACING)
        self._grid.setVerticalSpacing(GRID_SPACING)

    def add_widget(self, widget: QWidget) -> None:
        self._items.append(widget)
        self._arrange(self._columns_for(self.width()))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        columns = self._columns_for(event.size().width())
        if columns != self._columns:
            self._arrange(columns)

    def _columns_for(self, width: int) -> int:
        fitting = (width + GRID_SPACING) // (self._item_width + GRID_SPACING)
        return max(1, min(len(self._items), fitting))

    def _arrange(self, columns: int) -> None:
        for item in self._items:
            self._grid.removeWidget(item)
        for column in range(self._columns):
            self._grid.setColumnStretch(column, 0)
        for index, item in enumerate(self._items):
            self._grid.addWidget(item, index // columns, index % columns)
        for column in range(columns):
            self._grid.setColumnStretch(column, 1)
        self._columns = columns
