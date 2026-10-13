from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from request_types import GROUP_ORDER, RequestType, request_types_of_group
from tab import Tab
from ui_widgets import hint_label, title_label, vertical_spacer

BUTTONS_PER_ROW: int = 3
BUTTON_MINIMUM_HEIGHT: int = 48
HOME_HINT: str = "Pick a request type: a new request tab opens where you can set the target table and the filters."


class HomeTab(Tab):

    requestSelected = Signal(object)

    def __init__(self, title: str) -> None:
        super().__init__(title)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(title_label("ServiceNow Developer Panel"))
        main_layout.addWidget(hint_label(HOME_HINT))

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        for group in GROUP_ORDER:
            content_layout.addWidget(self._build_group(group))
        content_layout.addWidget(vertical_spacer())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _build_group(self, group: str) -> QGroupBox:
        box = QGroupBox(group)
        layout = QGridLayout(box)
        for index, request_type in enumerate(request_types_of_group(group)):
            layout.addWidget(self._build_button(request_type), index // BUTTONS_PER_ROW, index % BUTTONS_PER_ROW)
        return box

    def _build_button(self, request_type: RequestType) -> QPushButton:
        button = QPushButton(request_type.label)
        button.setMinimumHeight(BUTTON_MINIMUM_HEIGHT)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(request_type.description)
        button.clicked.connect(lambda: self.requestSelected.emit(request_type))
        return button
