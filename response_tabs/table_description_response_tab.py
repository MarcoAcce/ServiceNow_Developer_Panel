from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
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
from ui.dialogs import CLOSE_LABEL, FramelessDialog, show_error
from ui.ui_widgets import (
    hint_label,
    horizontal_rule,
    primary_button,
    shorten_text,
    title_label,
)
from ui.widgets.detail_rows import ChoiceDetail, CodeDetail, InlineDetail
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
SAVE_IMAGE_LABEL: str = "Save as image"
SAVE_TEXT_LABEL: str = "Save as text"
SAVE_IMAGE_TITLE: str = "Save the relations as an image"
SAVE_TEXT_TITLE: str = "Save the relations as text"
IMAGE_FILTER: str = "PNG images (*.png)"
TEXT_FILTER: str = "Text files (*.txt)"
IMAGE_SUFFIX: str = ".png"
TEXT_SUFFIX: str = ".txt"
IMAGE_FORMAT: str = "PNG"
RELATIONS_FILE_NAME: str = "{table}_relations{suffix}"
SAVE_ERROR_TITLE: str = "Save failed"
IMAGE_ERROR_MESSAGE: str = "The image could not be written to {path}."
DETAILS_SECTION: str = "Field details"
DETAILS_TITLE_DELTA: int = 2
DETAILS_HEIGHT: int = 300
DETAILS_SPACING: int = 10
EMPTY_DETAILS: str = "Select a field in the list above to read its details."
CHOICES_TITLE: str = "Choice list"
DESCRIBE_LABEL: str = "Describe this table"
DESCRIBE_TOOLTIP: str = "Open a new describe table request for {table} and run it"
OVERRIDE_TEXT: str = "{attribute} = {value} on {table}"
REFERENCE_KEY: str = "reference"


class DetailKind(StrEnum):
    TEXT = "text"
    COPYABLE = "copyable"
    CODE = "code"


DETAIL_ROWS: tuple[tuple[str, str, DetailKind], ...] = (
    ("label", "Label", DetailKind.COPYABLE),
    ("type", "Type", DetailKind.TEXT),
    (REFERENCE_KEY, "Reference to", DetailKind.COPYABLE),
    ("defined_on", "Defined on", DetailKind.COPYABLE),
    ("max_length", "Max length", DetailKind.TEXT),
    ("dependent", "Dependent on", DetailKind.COPYABLE),
    ("default_value", "Default value", DetailKind.CODE),
    ("qualifier_type", "Qualifier type", DetailKind.TEXT),
    ("qualifier", "Reference qualifier", DetailKind.CODE),
    ("attributes", "Attributes", DetailKind.CODE),
    ("overrides", "Overrides", DetailKind.CODE),
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


def save_path(parent: QWidget, title: str, name: str, filter_text: str, suffix: str) -> str:
    path, _ = QFileDialog.getSaveFileName(parent, title, name, filter_text)
    if path and not path.lower().endswith(suffix):
        path = f"{path}{suffix}"
    return path


def choice_rows(field: DescribedField) -> list[tuple[str, str, str]]:
    return [
        (choice["value"], choice["label"], choice.get("dependent_value", ""))
        for choice in field.description.get("choices", [])
    ]


class RelationsDialog(FramelessDialog):

    def __init__(self, result: RequestResult, parent: QWidget | None = None) -> None:
        super().__init__(RELATIONS_TITLE.format(table=result.table), parent)
        self._table: str = result.table
        self.graph: RelationsGraph = RelationsGraph(
            result.table, relations(result, described_fields(result))
        )
        scroll = QScrollArea()
        scroll.setWidget(self.graph)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        size = self.graph.sizeHint()
        scroll.setMinimumSize(
            min(size.width() + RELATIONS_EXTRA, RELATIONS_MAXIMUM_WIDTH),
            min(size.height() + RELATIONS_EXTRA, RELATIONS_MAXIMUM_HEIGHT),
        )
        self.content_layout.addWidget(hint_label(RELATIONS_HINT))
        self.content_layout.addWidget(scroll, 1)
        image_button = QPushButton(SAVE_IMAGE_LABEL)
        image_button.clicked.connect(self._save_image)
        text_button = QPushButton(SAVE_TEXT_LABEL)
        text_button.clicked.connect(self._save_text)
        close_button = primary_button(CLOSE_LABEL)
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        self.add_button_row(image_button, text_button, close_button)

    def _file_name(self, suffix: str) -> str:
        return RELATIONS_FILE_NAME.format(table=self._table, suffix=suffix)

    def _save_image(self) -> None:
        path = save_path(
            self, SAVE_IMAGE_TITLE, self._file_name(IMAGE_SUFFIX), IMAGE_FILTER, IMAGE_SUFFIX
        )
        if not path:
            return
        if not self.graph.to_image().save(path, IMAGE_FORMAT):
            show_error(self, SAVE_ERROR_TITLE, IMAGE_ERROR_MESSAGE.format(path=path))
            return
        self.accept()

    def _save_text(self) -> None:
        path = save_path(
            self, SAVE_TEXT_TITLE, self._file_name(TEXT_SUFFIX), TEXT_FILTER, TEXT_SUFFIX
        )
        if not path:
            return
        try:
            Path(path).write_text(self.graph.text, encoding="utf-8")
        except OSError as error:
            show_error(self, SAVE_ERROR_TITLE, str(error))
            return
        self.accept()


class TableDescriptionResponseTab(RecordsResponseTab):

    describeRequested = Signal(str)

    def __init__(self, result: RequestResult) -> None:
        self._fields: list[DescribedField] = []
        self._reference: str = ""
        self.relations_button: QPushButton = QPushButton(RELATIONS_LABEL)
        self.details_section: QWidget = QWidget()
        self.details_scroll: QScrollArea = QScrollArea()
        self.empty_details_label: QLabel = hint_label(EMPTY_DETAILS)
        self.details: dict[str, InlineDetail | CodeDetail] = {}
        self.choices_detail: ChoiceDetail = ChoiceDetail(CHOICES_TITLE)
        self.describe_button: QPushButton = QPushButton(DESCRIBE_LABEL)
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
        layout.addWidget(horizontal_rule())
        self.details_section.setFixedHeight(DETAILS_HEIGHT)
        section = QVBoxLayout(self.details_section)
        section.setContentsMargins(0, 0, 0, 0)
        section.addWidget(title_label(DETAILS_SECTION, DETAILS_TITLE_DELTA))
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.details_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.details_scroll.setWidget(self._build_detail_rows())
        section.addWidget(self.details_scroll, 1)
        layout.addWidget(self.details_section)

    def on_row_selected(self, record: dict[str, str]) -> None:
        element = record.get(ELEMENT_FIELD, "")
        for field in self._fields:
            if field.row.get(ELEMENT_FIELD, "") == element:
                self._show_field(field)
                return

    def on_selection_cleared(self) -> None:
        self._show_field(None)

    def _build_detail_rows(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DETAILS_SPACING)
        layout.addWidget(self.empty_details_label)
        for key, title, kind in DETAIL_ROWS:
            detail = self._build_detail(title, kind)
            self.details[key] = detail
            layout.addWidget(detail)
        layout.addWidget(self.choices_detail)
        layout.addStretch(1)
        reference = self.details[REFERENCE_KEY]
        if isinstance(reference, InlineDetail):
            self.describe_button.clicked.connect(self._on_describe_clicked)
            reference.add_action(self.describe_button)
        return content

    def _build_detail(self, title: str, kind: DetailKind) -> InlineDetail | CodeDetail:
        if kind is DetailKind.CODE:
            return CodeDetail(title)
        return InlineDetail(title, copyable=kind is DetailKind.COPYABLE)

    def _show_field(self, field: DescribedField | None) -> None:
        self.details_section.setEnabled(field is not None)
        self.empty_details_label.setVisible(field is None)
        values = detail_values(field) if field is not None else {}
        for key, detail in self.details.items():
            detail.set_value(values.get(key, ""))
        self._reference = values.get(REFERENCE_KEY, "")
        self.describe_button.setToolTip(DESCRIBE_TOOLTIP.format(table=self._reference))
        self.choices_detail.set_choices(choice_rows(field) if field is not None else [])
        self.details_scroll.verticalScrollBar().setValue(0)

    def _on_describe_clicked(self) -> None:
        if self._reference:
            self.describeRequested.emit(self._reference)

    def _show_relations(self) -> None:
        dialog = RelationsDialog(self.result, self)
        dialog.exec()
        Shiboken.delete(dialog)
