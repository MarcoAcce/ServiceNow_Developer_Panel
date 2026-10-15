from PySide6.QtCore import Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config_repository import ConfigRepository
from icons import COLLAPSE_ICON, DELETE_ICON, EXPAND_ICON, IconButton, Tone
from multiple_tables_response_tab import MultipleTablesResponseTab
from request_hints import RequestHintRepository
from request_tab import RequestTab
from request_types import MULTIPLE_TABLES
from response_tab import ResponseTab
from service import RequestPart, RequestResult, RequestService, RequestSpec
from table_query_form import TableQueryForm
from ui_widgets import (
    as_row,
    hint_label,
    section_label,
    vertical_spacer,
)

TABLES_SECTION: str = "Tables"
TABLES_HINT: str = (
    "The tables are requested one after the other and cached in the same local database."
)
ADD_TABLE_LABEL: str = "Add table"
ADD_TABLE_TOOLTIP: str = "Add another table to the request"
ADD_TABLE_DISABLED_TOOLTIP: str = "Name the table you just added before adding another one"
NEW_TABLE_TITLE: str = "New table"
EXPAND_TOOLTIP: str = "Show the query of this table"
COLLAPSE_TOOLTIP: str = "Hide the query of this table"
REMOVE_TOOLTIP: str = "Remove this table from the request"
TABLES_REQUIRED_MESSAGE: str = "At least one table is required to send the request."
DUPLICATE_MESSAGE: str = "The table {table} is requested more than once."
ROW_SPACING: int = 6
ROW_MARGIN: int = 8
HEADER_SPACING: int = 6


class TableRequestRow(QFrame):

    changed = Signal()
    expandRequested = Signal(object)
    removeRequested = Signal(object)

    def __init__(self, form: TableQueryForm) -> None:
        super().__init__()
        self.form: TableQueryForm = form
        self.title_label = section_label(NEW_TABLE_TITLE)
        self.expand_button: IconButton = IconButton(COLLAPSE_ICON, COLLAPSE_TOOLTIP)
        self.remove_button: IconButton = IconButton(DELETE_ICON, REMOVE_TOOLTIP, Tone.DANGER)
        self._expanded: bool = True
        self._build_ui()

    def table_name(self) -> str:
        return self.form.table_name()

    def is_empty(self) -> bool:
        return self.form.is_empty()

    def part(self) -> RequestPart | None:
        return self.form.part()

    def focus_table(self) -> None:
        self.form.focus_table()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.form.setVisible(expanded)
        self.expand_button.set_name(COLLAPSE_ICON if expanded else EXPAND_ICON)
        self.expand_button.setToolTip(COLLAPSE_TOOLTIP if expanded else EXPAND_TOOLTIP)

    def set_removable(self, removable: bool) -> None:
        self.remove_button.setEnabled(removable)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if not self._expanded:
            self.expandRequested.emit(self)

    def _build_ui(self) -> None:
        as_row(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ROW_MARGIN, ROW_MARGIN, ROW_MARGIN, ROW_MARGIN)
        layout.setSpacing(ROW_SPACING)
        layout.addLayout(self._build_header())
        layout.addWidget(self.form)
        self.form.changed.connect(self._on_form_changed)
        self.expand_button.clicked.connect(self._on_expand_clicked)
        self.remove_button.clicked.connect(lambda: self.removeRequested.emit(self))

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(HEADER_SPACING)
        header.addWidget(self.expand_button)
        header.addWidget(self.title_label, 1)
        header.addWidget(self.remove_button)
        return header

    def _on_expand_clicked(self) -> None:
        if self._expanded:
            self.set_expanded(False)
            return
        self.expandRequested.emit(self)

    def _on_form_changed(self) -> None:
        self.title_label.setText(self.table_name() or NEW_TABLE_TITLE)
        self.changed.emit()


class MultipleTablesRequestTab(RequestTab):

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        self._rows: list[TableRequestRow] = []
        self._rows_layout: QVBoxLayout = QVBoxLayout()
        self.add_button: QPushButton = QPushButton(ADD_TABLE_LABEL)
        super().__init__(MULTIPLE_TABLES, service, repository, hints)
        self._add_row()

    def parts(self) -> tuple[RequestPart, ...]:
        parts = [row.part() for row in self._rows]
        return tuple(part for part in parts if part is not None)

    def missing_requirement(self) -> str:
        tables = [row.table_name() for row in self._rows if not row.is_empty()]
        if not tables:
            return TABLES_REQUIRED_MESSAGE
        seen: set[str] = set()
        for table in tables:
            if table in seen:
                return DUPLICATE_MESSAGE.format(table=table)
            seen.add(table)
        return ""

    def record_hints(self) -> None:
        for part in self.parts():
            self.record_hint(part.table)

    def build_request(self) -> RequestSpec:
        return RequestSpec(
            request_type=self.request_type,
            table="",
            parameters={},
            columns=(),
            target=self.instance_selector.current_target(),
            parts=self.parts(),
        )

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return MultipleTablesResponseTab(result)

    def refresh_state(self) -> None:
        addable = not self._rows or not self._rows[-1].is_empty()
        self.add_button.setEnabled(addable)
        self.add_button.setToolTip(
            ADD_TABLE_TOOLTIP if addable else ADD_TABLE_DISABLED_TOOLTIP
        )
        for row in self._rows:
            row.set_removable(len(self._rows) > 1)
        super().refresh_state()

    def build_content(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._build_header())
        layout.addWidget(hint_label(TABLES_HINT))
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(ROW_SPACING)
        layout.addLayout(self._rows_layout)
        layout.addWidget(vertical_spacer())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.add_button.clicked.connect(self._on_add_clicked)
        header.addWidget(section_label(TABLES_SECTION))
        header.addStretch(1)
        header.addWidget(self.add_button)
        return header

    def _add_row(self) -> None:
        form = TableQueryForm(self.table_names, self.field_names)
        row = TableRequestRow(form)
        row.changed.connect(self.refresh_state)
        row.expandRequested.connect(self._expand)
        row.removeRequested.connect(self._on_remove_requested)
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        self._expand(row)
        self.refresh_state()
        row.focus_table()

    def _on_add_clicked(self) -> None:
        self._add_row()

    def _expand(self, target: TableRequestRow) -> None:
        for row in self._rows:
            row.set_expanded(row is target)

    def _on_remove_requested(self, row: TableRequestRow) -> None:
        if len(self._rows) <= 1:
            return
        self._rows.remove(row)
        self._rows_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()
        self.refresh_state()
