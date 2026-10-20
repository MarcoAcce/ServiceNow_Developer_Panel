from collections.abc import Callable, Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.dialogs import CANCEL_LABEL, FramelessDialog
from ui.widgets.query_builder import QueryBuilder
from core.request_model import (
    FIELD_SEPARATOR,
    FIELDS_PARAMETER,
    LIMIT_PARAMETER,
    MAXIMUM_LIMIT,
    ORDER_PARAMETER,
    QUERY_PARAMETER,
    RequestPart,
    table_parameters,
)
from ui.widgets.suggestion_field import SuggestionField
from ui.ui_widgets import hint_label, primary_button, section_label

DEFAULT_LIMIT: int = 1000
SINGLE_CALL_LIMIT: int = 10000
TABLE_LABEL: str = "Table *"
TABLE_PLACEHOLDER: str = "Table name, for example incident"
FIELDS_LABEL: str = "Fields"
FIELDS_PLACEHOLDER: str = "Comma separated field list, empty for the default columns"
ORDER_LABEL: str = "Order by"
ORDER_PLACEHOLDER: str = "Field used to sort the records"
RECORD_COUNT_LABEL: str = "Number of records"
RECORD_COUNT_HINT: str = (
    f"The instance returns at most {SINGLE_CALL_LIMIT} records per call: asking for more than "
    f"{SINGLE_CALL_LIMIT} splits the request into several calls, which can take a little longer."
)
LIMIT_HINT: str = (
    f"Asking for more than {SINGLE_CALL_LIMIT} records splits the request into several calls."
)
QUERY_HINT: str = (
    "Build the condition like on the instance: AND starts a new group, "
    "OR adds a condition inside the current group."
)
QUERY_SECTION: str = "Encoded query"
ADD_TABLE_TITLE: str = "Add table"
ADD_TABLE_HINT: str = (
    "The records of this table are added to the local cache of the response."
)
ADD_TABLE_LABEL: str = "Add table"
DIALOG_WIDTH: int = 720
FORM_SPACING: int = 6

TableNames = Callable[[], Sequence[str]]
FieldNames = Callable[[str], Sequence[str]]


class TableQueryForm(QWidget):

    changed = Signal()

    def __init__(self, tables: TableNames, fields: FieldNames) -> None:
        super().__init__()
        self._fields: FieldNames = fields
        self.table_field: SuggestionField = SuggestionField(lambda: list(tables()))
        self.fields_field: QLineEdit = QLineEdit()
        self.order_field: SuggestionField = SuggestionField(self._field_names)
        self.limit_field: QSpinBox = QSpinBox()
        self.query_builder: QueryBuilder = QueryBuilder()
        self.options: list[QWidget] = []
        self._details: list[QWidget] = []
        self._form: QFormLayout = QFormLayout()
        self._build_ui()
        self._apply_state()

    def table_name(self) -> str:
        return self.table_field.text().strip()

    def is_empty(self) -> bool:
        return not self.table_name()

    def part(self) -> RequestPart | None:
        table = self.table_name()
        if not table:
            return None
        return RequestPart(
            table=table, parameters=self._parameters(), columns=self._columns()
        )

    def focus_table(self) -> None:
        self.table_field.setFocus()

    def set_details_visible(self, visible: bool) -> None:
        for widget in (self.fields_field, self.order_field, self.limit_field):
            self._form.setRowVisible(widget, visible)
        for widget in self._details:
            widget.setVisible(visible)

    def _field_names(self) -> list[str]:
        return list(self._fields(self.table_name()))

    def _columns(self) -> tuple[str, ...]:
        return tuple(
            name.strip()
            for name in self.fields_field.text().split(FIELD_SEPARATOR)
            if name.strip()
        )

    def _parameters(self) -> dict[str, str]:
        return table_parameters(
            self.query_builder.encoded_query(),
            self._columns(),
            self.order_field.text().strip(),
            self.limit_field.value(),
        )

    def _build_ui(self) -> None:
        self.table_field.setPlaceholderText(TABLE_PLACEHOLDER)
        self.fields_field.setPlaceholderText(FIELDS_PLACEHOLDER)
        self.fields_field.setClearButtonEnabled(True)
        self.order_field.setPlaceholderText(ORDER_PLACEHOLDER)
        self.limit_field.setRange(1, MAXIMUM_LIMIT)
        self.limit_field.setValue(DEFAULT_LIMIT)
        self.limit_field.setGroupSeparatorShown(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(FORM_SPACING)
        form = self._form
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(TABLE_LABEL, self.table_field)
        self._add_option(form, FIELDS_LABEL, self.fields_field)
        self._add_option(form, ORDER_LABEL, self.order_field)
        self._add_option(form, RECORD_COUNT_LABEL, self.limit_field)
        layout.addLayout(form)
        for widget in (hint_label(LIMIT_HINT), section_label(QUERY_SECTION),
                       hint_label(QUERY_HINT), self.query_builder):
            self.options.append(widget)
            self._details.append(widget)
            layout.addWidget(widget)
        self.table_field.textChanged.connect(self._on_table_changed)
        self.query_builder.changed.connect(self.changed)

    def _add_option(self, form: QFormLayout, label: str, widget: QWidget) -> None:
        form.addRow(label, widget)
        self.options.append(widget)
        field_label = form.labelForField(widget)
        if field_label is not None:
            self.options.append(field_label)

    def _on_table_changed(self) -> None:
        self._apply_state()
        self.changed.emit()

    def _apply_state(self) -> None:
        enabled = not self.is_empty()
        for widget in self.options:
            widget.setEnabled(enabled)


class TableQueryDialog(FramelessDialog):

    def __init__(
        self,
        parent: QWidget | None,
        tables: TableNames,
        fields: FieldNames,
        taken: Sequence[str] = (),
    ) -> None:
        super().__init__(ADD_TABLE_TITLE, parent)
        self.setMinimumWidth(DIALOG_WIDTH)
        self._taken: tuple[str, ...] = tuple(taken)
        self.form: TableQueryForm = TableQueryForm(tables, fields)
        self.confirm_button: QPushButton = primary_button(ADD_TABLE_LABEL)
        self._build_ui()

    def part(self) -> RequestPart | None:
        return self.form.part()

    def _build_ui(self) -> None:
        self.content_layout.addWidget(hint_label(ADD_TABLE_HINT))
        self.content_layout.addWidget(self.form)
        cancel_button = QPushButton(CANCEL_LABEL)
        cancel_button.clicked.connect(self.reject)
        self.confirm_button.setDefault(True)
        self.confirm_button.clicked.connect(self.accept)
        self.add_button_row(cancel_button, self.confirm_button)
        self.form.changed.connect(self._refresh_state)
        self._refresh_state()

    def _refresh_state(self) -> None:
        table = self.form.table_name()
        self.confirm_button.setEnabled(bool(table) and table not in self._taken)


def encoded_query_of(parameters: dict[str, str]) -> str:
    return parameters.get(QUERY_PARAMETER, "")


def limit_of(parameters: dict[str, str]) -> str:
    return parameters.get(LIMIT_PARAMETER, "")


def fields_of(parameters: dict[str, str]) -> str:
    return parameters.get(FIELDS_PARAMETER, "")


def order_of(parameters: dict[str, str]) -> str:
    return parameters.get(ORDER_PARAMETER, "")
