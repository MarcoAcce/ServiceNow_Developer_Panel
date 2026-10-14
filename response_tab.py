import csv
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
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from icons import REFRESH_ICON, IconButton
from service import RequestResult
from tab import Tab
from ui_widgets import (
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
ADDRESS_SEPARATOR: str = " - "
TABLE_NAME_LIMIT: int = 24
INSTANCE_NAME_LIMIT: int = 18


class ResponseTab(Tab):

    refreshRequested = Signal(object)

    def __init__(self, result: RequestResult) -> None:
        super().__init__(self.build_menu_title(result))
        self.result: RequestResult = result
        self._menu_table: str = self.build_menu_table(result)
        self._menu_detail: str = self.build_menu_detail(result)
        self._menu_tooltip: str = self.build_menu_tooltip(result)
        self._refreshing: bool = False
        self.table_widget: QTableWidget = QTableWidget()
        self.filter_field: QLineEdit = QLineEdit()
        self.record_count_label: QLabel = QLabel()
        self.title_hint_label: QLabel = hint_label("")
        self.status_label: QLabel = QLabel()
        self.instance_label: QLabel = QLabel()
        self.authentication_label: QLabel = QLabel()
        self.source_label: QLabel = QLabel()
        self.endpoint_label: QLabel = QLabel()
        self.parameters_label: QLabel = QLabel()
        self.status_value_label: QLabel = QLabel()
        self.received_label: QLabel = QLabel()
        self.refresh_button: IconButton = IconButton(REFRESH_ICON, REFRESH_TOOLTIP)
        self._build_ui()
        self._refresh_summary()
        self._fill_table()

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

    def columns(self) -> tuple[str, ...]:
        return self.result.columns

    def column_label(self, column: str) -> str:
        return column.replace("_", " ").capitalize()

    def build_details(self, layout: QVBoxLayout) -> None:
        return None

    def on_row_selected(self, record: dict[str, str]) -> None:
        return None

    def result_updated(self) -> None:
        return None

    def update_result(self, result: RequestResult) -> None:
        self.result = result
        self._menu_table = self.build_menu_table(result)
        self._menu_detail = self.build_menu_detail(result)
        self._menu_tooltip = self.build_menu_tooltip(result)
        self.set_refreshing(False)
        self._refresh_summary()
        self._fill_table()
        self._apply_filter(self.filter_field.text())
        self.result_updated()
        self.menu_title = self.build_menu_title(result)

    def set_refresh_enabled(self, enabled: bool) -> None:
        self.refresh_button.setEnabled(enabled and not self._refreshing)

    def set_refreshing(self, refreshing: bool) -> None:
        self._refreshing = refreshing
        self.refresh_button.setEnabled(not refreshing)
        show_status(self.status_label, REFRESHING_MESSAGE if refreshing else "")

    def show_refresh_error(self, message: str) -> None:
        self._refreshing = False
        self.refresh_button.setEnabled(True)
        show_status(self.status_label, REFRESH_ERROR_MESSAGE.format(message=message), failed=True)

    def is_closable(self) -> bool:
        return True

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addLayout(self._build_header())
        root.addWidget(self._build_summary())
        root.addWidget(horizontal_rule())
        root.addLayout(self._build_toolbar())
        root.addWidget(self.table_widget)
        self.build_details(root)

        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSortingEnabled(True)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.itemSelectionChanged.connect(self._on_selection_changed)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.addWidget(title_label(self.result.request_type.label))
        header.addWidget(self.title_hint_label, 1)
        self.refresh_button.clicked.connect(lambda: self.refreshRequested.emit(self))
        header.addWidget(self.status_label)
        header.addWidget(self.refresh_button)
        return header

    def _build_summary(self) -> QWidget:
        summary = QWidget()
        layout = QFormLayout(summary)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow("Instance", self.instance_label)
        layout.addRow("Authentication", self.authentication_label)
        layout.addRow("Source", self.source_label)
        layout.addRow("Endpoint", self.endpoint_label)
        layout.addRow("Parameters", self.parameters_label)
        layout.addRow("Status", self.status_value_label)
        layout.addRow("Received", self.received_label)
        layout.addRow("Records", self.record_count_label)
        return summary

    def _refresh_summary(self) -> None:
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
        self.endpoint_label.setText(self.result.endpoint)
        self.parameters_label.setText(self.result.query_string or "none")
        self.status_value_label.setText(
            f"{self.result.status_code} in {self.result.elapsed_ms} ms"
        )
        self.received_label.setText(self.result.executed_at.strftime(SUMMARY_TIME_FORMAT))

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

    def _fill_table(self) -> None:
        columns = self.columns()
        records = self.result.records
        self.table_widget.setSortingEnabled(False)
        self.table_widget.clearContents()
        self.table_widget.setColumnCount(len(columns))
        self.table_widget.setRowCount(len(records))
        self.table_widget.setHorizontalHeaderLabels([self.column_label(column) for column in columns])
        for row, record in enumerate(records):
            for column_index, column in enumerate(columns):
                item = QTableWidgetItem(record.get(column, ""))
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.table_widget.setItem(row, column_index, item)
        self.table_widget.setSortingEnabled(True)
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table_widget.resizeColumnsToContents()
        self._update_record_count(len(records))

    def _update_record_count(self, visible: int) -> None:
        total = len(self.result.records)
        if visible == total:
            self.record_count_label.setText(str(total))
        else:
            self.record_count_label.setText(f"{visible} of {total}")

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        visible = 0
        for row in range(self.table_widget.rowCount()):
            matches = not needle or self._row_matches(row, needle)
            self.table_widget.setRowHidden(row, not matches)
            visible += int(matches)
        self._update_record_count(visible)

    def _row_matches(self, row: int, needle: str) -> bool:
        for column in range(self.table_widget.columnCount()):
            item = self.table_widget.item(row, column)
            if item is not None and needle in item.text().lower():
                return True
        return False

    def _selected_record(self) -> dict[str, str] | None:
        items = self.table_widget.selectedItems()
        if not items:
            return None
        index = items[0].data(Qt.ItemDataRole.UserRole)
        if not isinstance(index, int) or index >= len(self.result.records):
            return None
        return self.result.records[index]

    def _on_selection_changed(self) -> None:
        record = self._selected_record()
        if record is not None:
            self.on_row_selected(record)

    def _save_as_csv(self) -> None:
        suggestion = f"{self.result.table or self.result.request_type.key}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Save response", suggestion, "CSV files (*.csv)")
        if not path:
            return
        columns = self.columns()
        try:
            with Path(path).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self.result.records)
        except OSError as error:
            QMessageBox.warning(self, "Save failed", str(error))
