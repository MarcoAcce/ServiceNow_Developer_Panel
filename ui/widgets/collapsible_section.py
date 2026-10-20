from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ui.icons import COLLAPSE_ICON, EXPAND_ICON, IconButton
from ui.ui_widgets import section_label

EXPAND_TOOLTIP: str = "Show this section"
COLLAPSE_TOOLTIP: str = "Hide this section"
HEADER_SPACING: int = 6


class CollapsibleHeader(QWidget):

    def __init__(self, section: "CollapsibleSection") -> None:
        super().__init__()
        self._section: CollapsibleSection = section
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        self._section.toggle()


class CollapsibleSection(QWidget):

    def __init__(self, title: str, body: QWidget, expanded: bool = False) -> None:
        super().__init__()
        self.body: QWidget = body
        self.toggle_button: IconButton = IconButton(EXPAND_ICON, EXPAND_TOOLTIP)
        self._expanded: bool = expanded
        self._build_ui(title)
        self.set_expanded(expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.body.setVisible(expanded)
        self.toggle_button.set_name(COLLAPSE_ICON if expanded else EXPAND_ICON)
        self.toggle_button.setToolTip(COLLAPSE_TOOLTIP if expanded else EXPAND_TOOLTIP)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def _build_ui(self, title: str) -> None:
        header = CollapsibleHeader(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(HEADER_SPACING)
        header_layout.addWidget(self.toggle_button)
        header_layout.addWidget(section_label(title), 1)
        self.toggle_button.clicked.connect(self.toggle)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(header)
        layout.addWidget(self.body)
