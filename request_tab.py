from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from config_repository import ConfigRepository
from filter_fields import BooleanFilterField, DateFilterField, RadioChoiceField
from instance_selector import InstanceSelector
from query_builder import (
    AND_SEPARATOR,
    OPERATOR_IS,
    OPERATOR_ON_OR_AFTER,
    QueryBuilder,
    QueryOperator,
    build_condition,
)
from request_hints import RequestHintRepository
from request_types import ANY_VALUE, RequestType
from response_tab import ResponseTab
from service import RequestCall, RequestError, RequestResult, RequestService, RequestSpec
from suggestion_field import SuggestionField
from tab import Tab
from ui_widgets import (
    hint_label,
    horizontal_rule,
    primary_button,
    section_label,
    show_status,
    title_label,
    vertical_spacer,
)

DEFAULT_LIMIT: int = 1000
MAXIMUM_LIMIT: int = 100000
SINGLE_CALL_LIMIT: int = 10000
RECORD_COUNT_LABEL: str = "Number of records"
RECORD_COUNT_HINT: str = (
    f"The instance returns at most {SINGLE_CALL_LIMIT} records per call: asking for more than "
    f"{SINGLE_CALL_LIMIT} splits the request into several calls, which can take a little longer."
)
IDLE_MESSAGE: str = "Ready to send through {source}."
RUNNING_MESSAGE: str = "Sending request..."
RESULT_MESSAGE: str = "{count} records received in {elapsed} ms."
ERROR_MESSAGE: str = "Request failed: {message}"
ERROR_TITLE: str = "Request failed"
TABLE_REQUIRED_MESSAGE: str = "Target table is required to send the request."
REQUIRED_MESSAGE: str = "{label} is required to send the request."
REQUIRED_SUFFIX: str = " *"
TABLE_LABEL: str = "Table *"
TABLE_PLACEHOLDER: str = "Table name, for example incident"
TARGET_HINT: str = "The target table is required: the request cannot be sent without it."
TARGET_LABEL: str = "Target table"
TARGET_SPACING: int = 8
QUERY_HINT: str = (
    "Build the condition like on the instance: AND starts a new group, "
    "OR adds a condition inside the current group."
)


@dataclass(frozen=True)
class FilterEntry:
    field: str
    operator: QueryOperator
    widget: QWidget


@dataclass(frozen=True)
class RequiredEntry:
    widget: QWidget
    message: str


def required_label(label: str) -> str:
    return f"{label}{REQUIRED_SUFFIX}"


def required_message(label: str) -> str:
    return REQUIRED_MESSAGE.format(label=label)


class RequestTab(Tab):

    executed = Signal(object)
    closed = Signal()
    runningChanged = Signal(bool)

    def __init__(
        self,
        request_type: RequestType,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        super().__init__(request_type.label)
        self.request_type: RequestType = request_type
        self._service: RequestService = service
        self._hints: RequestHintRepository = hints
        self.instance_selector: InstanceSelector = InstanceSelector(repository, compact=True)
        self._call: RequestCall | None = None
        self._filters: list[FilterEntry] = []
        self._required: list[RequiredEntry] = []
        self._table_hint: QLineEdit | None = None
        self._field_hint: QLineEdit | None = None
        self.table_field: QLineEdit = (
            QLineEdit(request_type.table)
            if request_type.table
            else self.table_suggestion_field()
        )
        self.query_builder: QueryBuilder = QueryBuilder()
        self.fields_field: QLineEdit = QLineEdit()
        self.order_field: QLineEdit = QLineEdit()
        self.limit_field: QSpinBox = QSpinBox()
        self.status_label: QLabel = QLabel()
        self.close_button: QPushButton = QPushButton("Close")
        self.execute_button: QPushButton = primary_button("Execute")
        self._build_ui()
        self._update_execute_state()
        self._show_idle_status()

    @property
    def service(self) -> RequestService:
        return self._service

    def set_service(self, service: RequestService) -> None:
        self._service = service
        if not self.is_running():
            self._show_idle_status()

    def is_running(self) -> bool:
        return self._call is not None and self._call.is_running()

    def cancel(self) -> None:
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def columns(self) -> tuple[str, ...]:
        raise NotImplementedError

    def build_filters(self, layout: QFormLayout) -> None:
        return None

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return ResponseTab(result)

    def target_table(self) -> str:
        return self.table_field.text().strip()

    def table_suggestion_field(self) -> SuggestionField:
        widget = SuggestionField(self.table_suggestions)
        self._table_hint = widget
        return widget

    def field_suggestion_field(self) -> SuggestionField:
        widget = SuggestionField(self.field_suggestions)
        self._field_hint = widget
        return widget

    def table_suggestions(self) -> list[str]:
        return self._hints.table_names(self.request_type.key)

    def field_suggestions(self) -> list[str]:
        return self._hints.field_names(self.request_type.key, self.hinted_table())

    def hinted_table(self) -> str:
        return self._table_hint.text().strip() if self._table_hint is not None else ""

    def hinted_field(self) -> str:
        widget = self._field_hint
        if widget is None or widget.isHidden():
            return ""
        return widget.text().strip()

    def missing_requirement(self) -> str:
        if not self.target_table():
            return TABLE_REQUIRED_MESSAGE
        for entry in self._required:
            if not self._filter_value(entry.widget):
                return entry.message
        return ""

    def require(self, widget: QWidget, message: str) -> None:
        self._required.append(RequiredEntry(widget=widget, message=message))
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(self.refresh_state)

    def refresh_state(self) -> None:
        self._update_execute_state()
        if not self.is_running():
            self._show_idle_status()

    def filter_conditions(self) -> list[str]:
        conditions: list[str] = []
        for entry in self._filters:
            condition = build_condition(entry.field, entry.operator, self._filter_value(entry.widget))
            if condition:
                conditions.append(condition)
        return conditions

    def add_text_filter(
        self,
        field: str,
        label: str,
        placeholder: str = "",
        operator: QueryOperator = OPERATOR_IS,
    ) -> QLineEdit:
        widget = QLineEdit()
        widget.setPlaceholderText(placeholder)
        widget.setClearButtonEnabled(True)
        self._register_filter(field, label, widget, operator)
        return widget

    def add_required_text_filter(
        self,
        field: str,
        label: str,
        placeholder: str = "",
        operator: QueryOperator = OPERATOR_IS,
        message: str = "",
    ) -> QLineEdit:
        widget = QLineEdit()
        widget.setPlaceholderText(placeholder)
        widget.setClearButtonEnabled(True)
        self._register_filter(field, required_label(label), widget, operator)
        self.require(widget, message or required_message(label))
        return widget

    def add_table_filter(
        self,
        field: str,
        label: str,
        placeholder: str = TABLE_PLACEHOLDER,
        operator: QueryOperator = OPERATOR_IS,
        message: str = "",
    ) -> SuggestionField:
        widget = self.table_suggestion_field()
        widget.setPlaceholderText(placeholder)
        self._register_filter(field, required_label(label), widget, operator)
        self.require(widget, message or required_message(label))
        return widget

    def add_field_filter(
        self,
        field: str,
        label: str,
        placeholder: str = "",
        operator: QueryOperator = OPERATOR_IS,
    ) -> SuggestionField:
        widget = self.field_suggestion_field()
        widget.setPlaceholderText(placeholder)
        self._register_filter(field, label, widget, operator)
        return widget

    def add_choice_filter(
        self,
        field: str,
        label: str,
        options: Sequence[str],
        operator: QueryOperator = OPERATOR_IS,
    ) -> QComboBox:
        widget = QComboBox()
        widget.addItem(ANY_VALUE)
        widget.addItems(list(options))
        self._register_filter(field, label, widget, operator)
        return widget

    def add_boolean_filter(
        self,
        field: str,
        label: str,
        checked: bool = True,
        operator: QueryOperator = OPERATOR_IS,
    ) -> BooleanFilterField:
        widget = BooleanFilterField(checked)
        self._register_filter(field, label, widget, operator)
        return widget

    def add_date_filter(
        self,
        field: str,
        label: str,
        operator: QueryOperator = OPERATOR_ON_OR_AFTER,
    ) -> DateFilterField:
        widget = DateFilterField()
        self._register_filter(field, label, widget, operator)
        return widget

    def add_filter_row(self, label: str, widget: QWidget) -> None:
        self._filter_layout.addRow(label, widget)

    def set_filter_row_visible(self, widget: QWidget, visible: bool) -> None:
        self._filter_layout.setRowVisible(widget, visible)

    def _register_filter(
        self,
        field: str,
        label: str,
        widget: QWidget,
        operator: QueryOperator,
    ) -> None:
        self._filters.append(FilterEntry(field=field, operator=operator, widget=widget))
        self.add_filter_row(label, widget)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(title_label(self.request_type.label))
        root.addWidget(hint_label(self.request_type.description))
        root.addWidget(horizontal_rule())
        root.addWidget(self._build_content(), 1)
        root.addWidget(horizontal_rule())
        root.addWidget(self.instance_selector)
        root.addWidget(horizontal_rule())
        root.addLayout(self._build_footer())

    def _build_content(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._build_target())

        layout.addWidget(section_label("Filters"))
        layout.addWidget(self._build_filters())

        layout.addWidget(section_label("Encoded query"))
        layout.addWidget(hint_label(QUERY_HINT))
        layout.addWidget(self.query_builder)

        layout.addWidget(section_label("Query options"))
        layout.addWidget(self._build_options())

        layout.addWidget(vertical_spacer())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _build_target(self) -> QWidget:
        if self.request_type.table:
            return self._build_fixed_target()
        target = QWidget()
        layout = QVBoxLayout(target)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(section_label("Target"))
        form = QWidget()
        form_layout = QFormLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        self.table_field.setPlaceholderText(TABLE_PLACEHOLDER)
        self.table_field.setClearButtonEnabled(True)
        self.table_field.textChanged.connect(self.refresh_state)
        form_layout.addRow(TABLE_LABEL, self.table_field)
        layout.addWidget(form)
        layout.addWidget(hint_label(TARGET_HINT))
        return target

    def _build_fixed_target(self) -> QWidget:
        target = QWidget()
        layout = QHBoxLayout(target)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TARGET_SPACING)
        layout.addWidget(section_label(TARGET_LABEL))
        layout.addWidget(hint_label(self.request_type.table))
        layout.addStretch(1)
        return target

    def _build_filters(self) -> QWidget:
        filters = QWidget()
        self._filter_layout: QFormLayout = QFormLayout(filters)
        self._filter_layout.setContentsMargins(0, 0, 0, 0)
        self.build_filters(self._filter_layout)
        return filters

    def _build_options(self) -> QWidget:
        options = QWidget()
        layout = QFormLayout(options)
        layout.setContentsMargins(0, 0, 0, 0)
        self.fields_field.setPlaceholderText("Comma separated field list, empty for the default columns")
        self.order_field.setPlaceholderText("Field used to sort the records")
        self.limit_field.setRange(1, MAXIMUM_LIMIT)
        self.limit_field.setValue(DEFAULT_LIMIT)
        self.limit_field.setGroupSeparatorShown(True)
        layout.addRow("Fields", self.fields_field)
        layout.addRow("Order by", self.order_field)
        layout.addRow(RECORD_COUNT_LABEL, self.limit_field)
        layout.addRow(hint_label(RECORD_COUNT_HINT))
        return options

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.execute_button.setDefault(True)
        self.execute_button.clicked.connect(self.execute)
        self.close_button.clicked.connect(self._on_close_clicked)
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.close_button)
        footer.addWidget(self.execute_button)
        return footer

    def _on_close_clicked(self) -> None:
        self.cancel()
        self.closed.emit()

    def _update_execute_state(self) -> None:
        missing = self.missing_requirement()
        self.execute_button.setEnabled(not missing and not self.is_running())
        self.execute_button.setToolTip(missing)

    def execute(self) -> None:
        if self.is_running() or self.missing_requirement():
            return
        self.execute_button.setEnabled(False)
        show_status(self.status_label, RUNNING_MESSAGE)
        self._call = self._service.send(self.build_request())
        self._call.succeeded.connect(self._on_succeeded)
        self._call.failed.connect(self._on_failed)
        self.runningChanged.emit(True)

    def _record_hint(self) -> None:
        table = self.hinted_table()
        if table:
            self._hints.record(self.request_type.key, table, self.hinted_field() or None)

    def reload_instances(self) -> None:
        self.instance_selector.reload()

    def set_instance_id(self, instance_id: int) -> None:
        self.instance_selector.set_instance_id(instance_id)

    def build_request(self) -> RequestSpec:
        return RequestSpec(
            request_type=self.request_type,
            table=self.target_table(),
            parameters=self._build_parameters(),
            columns=self.columns(),
            target=self.instance_selector.current_target(),
        )

    def _build_parameters(self) -> dict[str, str]:
        parameters: dict[str, str] = {}
        query = self._build_encoded_query()
        if query:
            parameters["sysparm_query"] = query
        fields = self.fields_field.text().strip()
        if fields:
            parameters["sysparm_fields"] = fields
        order = self.order_field.text().strip()
        if order:
            parameters["sysparm_order_by"] = order
        parameters["sysparm_limit"] = str(self.limit_field.value())
        return parameters

    def _build_encoded_query(self) -> str:
        conditions = self.filter_conditions()
        query = self.query_builder.encoded_query()
        if query:
            conditions.append(query)
        return AND_SEPARATOR.join(conditions)

    def _filter_value(self, widget: QWidget) -> str:
        if isinstance(widget, (BooleanFilterField, DateFilterField, RadioChoiceField)):
            return widget.value()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        if isinstance(widget, QComboBox):
            value = widget.currentText()
            return "" if value == ANY_VALUE else value
        if isinstance(widget, QSpinBox):
            return str(widget.value())
        return ""

    def _show_idle_status(self) -> None:
        missing = self.missing_requirement()
        if missing:
            show_status(self.status_label, missing)
            return
        show_status(self.status_label, IDLE_MESSAGE.format(source=self._service.describe()))

    def _on_succeeded(self, result: RequestResult) -> None:
        self._release_call()
        self._record_hint()
        show_status(
            self.status_label,
            RESULT_MESSAGE.format(count=len(result.records), elapsed=result.elapsed_ms),
        )
        self.executed.emit(self.create_response_tab(result))

    def _on_failed(self, error: RequestError) -> None:
        self._release_call()
        show_status(self.status_label, ERROR_MESSAGE.format(message=error.message), failed=True)
        QMessageBox.warning(self, ERROR_TITLE, error.message)

    def _release_call(self) -> None:
        if self._call is not None:
            self._call.deleteLater()
            self._call = None
        self._update_execute_state()
        self.runningChanged.emit(False)
