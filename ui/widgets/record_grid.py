from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget

MAXIMUM_COLUMN_WIDTH: int = 320


def configure_record_grid(table: QTableWidget) -> None:
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(False)
    header.setSectionsMovable(True)
    header.setTextElideMode(Qt.TextElideMode.ElideRight)


def reset_columns(table: QTableWidget) -> None:
    header = table.horizontalHeader()
    for logical in range(header.count()):
        header.moveSection(header.visualIndex(logical), logical)
    table.resizeColumnsToContents()
    for column in range(table.columnCount()):
        if table.columnWidth(column) > MAXIMUM_COLUMN_WIDTH:
            table.setColumnWidth(column, MAXIMUM_COLUMN_WIDTH)
