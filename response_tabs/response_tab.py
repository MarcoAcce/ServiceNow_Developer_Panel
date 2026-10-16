from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.dialogs import show_error
from ui.icons import REFRESH_ICON, IconButton
from core.record_columns import ordered_columns
from response_tabs.response_context import ResponseContext
from services.service import RequestResult
from ui.tab import Tab
from storage.table_export import write_csv
from ui.ui_widgets import (
    check_item,
    hint_label,
    horizontal_rule,
    section_label,
    shorten_text,
    show_status,
    title_label,
)

SUMMARY_TIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
MENU_TIME_FORMAT: str = "%H:%M:%S"
DETAIL_SEPARATOR: str = " · "
REFRESH_TOOLTIP: str = "Run this request again on the same instance"
REFRESHING_MESSAGE: str = "Running the request again..."
REFRESH_ERROR_MESSAGE: str = "Refresh failed: {message}"
SAVE_ERROR_TITLE: str = "Save failed"
ADDRESS_SEPARATOR: str = " - "
TABLE_NAME_LIMIT: int = 24
INSTANCE_NAME_LIMIT: int = 18
PAGE_SIZE: int = 100
PREVIOUS_LABEL: str = "Previous"
NEXT_LABEL: str = "Next"
PAGE_TEXT: str = "Page {page} of {pages}"
RANGE_TEXT: str = "{start} to {end} of {count}"
MATCHING_TEXT: str = "{start} to {end} of {matching} matching, {total} received"
NO_MATCH_TEXT: str = "0 of {total}"
PAGER_SPACING: int = 8
TRUE_VALUE: str = "true"


def received_columns(result: RequestResult) -> tuple[str, ...]:
    return ordered_columns(result.columns, result.records) or result.columns


class ResponseTab(Tab):

    refreshRequested = Signal(object)
    runningChanged = Signal(bool)

    def __init__(self, result: RequestResult) -> None:
        super().__init__(self.build_menu_title(result))
        self.result: RequestResult = result
        self._menu_table: str = self.build_menu_table(result)
        self._menu_detail: str = self.build_menu_detail(result)
        self._menu_tooltip: str = self.build_menu_tooltip(result)
        self._refreshing: bool = False
        self._context: ResponseContext | None = None
        self.title_hint_label: QLabel = hint_label("")
        self.status_label: QLabel = QLabel()
        self.instance_label: QLabel = QLabel()
        self.authentication_label: QLabel = QLabel()
        self.source_label: QLabel = QLabel()
        self.status_value_label: QLabel = QLabel()
        self.received_label: QLabel = QLabel()
        self.refresh_button: IconButton = IconButton(REFRESH_ICON, REFRESH_TOOLTIP)
        self._build_ui()
        self.refresh_summary()
        self.fill_content()

    @property
    def menu_table(self) -> str:
        return self._menu_table

    @property
    def menu_detail(self) -> str:
        return self._menu_detail

    @property
    def menu_tooltip(self) -> str:
        return self._menu_tooltip

    def build_menu_title(self, result: RequestResult) -> str:
        return result.request_type.label

    def build_menu_table(self, result: RequestResult) -> str:
        return shorten_text(result.table, TABLE_NAME_LIMIT)

    def build_menu_detail(self, result: RequestResult) -> str:
        return DETAIL_SEPARATOR.join(
            (
                shorten_text(result.target.label, INSTANCE_NAME_LIMIT),
                result.executed_at.strftime(MENU_TIME_FORMAT),
            )
        )

    def build_menu_tooltip(self, result: RequestResult) -> str:
        lines = (
            result.request_type.label,
            result.table,
            DETAIL_SEPARATOR.join(
                (result.target.label, result.executed_at.strftime(SUMMARY_TIME_FORMAT))
            ),
        )
        return "\n".join(line for line in lines if line)

    @property
    def context(self) -> ResponseContext | None:
        return self._context

    def attach(self, context: ResponseContext) -> None:
        self._context = context

    def build_body(self, layout: QVBoxLayout) -> None:
        raise NotImplementedError

    def build_summary_rows(self, layout: QFormLayout) -> None:
        layout.addRow("Instance", self.instance_label)
        layout.addRow("Authentication", self.authentication_label)
        layout.addRow("Source", self.source_label)
        layout.addRow("Status", self.status_value_label)
        layout.addRow("Received", self.received_label)

    def fill_content(self) -> None:
        return None

    def cancel(self) -> None:
        return None

    def update_result(self, result: RequestResult) -> None:
        self.result = result
        self._menu_table = self.build_menu_table(result)
        self._menu_detail = self.build_menu_detail(result)
        self._menu_tooltip = self.build_menu_tooltip(result)
        self.set_refreshing(False)
        self.refresh_summary()
        self.fill_content()
        self.menu_title = self.build_menu_title(result)

    def set_refresh_enabled(self, enabled: bool) -> None:
        self.refresh_button.setEnabled(enabled and not self._refreshing)

    def set_refreshing(self, refreshing: bool, message: str = REFRESHING_MESSAGE) -> None:
        self._refreshing = refreshing
        self.refresh_button.setEnabled(not refreshing)
        show_status(self.status_label, message if refreshing else "")

    def show_refresh_error(self, message: str) -> None:
        self._refreshing = False
        self.refresh_button.setEnabled(True)
        show_status(self.status_label, REFRESH_ERROR_MESSAGE.format(message=message), failed=True)

    def is_closable(self) -> bool:
        return True

    @property
    def is_refreshing(self) -> bool:
        return self._refreshing

    def refresh_summary(self) -> None:
        target = self.result.target
        address = target.address
        self.title_hint_label.setText(
            DETAIL_SEPARATOR.join(
                (target.label, self.result.executed_at.strftime(MENU_TIME_FORMAT))
            )
        )
        self.instance_label.setText(
            f"{target.label}{ADDRESS_SEPARATOR}{address}" if address else target.label
        )
        self.authentication_label.setText(target.authentication_label)
        self.source_label.setText(self.result.source)
        self.status_value_label.setText(
            f"{self.result.status_code} in {self.result.elapsed_ms} ms"
        )
        self.received_label.setText(self.result.executed_at.strftime(SUMMARY_TIME_FORMAT))

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addLayout(self._build_header())
        root.addWidget(self._build_summary())
        root.addWidget(horizontal_rule())
        self.build_body(root)

    def _build_summary(self) -> QWidget:
        summary = QWidget()
        layout = QFormLayout(summary)
        layout.setContentsMargins(0, 0, 0, 0)
        self.build_summary_rows(layout)
        return summary

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.addWidget(title_label(self.result.request_type.label))
        header.addWidget(self.title_hint_label, 1)
        self.refresh_button.clicked.connect(lambda: self.refreshRequested.emit(self))
        header.addWidget(self.status_label)
        header.addWidget(self.refresh_button)
        return header

class RecordsResponseTab(ResponseTab):

    def __init__(self, result: RequestResult) -> None:
        self._columns: tuple[str, ...] = ()
        self._checkboxes: tuple[str, ...] = ()
        self._filtered: list[int] = []
        self._page: int = 0
        self._sort_column: int = -1
        self._sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
        self.table_widget: QTableWidget = QTableWidget()
        self.pager: QWidget = QWidget()
        self.previous_button: QPushButton = QPushButton(PREVIOUS_LABEL)
        self.next_button: QPushButton = QPushButton(NEXT_LABEL)
        self.page_label: QLabel = QLabel()
        self.filter_field: QLineEdit = QLineEdit()
        self.record_count_label: QLabel = QLabel()
        self.endpoint_label: QLabel = QLabel()
        self.parameters_label: QLabel = QLabel()
        super().__init__(result)

    def columns(self) -> tuple[str, ...]:
        return received_columns(self.result)

    def checkbox_columns(self) -> tuple[str, ...]:
        return ()

    def export_columns(self) -> tuple[str, ...]:
        return received_columns(self.result)

    def records(self) -> list[dict[str, str]]:
        return self.result.records

    def column_label(self, column: str) -> str:
        return column.replace("_", " ").capitalize()

    def build_details(self, layout: QVBoxLayout) -> None:
        return None

    def on_row_selected(self, record: dict[str, str]) -> None:
        return None

    def build_summary_rows(self, layout: QFormLayout) -> None:
        super().build_summary_rows(layout)
        layout.addRow("Endpoint", self.endpoint_label)
        layout.addRow("Parameters", self.parameters_label)
        layout.addRow("Records", self.record_count_label)

    def refresh_summary(self) -> None:
        super().refresh_summary()
        self.endpoint_label.setText(self.result.endpoint)
        self.parameters_label.setText(self.result.query_string or "none")

    def fill_content(self) -> None:
        self._fill_table()

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addLayout(self._build_toolbar())
        layout.addWidget(self.table_widget)
        layout.addWidget(self._build_pager())
        self.build_details(layout)

        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSortingEnabled(False)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.itemSelectionChanged.connect(self._on_selection_changed)
        header = self.table_widget.horizontalHeader()
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_section_clicked)

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        self.filter_field.setPlaceholderText("Filter the rows below")
        self.filter_field.setClearButtonEnabled(True)
        self.filter_field.textChanged.connect(self._apply_filter)
        save_button = QPushButton("Save as CSV")
        save_button.clicked.connect(self._save_as_csv)
        toolbar.addWidget(section_label("Result"))
        toolbar.addWidget(self.filter_field, 1)
        toolbar.addWidget(save_button)
        return toolbar

    def _build_pager(self) -> QWidget:
        layout = QHBoxLayout(self.pager)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PAGER_SPACING)
        self.previous_button.clicked.connect(self._on_previous_page)
        self.next_button.clicked.connect(self._on_next_page)
        layout.addStretch(1)
        layout.addWidget(self.previous_button)
        layout.addWidget(self.page_label)
        layout.addWidget(self.next_button)
        return self.pager

    def _fill_table(self) -> None:
        self._columns = self.columns()
        self._checkboxes = self.checkbox_columns()
        self._sort_column = -1
        self._sort_order = Qt.SortOrder.AscendingOrder
        self.table_widget.clearContents()
        self.table_widget.setColumnCount(len(self._columns))
        self.table_widget.setHorizontalHeaderLabels(
            [self.column_label(column) for column in self._columns]
        )
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setSortIndicatorShown(False)
        self._apply_filter(self.filter_field.text())

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        records = self.records()
        if needle:
            self._filtered = [
                index
                for index, record in enumerate(records)
                if self._record_matches(record, needle)
            ]
        else:
            self._filtered = list(range(len(records)))
        self._sort_filtered()
        self._page = 0
        self._fill_page()

    def _record_matches(self, record: dict[str, str], needle: str) -> bool:
        return any(needle in record.get(column, "").lower() for column in self._columns)

    def _sort_filtered(self) -> None:
        if not 0 <= self._sort_column < len(self._columns):
            return
        column = self._columns[self._sort_column]
        records = self.records()
        self._filtered.sort(
            key=lambda index: records[index].get(column, "").lower(),
            reverse=self._sort_order == Qt.SortOrder.DescendingOrder,
        )

    def _fill_page(self) -> None:
        records = self.records()
        indexes = self._page_indexes()
        self.table_widget.clearContents()
        self.table_widget.setRowCount(len(indexes))
        for row, index in enumerate(indexes):
            record = records[index]
            for column_index, column in enumerate(self._columns):
                item = self._cell_item(column, record)
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.table_widget.setItem(row, column_index, item)
        self.table_widget.resizeColumnsToContents()
        self._update_pager()
        self._update_record_count()

    def _page_indexes(self) -> list[int]:
        start = self._page * PAGE_SIZE
        return self._filtered[start : start + PAGE_SIZE]

    def _page_count(self) -> int:
        return max(1, (len(self._filtered) + PAGE_SIZE - 1) // PAGE_SIZE)

    def _update_pager(self) -> None:
        pages = self._page_count()
        self.pager.setVisible(len(self._filtered) > PAGE_SIZE)
        self.page_label.setText(PAGE_TEXT.format(page=self._page + 1, pages=pages))
        self.previous_button.setEnabled(self._page > 0)
        self.next_button.setEnabled(self._page + 1 < pages)

    def _cell_item(self, column: str, record: dict[str, str]) -> QTableWidgetItem:
        value = record.get(column, "")
        if column not in self._checkboxes:
            return QTableWidgetItem(value)
        return check_item(value == TRUE_VALUE)

    def _update_record_count(self) -> None:
        total = len(self.records())
        matching = len(self._filtered)
        if not matching:
            self.record_count_label.setText(NO_MATCH_TEXT.format(total=total))
            return
        start = self._page * PAGE_SIZE + 1
        end = min(start + PAGE_SIZE - 1, matching)
        if matching != total:
            text = MATCHING_TEXT.format(start=start, end=end, matching=matching, total=total)
        elif matching <= PAGE_SIZE:
            text = str(total)
        else:
            text = RANGE_TEXT.format(start=start, end=end, count=total)
        self.record_count_label.setText(text)

    def _on_previous_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._fill_page()

    def _on_next_page(self) -> None:
        if self._page + 1 < self._page_count():
            self._page += 1
            self._fill_page()

    def _on_section_clicked(self, index: int) -> None:
        if index == self._sort_column:
            self._sort_order = (
                Qt.SortOrder.DescendingOrder
                if self._sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            self._sort_column = index
            self._sort_order = Qt.SortOrder.AscendingOrder
        header = self.table_widget.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self._sort_column, self._sort_order)
        self._sort_filtered()
        self._page = 0
        self._fill_page()

    def _selected_record(self) -> dict[str, str] | None:
        items = self.table_widget.selectedItems()
        if not items:
            return None
        records = self.records()
        index = items[0].data(Qt.ItemDataRole.UserRole)
        if not isinstance(index, int) or index >= len(records):
            return None
        return records[index]

    def _on_selection_changed(self) -> None:
        record = self._selected_record()
        if record is not None:
            self.on_row_selected(record)

    def _save_as_csv(self) -> None:
        suggestion = f"{self.result.table or self.result.request_type.key}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Save response", suggestion, "CSV files (*.csv)")
        if not path:
            return
        try:
            write_csv(Path(path), self.export_columns(), self.records())
        except OSError as error:
            show_error(self, SAVE_ERROR_TITLE, str(error))
