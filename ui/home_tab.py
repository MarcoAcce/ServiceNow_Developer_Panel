from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from configuration.config_repository import ConfigRepository
from ui.widgets.instance_selector import InstanceSelector
from core.request_types import (
    GROUP_FEATURED,
    TABLE_API_GROUPS,
    RequestType,
    request_types_of_group,
)
from ui.tab import Tab
from ui.theme import Role, set_role
from ui.ui_widgets import hint_label, horizontal_rule, section_label, title_label, vertical_spacer

BUTTONS_PER_ROW: int = 3
BUTTON_MINIMUM_HEIGHT: int = 48
FEATURED_TITLE_DELTA: int = 2
TABLE_API_TITLE: str = "Table APIs"
HOME_HINT: str = "Pick a request type: a new request tab opens where you can set the target table and the filters."
INSTANCE_SECTION: str = "Working instance"
INSTANCE_HINT: str = "The request tabs opened from here start on this instance and its active authentication method."


class HomeTab(Tab):

    requestSelected = Signal(object)

    def __init__(self, title: str, repository: ConfigRepository) -> None:
        super().__init__(title)
        self.instance_selector: InstanceSelector = InstanceSelector(repository)
        self._build_ui()

    def reload_instances(self) -> None:
        self.instance_selector.reload()

    def current_instance_id(self) -> int:
        return self.instance_selector.current_instance_id()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(title_label("ServiceNow Developer Panel"))
        main_layout.addWidget(hint_label(HOME_HINT))

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._build_featured())
        content_layout.addWidget(horizontal_rule())
        content_layout.addWidget(title_label(TABLE_API_TITLE, FEATURED_TITLE_DELTA))
        for group in TABLE_API_GROUPS:
            content_layout.addWidget(self._build_group(group))
        content_layout.addWidget(vertical_spacer())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        main_layout.addWidget(horizontal_rule())
        main_layout.addWidget(section_label(INSTANCE_SECTION))
        main_layout.addWidget(hint_label(INSTANCE_HINT))
        main_layout.addWidget(self.instance_selector)

    def _build_featured(self) -> QWidget:
        featured = QWidget()
        layout = QGridLayout(featured)
        layout.setContentsMargins(0, 0, 0, 0)
        for index, request_type in enumerate(request_types_of_group(GROUP_FEATURED)):
            button = self._build_button(request_type)
            set_role(button, Role.FEATURED)
            font = button.font()
            font.setBold(True)
            font.setPointSize(font.pointSize() + FEATURED_TITLE_DELTA)
            button.setFont(font)
            description = hint_label(request_type.description)
            description.setAlignment(Qt.AlignmentFlag.AlignTop)
            layout.addWidget(button, 0, index)
            layout.addWidget(description, 1, index)
        return featured

    def _build_group(self, group: str) -> QGroupBox:
        box = QGroupBox(group)
        layout = QGridLayout(box)
        for index, request_type in enumerate(request_types_of_group(group)):
            layout.addWidget(
                self._build_button(request_type),
                index // BUTTONS_PER_ROW,
                index % BUTTONS_PER_ROW,
            )
        return box

    def _build_button(self, request_type: RequestType) -> QPushButton:
        button = QPushButton(request_type.button_label)
        button.setMinimumHeight(BUTTON_MINIMUM_HEIGHT)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(request_type.description)
        button.clicked.connect(lambda: self.requestSelected.emit(request_type))
        return button
