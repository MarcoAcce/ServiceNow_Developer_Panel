from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_paths import cache_path
from background_task import BackgroundTask
from cache_query import MAXIMUM_ROWS, QueryOutcome, run_script
from dialogs import CLOSE_LABEL, FramelessDialog, ask_confirmation
from response_context import ResponseContext
from response_tab import REFRESHING_MESSAGE, ResponseTab
from service import (
    RequestCall,
    RequestError,
    RequestPart,
    RequestResult,
    RequestSpec,
    ResultSection,
    section_of,
)
from table_query_form import (
    ADD_TABLE_LABEL,
    TableQueryDialog,
    encoded_query_of,
    fields_of,
    limit_of,
    order_of,
)
from ui_widgets import (
    hint_label,
    horizontal_rule,
    primary_button,
    script_editor,
    section_label,
    show_status,
)

TABLES_SECTION: str = "Tables requested"
TABLES_HINT: str = "Click a table to read the query that was sent for it."
TABLE_COLUMN: str = "Table"
RECORDS_COLUMN: str = "Records"
TABLES_HEIGHT: int = 190
TABLES_MARGIN: int = 4
CONSOLE_SECTION: str = "Query the local cache"
CONSOLE_HINT: str = (
    "Every requested table is a table of the local cache database: {tables}. "
    f"At most {MAXIMUM_ROWS} rows are shown."
)
CONSOLE_UNAVAILABLE_HINT: str = (
    "This response has no local cache database, so it cannot be queried."
)
QUERY_PLACEHOLDER: str = "SELECT * FROM incident LIMIT 50"
EXECUTE_QUERY_LABEL: str = "Execute query"
NEW_QUERY_LABEL: str = "New query"
RUNNING_QUERY_MESSAGE: str = "Running the query..."
QUERY_ERROR_MESSAGE: str = "Query failed: {message}"
ROWS_MESSAGE: str = "{count} rows."
TRUNCATED_MESSAGE: str = "First {count} rows, the result is longer."
CHANGES_MESSAGE: str = "The script ran, {changes} rows changed."
ADD_TABLE_TOOLTIP: str = "Request another table into the cache of this response"
ADDING_MESSAGE: str = "Requesting the new table..."
REQUESTING_MESSAGE: str = "Requesting every table again..."
STALE_TITLE: str = "Cache no longer up to date"
STALE_MESSAGE: str = (
    "The local cache of this response is expired, so the new table cannot be added to it. "
    "Every table of this request, including the new one, can be requested again instead."
)
REQUEST_AGAIN_LABEL: str = "Request everything"
DETAILS_TITLE: str = "Query sent for {table}"
DETAILS_WIDTH: int = 520
DETAILS_NONE: str = "none"
SINGLE_TABLE_LABEL: str = "1 table"
TABLE_COUNT_LABEL: str = "{count} tables"
EDITOR_PAGE: int = 0
RESULT_PAGE: int = 1
TABLE_COLUMN_INDEX: int = 0
COUNT_COLUMN_INDEX: int = 1
TABLE_SEPARATOR: str = ", "


def table_count(count: int) -> str:
    if count == 1:
        return SINGLE_TABLE_LABEL
    return TABLE_COUNT_LABEL.format(count=count)


class TableDetailsDialog(FramelessDialog):

    def __init__(self, section: ResultSection, parent: QWidget | None = None) -> None:
        super().__init__(DETAILS_TITLE.format(table=section.table), parent)
        self.setMinimumWidth(DETAILS_WIDTH)
        self._build_ui(section)

    def _build_ui(self, section: ResultSection) -> None:
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(TABLE_COLUMN, self._value(section.table))
        form.addRow(RECORDS_COLUMN, self._value(str(len(section.records))))
        form.addRow("Requested", self._value(limit_of(section.parameters)))
        form.addRow("Fields", self._value(fields_of(section.parameters)))
        form.addRow("Order by", self._value(order_of(section.parameters)))
        form.addRow("Encoded query", self._value(encoded_query_of(section.parameters)))
        self.content_layout.addLayout(form)
        close_button = primary_button(CLOSE_LABEL)
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        self.add_button_row(close_button)

    def _value(self, text: str) -> QLabel:
        label = QLabel(text or DETAILS_NONE)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        return label


class MultipleTablesResponseTab(ResponseTab):

    def __init__(self, result: RequestResult) -> None:
        self._running: bool = False
        self._enabled: bool = True
        self._call: RequestCall | None = None
        self._query_task: BackgroundTask | None = None
        self._store_task: BackgroundTask | None = None
        self.tables_widget: QTableWidget = QTableWidget()
        self.table_count_label: QLabel = QLabel()
        self.record_count_label: QLabel = QLabel()
        self.console_hint_label: QLabel = hint_label("")
        self.console_status_label: QLabel = QLabel()
        self.pages: QStackedWidget = QStackedWidget()
        self.query_input: QPlainTextEdit = script_editor(QUERY_PLACEHOLDER)
        self.execute_button: QPushButton = primary_button(EXECUTE_QUERY_LABEL)
        self.result_widget: QTableWidget = QTableWidget()
        self.result_label: QLabel = QLabel()
        self.new_query_button: QPushButton = QPushButton(NEW_QUERY_LABEL)
        self.add_button: QPushButton = QPushButton(ADD_TABLE_LABEL)
        super().__init__(result)

    def build_menu_table(self, result: RequestResult) -> str:
        return table_count(len(result.sections))

    def attach(self, context: ResponseContext) -> None:
        super().attach(context)
        self._refresh_add_state()

    def build_summary_rows(self, layout: QFormLayout) -> None:
        super().build_summary_rows(layout)
        layout.addRow("Tables", self.table_count_label)
        layout.addRow("Records", self.record_count_label)

    def refresh_summary(self) -> None:
        super().refresh_summary()
        self.table_count_label.setText(str(len(self.result.sections)))
        self.record_count_label.setText(str(len(self.result.records)))

    def fill_content(self) -> None:
        self._fill_tables()
        self._refresh_console()

    def cancel(self) -> None:
        self._release_call(cancel=True)
        cancel_task(self._query_task)
        cancel_task(self._store_task)
        self._query_task = None
        self._store_task = None
        if self._running:
            self._finish()

    def set_refreshing(self, refreshing: bool, message: str = REFRESHING_MESSAGE) -> None:
        super().set_refreshing(refreshing, message)
        self._refresh_add_state()

    def set_refresh_enabled(self, enabled: bool) -> None:
        super().set_refresh_enabled(enabled)
        self._enabled = enabled
        self._refresh_add_state()

    def build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(section_label(TABLES_SECTION))
        layout.addWidget(hint_label(TABLES_HINT))
        layout.addWidget(self.tables_widget)
        layout.addWidget(horizontal_rule())
        layout.addWidget(section_label(CONSOLE_SECTION))
        layout.addWidget(self.console_hint_label)
        layout.addWidget(self.pages, 1)
        layout.addWidget(horizontal_rule())
        layout.addLayout(self._build_footer())
        self._configure_tables()
        self._build_pages()

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        self.add_button.setToolTip(ADD_TABLE_TOOLTIP)
        self.add_button.clicked.connect(self._on_add_clicked)
        footer.addStretch(1)
        footer.addWidget(self.add_button)
        return footer

    def _configure_tables(self) -> None:
        configure_table(self.tables_widget)
        self.tables_widget.setColumnCount(2)
        self.tables_widget.setHorizontalHeaderLabels([TABLE_COLUMN, RECORDS_COLUMN])
        header = self.tables_widget.horizontalHeader()
        header.setSectionResizeMode(TABLE_COLUMN_INDEX, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            COUNT_COLUMN_INDEX, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tables_widget.itemClicked.connect(self._on_table_clicked)
        configure_table(self.result_widget)

    def _build_pages(self) -> None:
        self.pages.addWidget(self._build_editor_page())
        self.pages.addWidget(self._build_result_page())
        self.pages.setCurrentIndex(EDITOR_PAGE)

    def _build_editor_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.query_input, 1)
        row = QHBoxLayout()
        self.console_status_label.setWordWrap(True)
        self.execute_button.clicked.connect(self._on_execute_clicked)
        row.addWidget(self.console_status_label, 1)
        row.addWidget(self.execute_button)
        layout.addLayout(row)
        return page

    def _build_result_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.result_widget, 1)
        row = QHBoxLayout()
        self.result_label.setWordWrap(True)
        self.new_query_button.clicked.connect(self._on_new_query_clicked)
        row.addWidget(self.result_label, 1)
        row.addWidget(self.new_query_button)
        layout.addLayout(row)
        return page

    def _fill_tables(self) -> None:
        sections = self.result.sections
        self.tables_widget.clearContents()
        self.tables_widget.setRowCount(len(sections))
        for row, section in enumerate(sections):
            name_item = QTableWidgetItem(section.table)
            name_item.setData(Qt.ItemDataRole.UserRole, row)
            count_item = QTableWidgetItem(str(len(section.records)))
            count_item.setData(Qt.ItemDataRole.UserRole, row)
            count_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.tables_widget.setItem(row, TABLE_COLUMN_INDEX, name_item)
            self.tables_widget.setItem(row, COUNT_COLUMN_INDEX, count_item)
        self._resize_tables()

    def _resize_tables(self) -> None:
        height = self.tables_widget.horizontalHeader().height() + TABLES_MARGIN
        for row in range(self.tables_widget.rowCount()):
            height += self.tables_widget.rowHeight(row)
        self.tables_widget.setFixedHeight(min(height, TABLES_HEIGHT))

    def _refresh_console(self) -> None:
        available = bool(self.result.cache_name)
        tables = TABLE_SEPARATOR.join(section.table for section in self.result.sections)
        self.console_hint_label.setText(
            CONSOLE_HINT.format(tables=tables) if available else CONSOLE_UNAVAILABLE_HINT
        )
        self.query_input.setEnabled(available)
        self.execute_button.setEnabled(available)
        self._reset_console()

    def _reset_console(self) -> None:
        self.result_widget.clearContents()
        self.result_widget.setRowCount(0)
        self.result_widget.setColumnCount(0)
        self.result_label.clear()
        show_status(self.console_status_label, "")
        self.pages.setCurrentIndex(EDITOR_PAGE)

    def _on_table_clicked(self, item: QTableWidgetItem) -> None:
        index = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(index, int) or index >= len(self.result.sections):
            return
        TableDetailsDialog(self.result.sections[index], self).exec()

    def _on_new_query_clicked(self) -> None:
        self._reset_console()
        self.query_input.setFocus()

    def _on_execute_clicked(self) -> None:
        if self._query_task is not None:
            return
        path = cache_path(self.result.cache_name)
        script = self.query_input.toPlainText()
        show_status(self.console_status_label, RUNNING_QUERY_MESSAGE)
        self.execute_button.setEnabled(False)
        task = BackgroundTask(lambda: run_script(path, script), self)
        task.finished.connect(self._on_query_finished)
        task.failed.connect(self._on_query_failed)
        self._query_task = task
        task.start()

    def _on_query_finished(self, value: object) -> None:
        self._release_query()
        if not isinstance(value, QueryOutcome):
            return
        self._show_outcome(value)
        self.pages.setCurrentIndex(RESULT_PAGE)

    def _on_query_failed(self, message: str) -> None:
        self._release_query()
        show_status(
            self.console_status_label,
            QUERY_ERROR_MESSAGE.format(message=message),
            failed=True,
        )

    def _release_query(self) -> None:
        self._query_task = None
        self.execute_button.setEnabled(bool(self.result.cache_name))
        show_status(self.console_status_label, "")

    def _show_outcome(self, outcome: QueryOutcome) -> None:
        self.result_widget.clearContents()
        self.result_widget.setColumnCount(len(outcome.columns))
        self.result_widget.setHorizontalHeaderLabels(list(outcome.columns))
        self.result_widget.setRowCount(len(outcome.rows))
        for row, values in enumerate(outcome.rows):
            for column, value in enumerate(values):
                self.result_widget.setItem(row, column, QTableWidgetItem(value))
        self.result_widget.resizeColumnsToContents()
        self.result_label.setText(outcome_message(outcome))

    def _requested_tables(self) -> tuple[str, ...]:
        return tuple(section.table for section in self.result.sections)

    def _table_names(self) -> list[str]:
        context = self.context
        if context is None:
            return []
        return context.hints.table_names(self.result.request_type.key)

    def _field_names(self, table: str) -> list[str]:
        context = self.context
        if context is None:
            return []
        return context.hints.field_names(self.result.request_type.key, table)

    def _refresh_add_state(self) -> None:
        ready = self.context is not None and not self.is_refreshing and not self._running
        self.add_button.setEnabled(self._enabled and ready)

    def _on_add_clicked(self) -> None:
        context = self.context
        if context is None or self._running:
            return
        dialog = TableQueryDialog(
            self, self._table_names, self._field_names, self._requested_tables()
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        part = dialog.part()
        if part is None:
            return
        if context.responses.is_current(self.result):
            self._send_part(context, part)
            return
        if ask_confirmation(self, STALE_TITLE, STALE_MESSAGE, REQUEST_AGAIN_LABEL):
            self._send_all(context, part)

    def _send_part(self, context: ResponseContext, part: RequestPart) -> None:
        spec = RequestSpec(
            request_type=self.result.request_type,
            table=part.table,
            parameters=part.parameters,
            columns=part.columns,
            target=self.result.target,
        ).transient()
        self._start(ADDING_MESSAGE)
        call = context.service.send(spec)
        call.succeeded.connect(self._on_part_succeeded)
        call.failed.connect(self._on_request_failed)
        self._call = call

    def _send_all(self, context: ResponseContext, part: RequestPart) -> None:
        self._start(REQUESTING_MESSAGE)
        call = context.service.send(self.result.request.extended(part).refreshed())
        call.succeeded.connect(self._on_all_succeeded)
        call.failed.connect(self._on_request_failed)
        self._call = call

    def _on_part_succeeded(self, result: RequestResult) -> None:
        self._release_call()
        self._record_hints((result.table,))
        context = self.context
        if context is None:
            self._finish()
            return
        section = section_of(result)
        task = BackgroundTask(lambda: context.responses.extend(self.result, section), self)
        task.finished.connect(self._on_stored)
        task.failed.connect(self._on_store_failed)
        self._store_task = task
        task.start()

    def _on_all_succeeded(self, result: RequestResult) -> None:
        self._release_call()
        self._record_hints([section.table for section in result.sections])
        self.update_result(result)
        self._finish()

    def _record_hints(self, tables: Sequence[str]) -> None:
        context = self.context
        if context is None:
            return
        for table in tables:
            context.hints.record(self.result.request_type.key, table)

    def _on_stored(self, value: object) -> None:
        self._store_task = None
        if isinstance(value, RequestResult):
            self.update_result(value)
        self._finish()

    def _on_store_failed(self, message: str) -> None:
        self._store_task = None
        self._finish()
        self.show_refresh_error(message)

    def _on_request_failed(self, error: RequestError) -> None:
        self._release_call()
        self._finish()
        self.show_refresh_error(error.message)

    def _start(self, message: str) -> None:
        self._running = True
        self.runningChanged.emit(True)
        self.set_refreshing(True, message)

    def _finish(self) -> None:
        self._running = False
        self.set_refreshing(False)
        self.runningChanged.emit(False)

    def _release_call(self, cancel: bool = False) -> None:
        call = self._call
        self._call = None
        if call is None:
            return
        if cancel:
            call.cancel()
        call.deleteLater()


def configure_table(widget: QTableWidget) -> None:
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setAlternatingRowColors(True)
    widget.setSortingEnabled(False)
    widget.verticalHeader().setVisible(False)
    widget.horizontalHeader().setStretchLastSection(True)


def cancel_task(task: BackgroundTask | None) -> None:
    if task is not None:
        task.cancel()


def outcome_message(outcome: QueryOutcome) -> str:
    if not outcome.has_rows:
        return CHANGES_MESSAGE.format(changes=outcome.changes)
    if outcome.truncated:
        return TRUNCATED_MESSAGE.format(count=len(outcome.rows))
    return ROWS_MESSAGE.format(count=len(outcome.rows))
