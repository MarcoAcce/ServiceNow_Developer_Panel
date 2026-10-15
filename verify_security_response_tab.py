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
    ProfileOutcome,
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
PROFILES_SECTION: str = "Users checked"
PROFILES_HINT: str = "Click a user to read the controls that decide the access."
PROFILES_HEIGHT: int = 130
PROFILE_COLUMN_LABELS: tuple[str, ...] = ("Roles", "Decision")
CONTROLS_SECTION: str = "Access controls evaluated"
CONTROLS_HINT: str = "Click a control to read its condition and its script."
CONTROLS_HEIGHT: int = 170
TABLE_MARGIN: int = 4
CONDITION_LABEL: str = "Condition"
CONDITION_PLACEHOLDER: str = "Select a control to read its condition."
SCRIPT_SECTION: str = "Control script"
SCRIPT_PLACEHOLDER: str = "Select a control to read its script."
SCRIPT_HEIGHT: int = 130
FLOW_SECTION: str = "Conditions and scripts to satisfy"
FLOW_HINT: str = (
    "Every stage has to be satisfied, from left to right, and each control is named "
    "with its sys_id. The text form of the same flow can be copied with the export "
    "button."
)
FLOW_TEXT_HEIGHT: int = 58
FLOW_PLACEHOLDER: str = "No condition and no script has to be satisfied."
GRAPH_HEIGHT: int = 260
GRAPH_ALLOWANCE: int = 20
EXPORT_LABEL: str = "Export flow"
EXPORT_TOOLTIP: str = "Copy the text form of the flow to the clipboard"
COPIED_MESSAGE: str = "The flow was copied to the clipboard."
CHECKED_ROW: str = "Checked"
USERS_ROW: str = "Users"
CONTROLS_ROW: str = "Access controls"
COLUMN_LABELS: tuple[str, ...] = (
    "Level",
    "Control",
    "Decision",
    "Roles",
    "Admin overrides",
    "Condition",
    "Script",
    "Roles match",
)
ROLES_COLUMN_INDEX: int = 3
CHECK_COLUMN_INDEXES: tuple[int, ...] = (4, 5, 6, 7)


class VerifySecurityResponseTab(ResponseTab):

    def __init__(self, result: RequestResult, verification: Verification) -> None:
        self._verification: Verification = verification
        self._outcome: VerificationOutcome | None = None
        self._profiles: tuple[ProfileOutcome, ...] = ()
        self._profile: ProfileOutcome | None = None
        self._checks: tuple[ControlCheck, ...] = ()
        self.verdict_label: QLabel = title_label("", VERDICT_POINT_SIZE_DELTA)
        self.reasons_label: QLabel = hint_label("")
        self.checked_label: QLabel = QLabel()
        self.users_label: QLabel = QLabel()
        self.controls_count_label: QLabel = QLabel()
        self.profiles_box: QWidget = QWidget()
        self.profiles_widget: QTableWidget = QTableWidget()
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
    def profile(self) -> ProfileOutcome | None:
        return self._profile

    @property
    def flow_text(self) -> str:
        return self._profile.text if self._profile is not None else ""

    def build_menu_table(self, result: RequestResult) -> str:
        return shorten_text(self._verification.target, TABLE_NAME_LIMIT)

    def build_summary_rows(self, layout: QFormLayout) -> None:
        super().build_summary_rows(layout)
        layout.addRow(CHECKED_ROW, self.checked_label)
        layout.addRow(USERS_ROW, self.users_label)
        layout.addRow(CONTROLS_ROW, self.controls_count_label)

    def refresh_summary(self) -> None:
        super().refresh_summary()
        verification = self._verification
        self.checked_label.setText(
            DETAIL_SEPARATOR.join((verification.target, verification.operation))
        )
        self.users_label.setText(verification.label)

    def build_body(self, layout: QVBoxLayout) -> None:
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(self._build_profiles())
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
        self._profiles = outcome.profiles
        self._fill_profiles()
        self._select_profile(0)

    def _build_profiles(self) -> QWidget:
        layout = QVBoxLayout(self.profiles_box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(section_label(PROFILES_SECTION))
        layout.addWidget(hint_label(PROFILES_HINT))
        layout.addWidget(self.profiles_widget)
        configure_table(self.profiles_widget)
        self.profiles_widget.setColumnCount(len(PROFILE_COLUMN_LABELS))
        self.profiles_widget.setHorizontalHeaderLabels(list(PROFILE_COLUMN_LABELS))
        header = self.profiles_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.profiles_widget.itemSelectionChanged.connect(self._on_profile_selected)
        return self.profiles_box

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
        self.controls_widget.itemSelectionChanged.connect(self._on_control_selected)

    def _fill_profiles(self) -> None:
        profiles = self._profiles
        self.profiles_box.setVisible(len(profiles) > 1)
        self.profiles_widget.blockSignals(True)
        self.profiles_widget.clearContents()
        self.profiles_widget.setRowCount(len(profiles))
        for row, profile in enumerate(profiles):
            self.profiles_widget.setItem(row, 0, row_item(profile.label, row))
            self.profiles_widget.setItem(row, 1, row_item(profile.decision_label, row))
        self.profiles_widget.selectRow(0)
        self.profiles_widget.blockSignals(False)
        resize_table(self.profiles_widget, PROFILES_HEIGHT)

    def _select_profile(self, index: int) -> None:
        if not 0 <= index < len(self._profiles):
            return
        profile = self._profiles[index]
        self._profile = profile
        self._checks = profile.checks
        self.controls_count_label.setText(str(len(self._checks)))
        self._show_verdict(profile)
        self._fill_controls()
        self._clear_details()
        self.flow_field.setPlainText(profile.text)
        self.export_button.setEnabled(bool(profile.text))
        self.graph.set_stages(profile.stages)
        self._resize_graph()
        show_status(self.flow_status_label, "")

    def _show_verdict(self, profile: ProfileOutcome) -> None:
        self.verdict_label.setText(profile.summary)
        refresh_role(
            self.verdict_label,
            Role.ERROR if profile.decision == DECISION_DENIED else Role.TITLE,
        )
        self.reasons_label.setText("\n".join(profile.reasons))

    def _fill_controls(self) -> None:
        self.controls_widget.blockSignals(True)
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
                self.controls_widget.setItem(row, column, row_item(value, row))
            name_item = self.controls_widget.item(row, 1)
            if name_item is not None:
                name_item.setToolTip(control.sys_id)
            flags = (
                control.overrides_admin,
                control.has_condition,
                control.has_script,
                check.satisfied,
            )
            for column, checked in zip(CHECK_COLUMN_INDEXES, flags):
                item = check_item(checked)
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.controls_widget.setItem(row, column, item)
        self.controls_widget.resizeColumnsToContents()
        self.controls_widget.blockSignals(False)
        resize_table(self.controls_widget, CONTROLS_HEIGHT)

    def _clear_details(self) -> None:
        self.condition_field.clear()
        self.script_preview.clear()

    def _selected_check(self) -> ControlCheck | None:
        row = selected_row(self.controls_widget)
        if row is None or row >= len(self._checks):
            return None
        return self._checks[row]

    def _on_profile_selected(self) -> None:
        row = selected_row(self.profiles_widget)
        if row is not None:
            self._select_profile(row)

    def _on_control_selected(self) -> None:
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


def row_item(value: str, row: int) -> QTableWidgetItem:
    item = QTableWidgetItem(value)
    item.setData(Qt.ItemDataRole.UserRole, row)
    return item


def selected_row(widget: QTableWidget) -> int | None:
    items = widget.selectedItems()
    if not items:
        return None
    row = items[0].data(Qt.ItemDataRole.UserRole)
    return row if isinstance(row, int) else None


def resize_table(widget: QTableWidget, limit: int) -> None:
    height = widget.horizontalHeader().height() + TABLE_MARGIN
    for row in range(widget.rowCount()):
        height += widget.rowHeight(row)
    widget.setFixedHeight(min(height, limit))
