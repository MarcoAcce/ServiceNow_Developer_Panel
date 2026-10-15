from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from acl_controls import controls_of
from acl_verification import (
    DECISION_DENIED,
    LEVEL_LABELS,
    ControlCheck,
    Verification,
    VerificationOutcome,
    evaluate,
)
from flow_graph import FlowGraph
from response_tab import DETAIL_SEPARATOR, TABLE_NAME_LIMIT, ResponseTab
from service import RequestResult
from theme import Role, refresh_role, set_role
from ui_widgets import (
    check_item,
    configure_table,
    hint_label,
    horizontal_rule,
    script_view,
    section_label,
    shorten_text,
    show_status,
    title_label,
    vertical_spacer,
)

VERDICT_POINT_SIZE_DELTA: int = 2
CONTROLS_SECTION: str = "Access controls evaluated"
CONTROLS_HINT: str = "Click a control to read its condition and its script."
CONTROLS_HEIGHT: int = 170
CONTROLS_MARGIN: int = 4
CONDITION_LABEL: str = "Condition"
CONDITION_PLACEHOLDER: str = "Select a control to read its condition."
SCRIPT_SECTION: str = "Control script"
SCRIPT_PLACEHOLDER: str = "Select a control to read its script."
SCRIPT_HEIGHT: int = 130
FLOW_SECTION: str = "Conditions and scripts to satisfy"
FLOW_HINT: str = (
    "Every stage has to be satisfied, from left to right. The text form of the same "
    "flow can be copied with the export button."
)
FLOW_TEXT_HEIGHT: int = 58
FLOW_PLACEHOLDER: str = "No condition and no script has to be satisfied."
GRAPH_HEIGHT: int = 230
GRAPH_ALLOWANCE: int = 20
EXPORT_LABEL: str = "Export flow"
EXPORT_TOOLTIP: str = "Copy the text form of the flow to the clipboard"
COPIED_MESSAGE: str = "The flow was copied to the clipboard."
CHECKED_ROW: str = "Checked"
ROLES_ROW: str = "Roles"
CONTROLS_ROW: str = "Access controls"
COLUMN_LABELS: tuple[str, ...] = (
    "Level",
    "Control",
    "Decision",
    "Roles",
    "Condition",
    "Script",
    "Roles match",
)
CONTROL_COLUMN_INDEX: int = 1
ROLES_COLUMN_INDEX: int = 3
CHECK_COLUMN_INDEXES: tuple[int, ...] = (4, 5, 6)


class VerifySecurityResponseTab(ResponseTab):

    def __init__(self, result: RequestResult, verification: Verification) -> None:
        self._verification: Verification = verification
        self._outcome: VerificationOutcome | None = None
        self._checks: tuple[ControlCheck, ...] = ()
        self.verdict_label: QLabel = title_label("", VERDICT_POINT_SIZE_DELTA)
        self.reasons_label: QLabel = hint_label("")
        self.checked_label: QLabel = QLabel()
        self.roles_label: QLabel = QLabel()
        self.controls_count_label: QLabel = QLabel()
        self.controls_widget: QTableWidget = QTableWidget()
        self.condition_field: QLineEdit = QLineEdit()
        self.script_preview: QPlainTextEdit = script_view(SCRIPT_PLACEHOLDER)
        self.flow_field: QPlainTextEdit = script_view(FLOW_PLACEHOLDER)
        self.flow_status_label: QLabel = QLabel()
        self.export_button: QPushButton = QPushButton(EXPORT_LABEL)
        self.graph: FlowGraph = FlowGraph()
        self.graph_area: QScrollArea = QScrollArea()
        super().__init__(result)

    @property
    def verification(self) -> Verification:
        return self._verification

    @property
    def outcome(self) -> VerificationOutcome | None:
        return self._outcome

    @property
    def flow_text(self) -> str:
        return self._outcome.text if self._outcome is not None else ""

    def build_menu_table(self, result: RequestResult) -> str:
        return shorten_text(self._verification.target, TABLE_NAME_LIMIT)

    def build_summary_rows(self, layout: QFormLayout) -> None:
        super().build_summary_rows(layout)
        layout.addRow(CHECKED_ROW, self.checked_label)
        layout.addRow(ROLES_ROW, self.roles_label)
        layout.addRow(CONTROLS_ROW, self.controls_count_label)

    def refresh_summary(self) -> None:
        super().refresh_summary()
        verification = self._verification
        self.checked_label.setText(
            DETAIL_SEPARATOR.join((verification.target, verification.operation))
        )
        self.roles_label.setText(verification.role_label)

    def build_body(self, layout: QVBoxLayout) -> None:
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(self.verdict_label)
        body.addWidget(self.reasons_label)
        body.addWidget(horizontal_rule())
        body.addWidget(section_label(FLOW_SECTION))
        body.addWidget(hint_label(FLOW_HINT))
        body.addWidget(self._build_flow_text())
        body.addLayout(self._build_export_row())
        body.addWidget(self._build_graph())
        body.addWidget(horizontal_rule())
        body.addWidget(section_label(CONTROLS_SECTION))
        body.addWidget(hint_label(CONTROLS_HINT))
        body.addWidget(self.controls_widget)
        self._build_details(body)
        body.addWidget(vertical_spacer())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self._configure_controls()

    def fill_content(self) -> None:
        outcome = evaluate(self._verification, controls_of(self.result))
        self._outcome = outcome
        self._checks = outcome.checks
        self.controls_count_label.setText(str(len(self._checks)))
        self._show_verdict(outcome)
        self._fill_controls()
        self._clear_details()
        self.flow_field.setPlainText(outcome.text)
        self.export_button.setEnabled(bool(outcome.text))
        self.graph.set_stages(outcome.stages)
        self._resize_graph()
        show_status(self.flow_status_label, "")

    def _build_details(self, body: QVBoxLayout) -> None:
        self.condition_field.setReadOnly(True)
        self.condition_field.setPlaceholderText(CONDITION_PLACEHOLDER)
        set_role(self.condition_field, Role.MONOSPACE)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(CONDITION_LABEL, self.condition_field)
        body.addLayout(form)
        self.script_preview.setFixedHeight(SCRIPT_HEIGHT)
        body.addWidget(section_label(SCRIPT_SECTION))
        body.addWidget(self.script_preview)

    def _build_export_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.flow_status_label.setWordWrap(True)
        self.export_button.setToolTip(EXPORT_TOOLTIP)
        self.export_button.clicked.connect(self._on_export_clicked)
        row.addWidget(self.flow_status_label, 1)
        row.addWidget(self.export_button)
        return row

    def _build_flow_text(self) -> QPlainTextEdit:
        self.flow_field.setFixedHeight(FLOW_TEXT_HEIGHT)
        self.flow_field.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        return self.flow_field

    def _build_graph(self) -> QScrollArea:
        self.graph_area.setWidgetResizable(True)
        self.graph_area.setWidget(self.graph)
        return self.graph_area

    def _resize_graph(self) -> None:
        height = self.graph.sizeHint().height() + GRAPH_ALLOWANCE
        self.graph_area.setFixedHeight(min(height, GRAPH_HEIGHT))

    def _configure_controls(self) -> None:
        configure_table(self.controls_widget)
        self.controls_widget.setColumnCount(len(COLUMN_LABELS))
        self.controls_widget.setHorizontalHeaderLabels(list(COLUMN_LABELS))
        header = self.controls_widget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(ROLES_COLUMN_INDEX, QHeaderView.ResizeMode.Stretch)
        self.controls_widget.itemSelectionChanged.connect(self._on_selection_changed)

    def _show_verdict(self, outcome: VerificationOutcome) -> None:
        self.verdict_label.setText(outcome.summary)
        refresh_role(
            self.verdict_label,
            Role.ERROR if outcome.decision == DECISION_DENIED else Role.TITLE,
        )
        self.reasons_label.setText("\n".join(outcome.reasons))

    def _fill_controls(self) -> None:
        self.controls_widget.clearContents()
        self.controls_widget.setRowCount(len(self._checks))
        for row, check in enumerate(self._checks):
            control = check.control
            values = (
                LEVEL_LABELS[check.level],
                control.name,
                control.decision_label,
                control.role_label,
            )
            for column, value in enumerate(values):
                self.controls_widget.setItem(row, column, self._item(value, row))
            flags = (control.has_condition, control.has_script, check.satisfied)
            for column, checked in zip(CHECK_COLUMN_INDEXES, flags):
                item = check_item(checked)
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.controls_widget.setItem(row, column, item)
        self.controls_widget.resizeColumnsToContents()
        self._resize_controls()

    def _item(self, value: str, row: int) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        item.setData(Qt.ItemDataRole.UserRole, row)
        return item

    def _resize_controls(self) -> None:
        height = self.controls_widget.horizontalHeader().height() + CONTROLS_MARGIN
        for row in range(self.controls_widget.rowCount()):
            height += self.controls_widget.rowHeight(row)
        self.controls_widget.setFixedHeight(min(height, CONTROLS_HEIGHT))

    def _clear_details(self) -> None:
        self.condition_field.clear()
        self.script_preview.clear()

    def _selected_check(self) -> ControlCheck | None:
        items = self.controls_widget.selectedItems()
        if not items:
            return None
        row = items[0].data(Qt.ItemDataRole.UserRole)
        if not isinstance(row, int) or row >= len(self._checks):
            return None
        return self._checks[row]

    def _on_selection_changed(self) -> None:
        check = self._selected_check()
        if check is None:
            return
        self.condition_field.setText(check.control.condition)
        self.script_preview.setPlainText(check.control.script)

    def _on_export_clicked(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return
        clipboard.setText(self.flow_text)
        show_status(self.flow_status_label, COPIED_MESSAGE)
