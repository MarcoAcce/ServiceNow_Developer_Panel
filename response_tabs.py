from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout

from acl_controls import (
    COLUMN_LABELS,
    EXPORT_COLUMNS,
    GRID_COLUMNS,
    NAME_FIELD,
    SCRIPT_FLAG_COLUMN,
    controls_of,
    display_records,
    section_records,
)
from acl_requests import ACL_TABLE
from service import RequestResult
from response_tab import TABLE_NAME_LIMIT, RecordsResponseTab
from ui_widgets import script_view, section_label, shorten_text

SCRIPT_PREVIEW_HEIGHT: int = 180
EMPTY_SCRIPT_MESSAGE: str = "Select a row to read its script."


class TableRecordsResponseTab(RecordsResponseTab):
    pass


class DictionaryResponseTab(RecordsResponseTab):

    def column_label(self, column: str) -> str:
        if column == "element":
            return "Field"
        if column == "internal_type":
            return "Type"
        return super().column_label(column)


class ScriptResponseTab(RecordsResponseTab):

    script_field: str = "script"
    script_section_title: str = "Script"

    def __init__(self, result: RequestResult) -> None:
        self.script_preview: QPlainTextEdit = script_view(EMPTY_SCRIPT_MESSAGE)
        super().__init__(result)

    def build_details(self, layout: QVBoxLayout) -> None:
        self.script_preview.setFixedHeight(SCRIPT_PREVIEW_HEIGHT)
        layout.addWidget(section_label(self.script_section_title))
        layout.addWidget(self.script_preview)

    def columns(self) -> tuple[str, ...]:
        return tuple(column for column in super().columns() if column != self.script_field)

    def on_row_selected(self, record: dict[str, str]) -> None:
        self.script_preview.setPlainText(record.get(self.script_field, ""))

    def fill_content(self) -> None:
        self.script_preview.clear()
        super().fill_content()


class AclResponseTab(ScriptResponseTab):

    script_section_title: str = "ACL script"

    def __init__(self, result: RequestResult) -> None:
        self._records: list[dict[str, str]] = []
        super().__init__(result)

    def build_menu_table(self, result: RequestResult) -> str:
        records = section_records(result, ACL_TABLE)
        name = records[0].get(NAME_FIELD, "") if records else ""
        return shorten_text(name or result.table, TABLE_NAME_LIMIT)

    def columns(self) -> tuple[str, ...]:
        return GRID_COLUMNS

    def checkbox_columns(self) -> tuple[str, ...]:
        return (SCRIPT_FLAG_COLUMN,)

    def export_columns(self) -> tuple[str, ...]:
        return EXPORT_COLUMNS

    def records(self) -> list[dict[str, str]]:
        return self._records

    def column_label(self, column: str) -> str:
        return COLUMN_LABELS.get(column) or super().column_label(column)

    def fill_content(self) -> None:
        self._records = display_records(controls_of(self.result))
        super().fill_content()


class ClientScriptResponseTab(ScriptResponseTab):

    script_section_title: str = "Client script"


class BusinessRuleResponseTab(ScriptResponseTab):

    script_section_title: str = "Server script"


class ScriptIncludeResponseTab(ScriptResponseTab):

    script_section_title: str = "Script include source"


class DataPolicyResponseTab(RecordsResponseTab):
    pass


class UiPolicyResponseTab(ScriptResponseTab):

    script_field: str = "script_true"
    script_section_title: str = "Script executed when true"


class UiActionResponseTab(ScriptResponseTab):

    script_section_title: str = "Action script"
