from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import Shiboken

from core.request_model import RequestResult
from core.table_description import (
    ATTRIBUTES_FIELD,
    DEFINED_ON_FIELD,
    DISPLAY_FIELD,
    MANDATORY_COLUMN,
    MAX_LENGTH_FIELD,
    READ_ONLY_COLUMN,
    REFERENCE_CONDITION_FIELD,
    REFERENCE_QUAL_FIELD,
    REFERENCE_QUAL_TYPE_FIELD,
    DescribedField,
    active_only,
    described_fields,
    relations,
)
from core.table_dictionary import ACTIVE_FIELD, ELEMENT_FIELD, REFERENCE_FIELD, TYPE_FIELD
from response_tabs.response_tab import TABLE_NAME_LIMIT, RecordsResponseTab
from ui.dialogs import CLOSE_LABEL, FramelessDialog
from ui.ui_widgets import (
    configure_table,
    hint_label,
    primary_button,
    section_label,
    shorten_text,
)
from ui.widgets.relations_graph import RelationsGraph

FIELD_COLUMNS: tuple[str, ...] = (
    ELEMENT_FIELD,
    "column_label",
    TYPE_FIELD,
    REFERENCE_FIELD,
    MANDATORY_COLUMN,
    READ_ONLY_COLUMN,
    DISPLAY_FIELD,
    DEFINED_ON_FIELD,
)
CHECKBOX_COLUMNS: tuple[str, ...] = (
    MANDATORY_COLUMN,
    READ_ONLY_COLUMN,
    DISPLAY_FIELD,
    ACTIVE_FIELD,
)
COLUMN_LABELS: dict[str, str] = {
    ELEMENT_FIELD: "Field",
    "column_label": "Label",
    TYPE_FIELD: "Type",
    REFERENCE_FIELD: "Reference to",
    MANDATORY_COLUMN: "Mandatory",
    READ_ONLY_COLUMN: "Read only",
    DISPLAY_FIELD: "Display",
    ACTIVE_FIELD: "Active",
    DEFINED_ON_FIELD: "Defined on",
}
RELATIONS_LABEL: str = "Show relations"
RELATIONS_TITLE: str = "Relations of {table}"
RELATIONS_HINT: str = (
    "Tables on the left reference this table, tables on the right are referenced by it. "
    "The number at the end of each line is the cardinality of the other table. "
    "Hover a table to read the fields behind the relation."
)
RELATIONS_MAXIMUM_WIDTH: int = 1180
RELATIONS_MAXIMUM_HEIGHT: int = 640
RELATIONS_EXTRA: int = 24
DETAILS_SECTION: str = "Field details"
DETAILS_HEIGHT: int = 230
DETAILS_SPACING: int = 12
EMPTY_DETAILS: str = "Select a field to read its details."
CHOICES_SECTION: str = "Choice list"
NO_CHOICES: str = "This field has no choice list."
CHOICE_COLUMNS: tuple[str, ...] = ("Value", "Label", "Dependent value")
OVERRIDE_TEXT: str = "{attribute} = {value} on {table}"
DETAIL_ROWS: tuple[tuple[str, str], ...] = (
    ("label", "Label"),
    ("type", "Type"),
    ("reference", "Reference to"),
    ("defined_on", "Defined on"),
    ("max_length", "Max length"),
    ("default_value", "Default value"),
    ("dependent", "Dependent on"),
    ("qualifier_type", "Qualifier type"),
    ("qualifier", "Reference qualifier"),
    ("attributes", "Attributes"),
    ("overrides", "Overrides"),
)


def detail_values(field: DescribedField) -> dict[str, str]:
    description = field.description
    record = field.record
    overrides = description.get("overrides", [])
    qualifier = record.get(REFERENCE_QUAL_FIELD, "") or record.get(
        REFERENCE_CONDITION_FIELD, ""
    )
    for override in overrides:
        if override["attribute"] == REFERENCE_QUAL_FIELD:
            qualifier = override["value"]
    return {
        "label": description["label"],
        "type": description["type"],
        "reference": description["reference"],
        "defined_on": description["defined_on"],
        "max_length": record.get(MAX_LENGTH_FIELD, ""),
        "default_value": description.get("default_value", ""),
        "dependent": description.get("dependent", ""),
        "qualifier_type": record.get(REFERENCE_QUAL_TYPE_FIELD, "") if qualifier else "",
        "qualifier": qualifier,
        "attributes": record.get(ATTRIBUTES_FIELD, ""),
        "overrides": "\n".join(
            OVERRIDE_TEXT.format(
                attribute=override["attribute"],
                value=override["value"],
                table=override["table"],
            )
            for override in overrides
        ),
    }


class RelationsDialog(FramelessDialog):

    def __init__(self, result: RequestResult, parent: QWidget | None = None) -> None:
        super().__init__(RELATIONS_TITLE.format(table=result.table), parent)
        graph = RelationsGraph(result.table, relations(result, described_fields(result)))
        scroll = QScrollArea()
        scroll.setWidget(graph)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        size = graph.sizeHint()
        scroll.setMinimumSize(
            min(size.width() + RELATIONS_EXTRA, RELATIONS_MAXIMUM_WIDTH),
            min(size.height() + RELATIONS_EXTRA, RELATIONS_MAXIMUM_HEIGHT),
        )
        self.content_layout.addWidget(hint_label(RELATIONS_HINT))
        self.content_layout.addWidget(scroll, 1)
        close_button = primary_button(CLOSE_LABEL)
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        self.add_button_row(close_button)


class TableDescriptionResponseTab(RecordsResponseTab):

    def __init__(self, result: RequestResult) -> None:
        self._fields: list[DescribedField] = []
        self.relations_button: QPushButton = QPushButton(RELATIONS_LABEL)
        self.details_form: QFormLayout = QFormLayout()
        self.details_values: dict[str, QLabel] = {}
        self.empty_details_label: QLabel = hint_label(EMPTY_DETAILS)
        self.choices_widget: QTableWidget = QTableWidget()
        self.no_choices_label: QLabel = hint_label(NO_CHOICES)
        super().__init__(result)

    def build_menu_table(self, result: RequestResult) -> str:
        return shorten_text(result.table, TABLE_NAME_LIMIT)

    def columns(self) -> tuple[str, ...]:
        if active_only(self.result):
            return FIELD_COLUMNS
        return FIELD_COLUMNS + (ACTIVE_FIELD,)

    def checkbox_columns(self) -> tuple[str, ...]:
        return CHECKBOX_COLUMNS

    def export_columns(self) -> tuple[str, ...]:
        return self.columns()

    def records(self) -> list[dict[str, str]]:
        return [field.row for field in self._fields]

    def column_label(self, column: str) -> str:
        return COLUMN_LABELS.get(column) or super().column_label(column)

    def fill_content(self) -> None:
        self._fields = described_fields(self.result)
        self._show_field(None)
        super().fill_content()

    def build_toolbar(self, toolbar: QHBoxLayout) -> None:
        self.relations_button.clicked.connect(self._show_relations)
        toolbar.addWidget(self.relations_button)

    def build_details(self, layout: QVBoxLayout) -> None:
        layout.addWidget(section_label(DETAILS_SECTION))
        details = QWidget()
        details.setFixedHeight(DETAILS_HEIGHT)
        row = QHBoxLayout(details)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(DETAILS_SPACING)
        row.addWidget(self._build_form(), 1)
        row.addWidget(self._build_choices(), 1)
        layout.addWidget(details)

    def on_row_selected(self, record: dict[str, str]) -> None:
        element = record.get(ELEMENT_FIELD, "")
        for field in self._fields:
            if field.row.get(ELEMENT_FIELD, "") == element:
                self._show_field(field)
                return

    def _build_form(self) -> QScrollArea:
        form = QWidget()
        form.setLayout(self.details_form)
        self.details_form.setContentsMargins(0, 0, 0, 0)
        self.details_form.addRow(self.empty_details_label)
        for key, label in DETAIL_ROWS:
            value = QLabel()
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.details_values[key] = value
            self.details_form.addRow(label, value)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(form)
        return scroll

    def _build_choices(self) -> QWidget:
        choices = QWidget()
        layout = QVBoxLayout(choices)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(section_label(CHOICES_SECTION))
        self.no_choices_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.no_choices_label, 1)
        layout.addWidget(self.choices_widget, 1)
        configure_table(self.choices_widget)
        self.choices_widget.setColumnCount(len(CHOICE_COLUMNS))
        self.choices_widget.setHorizontalHeaderLabels(list(CHOICE_COLUMNS))
        self.choices_widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.choices_widget.horizontalHeader().setStretchLastSection(True)
        return choices

    def _show_field(self, field: DescribedField | None) -> None:
        self.details_form.setRowVisible(self.empty_details_label, field is None)
        values = detail_values(field) if field is not None else {}
        for key, label in self.details_values.items():
            text = values.get(key, "")
            label.setText(text)
            self.details_form.setRowVisible(label, bool(text))
        choices = field.description.get("choices", []) if field is not None else []
        self.choices_widget.setVisible(bool(choices))
        self.no_choices_label.setVisible(not choices)
        self.no_choices_label.setText(NO_CHOICES if field is not None else "")
        self.choices_widget.setRowCount(len(choices))
        for row, choice in enumerate(choices):
            cells = (choice["value"], choice["label"], choice.get("dependent_value", ""))
            for column, text in enumerate(cells):
                self.choices_widget.setItem(row, column, QTableWidgetItem(text))

    def _show_relations(self) -> None:
        dialog = RelationsDialog(self.result, self)
        dialog.exec()
        Shiboken.delete(dialog)
