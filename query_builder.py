from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from query_conditions import (
    AND_SEPARATOR,
    CLOSE_PAREN,
    OPEN_PAREN,
    OPERATOR_CONTAINS,
    OPERATOR_IS,
    OPERATOR_IS_NOT,
    OPERATOR_IS_ONE_OF,
    OPERATOR_ON_OR_AFTER,
    OPERATOR_STARTS_WITH,
    OPERATORS,
    OR_SEPARATOR,
    QueryOperator,
    build_condition,
    encode_groups,
)
from theme import Role, set_role
from ui_widgets import as_row

__all__ = [
    "AND_SEPARATOR",
    "CLOSE_PAREN",
    "OPEN_PAREN",
    "OPERATOR_CONTAINS",
    "OPERATOR_IS",
    "OPERATOR_IS_NOT",
    "OPERATOR_IS_ONE_OF",
    "OPERATOR_ON_OR_AFTER",
    "OPERATOR_STARTS_WITH",
    "OPERATORS",
    "OR_SEPARATOR",
    "ConditionRow",
    "QueryBuilder",
    "QueryGroup",
    "QueryOperator",
    "build_condition",
    "encode_groups",
    "paren_label",
]

AND_LABEL: str = "AND"
OR_LABEL: str = "OR"

ADD_AND_TEXT: str = "+ AND"
ADD_OR_TEXT: str = "+ OR"
REMOVE_TEXT: str = "x"
ADD_AND_TOOLTIP: str = "Add a condition joined with AND, in a new group"
ADD_OR_TOOLTIP: str = "Add a condition joined with OR, inside this group"
REMOVE_TOOLTIP: str = "Remove this condition"
FIELD_PLACEHOLDER: str = "Field name, for example priority"
VALUE_PLACEHOLDER: str = "Value"
NO_VALUE_PLACEHOLDER: str = "No value needed"
PREVIEW_LABEL: str = "Generated query"
PREVIEW_PLACEHOLDER: str = "No conditions yet"

CONNECTOR_WIDTH: int = 38
OPERATOR_WIDTH: int = 150
CONNECTOR_BUTTON_WIDTH: int = 78
REMOVE_BUTTON_WIDTH: int = 32
PAREN_POINT_SIZE_DELTA: int = 8
PAREN_WIDTH: int = 14
FIELD_STRETCH: int = 3
VALUE_STRETCH: int = 3
GROUP_SPACING: int = 4
GROUP_MARGIN: int = 6


def paren_label() -> QLabel:
    label = QLabel()
    font = label.font()
    font.setPointSize(font.pointSize() + PAREN_POINT_SIZE_DELTA)
    label.setFont(font)
    label.setFixedWidth(PAREN_WIDTH)
    set_role(label, Role.HINT)
    return label


class ConditionRow(QWidget):

    changed = Signal()
    andRequested = Signal(object)
    orRequested = Signal(object)
    removeRequested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.connector_label: QLabel = QLabel()
        self.field_input: QLineEdit = QLineEdit()
        self.operator_input: QComboBox = QComboBox()
        self.value_input: QLineEdit = QLineEdit()
        self.and_button: QPushButton = QPushButton(ADD_AND_TEXT)
        self.or_button: QPushButton = QPushButton(ADD_OR_TEXT)
        self.remove_button: QPushButton = QPushButton(REMOVE_TEXT)
        self._build_ui()

    def operator(self) -> QueryOperator:
        return OPERATORS[self.operator_input.currentIndex()]

    def condition(self) -> str:
        return build_condition(
            self.field_input.text().strip(),
            self.operator(),
            self.value_input.text().strip(),
        )

    def set_connector(self, text: str) -> None:
        self.connector_label.setText(text)

    def set_removable(self, removable: bool) -> None:
        self.remove_button.setEnabled(removable)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.connector_label.setFixedWidth(CONNECTOR_WIDTH)
        set_role(self.connector_label, Role.HINT)
        self.field_input.setPlaceholderText(FIELD_PLACEHOLDER)
        self.field_input.setClearButtonEnabled(True)
        for operator in OPERATORS:
            self.operator_input.addItem(operator.label)
        self.operator_input.setMinimumWidth(OPERATOR_WIDTH)
        self.value_input.setPlaceholderText(VALUE_PLACEHOLDER)
        self.value_input.setClearButtonEnabled(True)
        self.and_button.setToolTip(ADD_AND_TOOLTIP)
        self.or_button.setToolTip(ADD_OR_TOOLTIP)
        self.remove_button.setToolTip(REMOVE_TOOLTIP)
        self.and_button.setFixedWidth(CONNECTOR_BUTTON_WIDTH)
        self.or_button.setFixedWidth(CONNECTOR_BUTTON_WIDTH)
        self.remove_button.setFixedWidth(REMOVE_BUTTON_WIDTH)
        layout.addWidget(self.connector_label)
        layout.addWidget(self.field_input, FIELD_STRETCH)
        layout.addWidget(self.operator_input)
        layout.addWidget(self.value_input, VALUE_STRETCH)
        layout.addWidget(self.and_button)
        layout.addWidget(self.or_button)
        layout.addWidget(self.remove_button)
        self.field_input.textChanged.connect(self.changed)
        self.value_input.textChanged.connect(self.changed)
        self.operator_input.currentIndexChanged.connect(self._on_operator_changed)
        self.and_button.clicked.connect(lambda: self.andRequested.emit(self))
        self.or_button.clicked.connect(lambda: self.orRequested.emit(self))
        self.remove_button.clicked.connect(lambda: self.removeRequested.emit(self))

    def _on_operator_changed(self) -> None:
        takes_value = self.operator().takes_value
        self.value_input.setEnabled(takes_value)
        self.value_input.setPlaceholderText(VALUE_PLACEHOLDER if takes_value else NO_VALUE_PLACEHOLDER)
        if not takes_value:
            self.value_input.clear()
        self.changed.emit()


class QueryGroup(QFrame):

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[ConditionRow] = []
        self.open_label: QLabel = paren_label()
        self.close_label: QLabel = paren_label()
        self._rows_layout: QVBoxLayout = QVBoxLayout()
        self._build_ui()

    def rows(self) -> tuple[ConditionRow, ...]:
        return tuple(self._rows)

    def conditions(self) -> list[str]:
        return [row.condition() for row in self._rows]

    def add_row(self, row: ConditionRow, after: ConditionRow | None = None) -> None:
        index = len(self._rows) if after is None else self._rows.index(after) + 1
        self._rows.insert(index, row)
        self._rows_layout.insertWidget(index, row)

    def remove_row(self, row: ConditionRow) -> None:
        self._rows.remove(row)
        self._rows_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()

    def refresh(self, first: bool) -> None:
        grouped = len(self._rows) > 1
        self.open_label.setText(OPEN_PAREN if grouped else "")
        self.close_label.setText(CLOSE_PAREN if grouped else "")
        for index, row in enumerate(self._rows):
            row.set_connector(OR_LABEL if index else ("" if first else AND_LABEL))

    def _build_ui(self) -> None:
        as_row(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(GROUP_MARGIN, GROUP_MARGIN, GROUP_MARGIN, GROUP_MARGIN)
        layout.setSpacing(GROUP_SPACING)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(GROUP_SPACING)
        layout.addWidget(self.open_label)
        layout.addLayout(self._rows_layout, 1)
        layout.addWidget(self.close_label)


class QueryBuilder(QWidget):

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._groups: list[QueryGroup] = []
        self.preview_field: QLineEdit = QLineEdit()
        self._groups_layout: QVBoxLayout = QVBoxLayout()
        self._build_ui()
        self._add_group()
        self._refresh()

    def encoded_query(self) -> str:
        return encode_groups(group.conditions() for group in self._groups)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._groups_layout.setContentsMargins(0, 0, 0, 0)
        self._groups_layout.setSpacing(GROUP_SPACING)
        layout.addLayout(self._groups_layout)
        self.preview_field.setReadOnly(True)
        self.preview_field.setPlaceholderText(PREVIEW_PLACEHOLDER)
        set_role(self.preview_field, Role.MONOSPACE)
        preview = QWidget()
        preview_layout = QFormLayout(preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addRow(PREVIEW_LABEL, self.preview_field)
        layout.addWidget(preview)

    def _add_group(self, after: QueryGroup | None = None) -> QueryGroup:
        group = QueryGroup()
        index = len(self._groups) if after is None else self._groups.index(after) + 1
        self._groups.insert(index, group)
        self._groups_layout.insertWidget(index, group)
        group.add_row(self._create_row())
        return group

    def _create_row(self) -> ConditionRow:
        row = ConditionRow()
        row.changed.connect(self._on_row_changed)
        row.andRequested.connect(self._on_and_requested)
        row.orRequested.connect(self._on_or_requested)
        row.removeRequested.connect(self._on_remove_requested)
        return row

    def _group_of(self, row: ConditionRow) -> QueryGroup | None:
        for group in self._groups:
            if row in group.rows():
                return group
        return None

    def _on_and_requested(self, row: ConditionRow) -> None:
        self._add_group(after=self._group_of(row))
        self._refresh()

    def _on_or_requested(self, row: ConditionRow) -> None:
        group = self._group_of(row)
        if group is None:
            return
        group.add_row(self._create_row(), after=row)
        self._refresh()

    def _on_remove_requested(self, row: ConditionRow) -> None:
        group = self._group_of(row)
        if group is None:
            return
        group.remove_row(row)
        if not group.rows():
            self._groups.remove(group)
            self._groups_layout.removeWidget(group)
            group.setParent(None)
            group.deleteLater()
        if not self._groups:
            self._add_group()
        self._refresh()

    def _on_row_changed(self) -> None:
        self.preview_field.setText(self.encoded_query())
        self.changed.emit()

    def _refresh(self) -> None:
        for index, group in enumerate(self._groups):
            group.refresh(index == 0)
        removable = len(self._groups) > 1 or len(self._groups[0].rows()) > 1
        for group in self._groups:
            for row in group.rows():
                row.set_removable(removable)
        self._on_row_changed()
