from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout

from service import RequestResult
from response_tab import ResponseTab
from ui_widgets import script_view, section_label

SCRIPT_PREVIEW_HEIGHT: int = 180
EMPTY_SCRIPT_MESSAGE: str = "Select a row to read its script."


class TableRecordsResponseTab(ResponseTab):
    pass


class DictionaryResponseTab(ResponseTab):

    def column_label(self, column: str) -> str:
        if column == "element":
            return "Field"
        if column == "internal_type":
            return "Type"
        return super().column_label(column)


class ScriptResponseTab(ResponseTab):

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
        return tuple(column for column in self.result.columns if column != self.script_field)

    def on_row_selected(self, record: dict[str, str]) -> None:
        self.script_preview.setPlainText(record.get(self.script_field, ""))

    def result_updated(self) -> None:
        self.script_preview.clear()


class AclResponseTab(ScriptResponseTab):

    script_section_title: str = "ACL script"

    def column_label(self, column: str) -> str:
        if column == "admin_overrides":
            return "Admin overrides"
        return super().column_label(column)


class ClientScriptResponseTab(ScriptResponseTab):

    script_section_title: str = "Client script"


class BusinessRuleResponseTab(ScriptResponseTab):

    script_section_title: str = "Server script"


class ScriptIncludeResponseTab(ScriptResponseTab):

    script_section_title: str = "Script include source"


class DataPolicyResponseTab(ResponseTab):
    pass


class UiPolicyResponseTab(ScriptResponseTab):

    script_field: str = "script_true"
    script_section_title: str = "Script executed when true"


class UiActionResponseTab(ScriptResponseTab):

    script_section_title: str = "Action script"
