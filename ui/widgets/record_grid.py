import html
import textwrap

from PySide6.QtCore import QEvent, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QToolTip,
)

MAXIMUM_COLUMN_WIDTH: int = 320
TOOLTIP_LINE_LENGTH: int = 200
TOOLTIP_MAXIMUM_LINES: int = 3
TOOLTIP_ELLIPSIS: str = "..."
TOOLTIP_TEMPLATE: str = "<p style='white-space:pre'>{text}</p>"


def cell_tooltip(text: str) -> str:
    lines: list[str] = []
    for paragraph in text.strip().splitlines():
        lines.extend(textwrap.wrap(paragraph, TOOLTIP_LINE_LENGTH) or [""])
    shown = lines[:TOOLTIP_MAXIMUM_LINES]
    if len(lines) > TOOLTIP_MAXIMUM_LINES:
        kept = shown[-1][: TOOLTIP_LINE_LENGTH - len(TOOLTIP_ELLIPSIS)]
        shown[-1] = f"{kept}{TOOLTIP_ELLIPSIS}"
    return "\n".join(shown)


def tooltip_markup(text: str) -> str:
    return TOOLTIP_TEMPLATE.format(text=html.escape(text).replace("\n", "<br>"))


class CellTooltipDelegate(QStyledItemDelegate):

    def helpEvent(
        self,
        event: QHelpEvent,
        view: QAbstractItemView,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        if event is None or event.type() != QEvent.Type.ToolTip or not index.isValid():
            return super().helpEvent(event, view, option, index)
        content = cell_tooltip(str(index.data(Qt.ItemDataRole.DisplayRole) or ""))
        extra = str(index.data(Qt.ItemDataRole.ToolTipRole) or "").strip()
        text = "\n".join(part for part in (content, extra) if part)
        if not text:
            QToolTip.hideText()
            return True
        QToolTip.showText(event.globalPos(), tooltip_markup(text), view)
        return True


def configure_record_grid(table: QTableWidget) -> None:
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(False)
    table.verticalHeader().setVisible(False)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setItemDelegate(CellTooltipDelegate(table))
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(False)
    header.setSectionsMovable(True)
    header.setTextElideMode(Qt.TextElideMode.ElideRight)


def fit_columns(table: QTableWidget) -> None:
    table.resizeColumnsToContents()
    for column in range(table.columnCount()):
        if table.columnWidth(column) > MAXIMUM_COLUMN_WIDTH:
            table.setColumnWidth(column, MAXIMUM_COLUMN_WIDTH)


def reset_columns(table: QTableWidget) -> None:
    header = table.horizontalHeader()
    for logical in range(header.count()):
        header.moveSection(header.visualIndex(logical), logical)
    fit_columns(table)
