from PySide6.QtWidgets import QCheckBox, QFormLayout, QScrollArea, QVBoxLayout, QWidget

from configuration.config_repository import ConfigRepository
from core.request_types import TABLE_DESCRIPTION
from request_tabs.request_tab import TABLE_REQUIRED_MESSAGE, RequestTab
from response_tabs.response_tab import ResponseTab
from response_tabs.table_description_response_tab import TableDescriptionResponseTab
from services.service import RequestCall, RequestResult, RequestService, RequestSpec
from services.table_description_call import TableDescriptionCall
from storage.request_hints import RequestHintRepository
from ui.ui_widgets import hint_label, section_label, vertical_spacer
from ui.widgets.suggestion_field import SuggestionField
from ui.widgets.table_query_form import TABLE_LABEL, TABLE_PLACEHOLDER

TARGET_SECTION: str = "Table to describe"
TARGET_HINT: str = (
    "The fields of the parent tables are read too, so the list includes every inherited "
    "field. The relations of the table are read in the same request."
)
ACTIVE_LABEL: str = "Only include active fields"
ACTIVE_HINT: str = "Clear it to list the inactive dictionary entries as well."


class TableDescriptionRequestTab(RequestTab):

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        self.table_field: SuggestionField = SuggestionField(self.table_names)
        self.active_field: QCheckBox = QCheckBox(ACTIVE_LABEL)
        super().__init__(TABLE_DESCRIPTION, service, repository, hints)

    def target_table(self) -> str:
        return self.table_field.text().strip()

    def active_only(self) -> bool:
        return self.active_field.isChecked()

    def missing_requirement(self) -> str:
        return "" if self.target_table() else TABLE_REQUIRED_MESSAGE

    def record_hints(self) -> None:
        self.record_hint(self.target_table())

    def build_request(self) -> RequestSpec:
        return RequestSpec(
            request_type=self.request_type,
            table=self.target_table(),
            parameters={},
            columns=(),
            target=self.instance_selector.current_target(),
        )

    def send_request(self) -> RequestCall:
        return TableDescriptionCall(self.build_request(), self.active_only(), self.service)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return TableDescriptionResponseTab(result)

    def build_content(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(section_label(TARGET_SECTION))
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.table_field.setPlaceholderText(TABLE_PLACEHOLDER)
        self.table_field.textChanged.connect(self.refresh_state)
        form.addRow(TABLE_LABEL, self.table_field)
        self.active_field.setChecked(True)
        form.addRow("", self.active_field)
        form.addRow("", hint_label(ACTIVE_HINT))
        layout.addLayout(form)
        layout.addWidget(hint_label(TARGET_HINT))
        layout.addWidget(vertical_spacer())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll
