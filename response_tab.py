import csv
from pathlib import Path

from PySide6.QtCore import Qt
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

from service import RequestResult
from tab import Tab
from ui_widgets import horizontal_rule, section_label, title_label

SUMMARY_TIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
MENU_TIME_FORMAT: str = "%H:%M:%S"


class ResponseTab(Tab):

    def __init__(self, result: RequestResult) -> None:
        super().__init__(self.build_menu_title(result))
        self.result: RequestResult = result
        self.table_widget: QTableWidget = QTableWidget()
        self.filter_field: QLineEdit = QLineEdit()
        self.record_count_label: QLabel = QLabel()
        self._build_ui()
        self._fill_table()

    def build_menu_title(self, result: RequestResult) -> str:
        label = result.table or result.request_type.label
        return f"{label} ({result.executed_at.strftime(MENU_TIME_FORMAT)})"

    def columns(self) -> tuple[str, ...]:
        return self.result.columns

    def column_label(self, column: str) -> str:
        return column.replace("_", " ").capitalize()

    def build_details(self, layout: QVBoxLayout) -> None:
        return None

    def on_row_selected(self, record: dict[str, str]) -> None:
        return None

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(title_label(self.result.request_type.label))
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

    def _build_summary(self) -> QWidget:
        summary = QWidget()
        layout = QFormLayout(summary)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow("Source", QLabel(self.result.source))
        layout.addRow("Endpoint", QLabel(self.result.endpoint))
        layout.addRow("Parameters", QLabel(self.result.query_string or "none"))
        layout.addRow("Status", QLabel(f"{self.result.status_code} in {self.result.elapsed_ms} ms"))
        layout.addRow("Received", QLabel(self.result.executed_at.strftime(SUMMARY_TIME_FORMAT)))
        layout.addRow("Records", self.record_count_label)
        return summary

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

    def is_closable(self) -> bool:
        return True
