from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from request_types import ANY_VALUE, RequestType
from response_tab import ResponseTab
from service import RequestCall, RequestError, RequestResult, RequestService, RequestSpec
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

DEFAULT_LIMIT: int = 50
MAXIMUM_LIMIT: int = 10000
IDLE_MESSAGE: str = "Ready to send through {source}."
RUNNING_MESSAGE: str = "Sending request..."
RESULT_MESSAGE: str = "{count} records received in {elapsed} ms."
ERROR_MESSAGE: str = "Request failed: {message}"


class RequestTab(Tab):

    executed = Signal(object)
    closed = Signal()

    def __init__(self, request_type: RequestType, service: RequestService) -> None:
        super().__init__(request_type.label)
        self.request_type: RequestType = request_type
        self._service: RequestService = service
        self._call: RequestCall | None = None
        self._filters: dict[str, QWidget] = {}
        self.table_field: QLineEdit = QLineEdit(request_type.table)
        self.query_field: QLineEdit = QLineEdit()
        self.fields_field: QLineEdit = QLineEdit()
        self.order_field: QLineEdit = QLineEdit()
        self.limit_field: QSpinBox = QSpinBox()
        self.status_label: QLabel = QLabel()
        self.close_button: QPushButton = QPushButton("Close")
        self.execute_button: QPushButton = primary_button("Execute")
        self._build_ui()
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

    def filter_parameters(self) -> dict[str, str]:
        parameters: dict[str, str] = {}
        for name, widget in self._filters.items():
            value = self._filter_value(widget)
            if value:
                parameters[name] = value
        return parameters

    def add_text_filter(self, name: str, label: str, placeholder: str = "") -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setClearButtonEnabled(True)
        self._filters[name] = field
        self._filter_layout.addRow(label, field)
        return field

    def add_choice_filter(self, name: str, label: str, options: Sequence[str]) -> QComboBox:
        field = QComboBox()
        field.addItem(ANY_VALUE)
        field.addItems(list(options))
        self._filters[name] = field
        self._filter_layout.addRow(label, field)
        return field

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(title_label(self.request_type.label))
        root.addWidget(hint_label(self.request_type.description))
        root.addWidget(horizontal_rule())

        root.addWidget(section_label("Target"))
        target = QWidget()
        target_layout = QFormLayout(target)
        target_layout.setContentsMargins(0, 0, 0, 0)
        self.table_field.setPlaceholderText("Table name, for example incident")
        self.table_field.setReadOnly(bool(self.request_type.table))
        target_layout.addRow("Table", self.table_field)
        root.addWidget(target)

        root.addWidget(section_label("Filters"))
        filters = QWidget()
        self._filter_layout: QFormLayout = QFormLayout(filters)
        self._filter_layout.setContentsMargins(0, 0, 0, 0)
        self.build_filters(self._filter_layout)
        root.addWidget(filters)

        root.addWidget(section_label("Query options"))
        options = QWidget()
        options_layout = QFormLayout(options)
        options_layout.setContentsMargins(0, 0, 0, 0)
        self.query_field.setPlaceholderText("Additional encoded query")
        self.fields_field.setPlaceholderText("Comma separated field list, empty for the default columns")
        self.order_field.setPlaceholderText("Field used to sort the records")
        self.limit_field.setRange(1, MAXIMUM_LIMIT)
        self.limit_field.setValue(DEFAULT_LIMIT)
        options_layout.addRow("Encoded query", self.query_field)
        options_layout.addRow("Fields", self.fields_field)
        options_layout.addRow("Order by", self.order_field)
        options_layout.addRow("Limit", self.limit_field)
        root.addWidget(options)

        root.addWidget(vertical_spacer())
        root.addWidget(horizontal_rule())
        root.addLayout(self._build_footer())

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
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

    def execute(self) -> None:
        if self.is_running():
            return
        self.execute_button.setEnabled(False)
        show_status(self.status_label, RUNNING_MESSAGE)
        self._call = self._service.send(self.build_request())
        self._call.succeeded.connect(self._on_succeeded)
        self._call.failed.connect(self._on_failed)

    def build_request(self) -> RequestSpec:
        return RequestSpec(
            request_type=self.request_type,
            table=self.target_table(),
            parameters=self._build_parameters(),
            columns=self.columns(),
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
        conditions = [f"{name}={value}" for name, value in self.filter_parameters().items()]
        extra = self.query_field.text().strip()
        if extra:
            conditions.append(extra)
        return "^".join(conditions)

    def _filter_value(self, widget: QWidget) -> str:
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        if isinstance(widget, QComboBox):
            value = widget.currentText()
            return "" if value == ANY_VALUE else value
        if isinstance(widget, QSpinBox):
            return str(widget.value())
        return ""

    def _show_idle_status(self) -> None:
        show_status(self.status_label, IDLE_MESSAGE.format(source=self._service.describe()))

    def _on_succeeded(self, result: RequestResult) -> None:
        self._release_call()
        show_status(
            self.status_label,
            RESULT_MESSAGE.format(count=len(result.records), elapsed=result.elapsed_ms),
        )
        self.executed.emit(self.create_response_tab(result))

    def _on_failed(self, error: RequestError) -> None:
        self._release_call()
        show_status(self.status_label, ERROR_MESSAGE.format(message=error.message), failed=True)

    def _release_call(self) -> None:
        self.execute_button.setEnabled(True)
        if self._call is not None:
            self._call.deleteLater()
            self._call = None
