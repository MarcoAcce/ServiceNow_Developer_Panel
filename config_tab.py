from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from tab import Tab
from ui_widgets import hint_label, horizontal_rule, title_label, vertical_spacer

class ConfigTab(Tab):

    settingsSaved = Signal(object)

    def __init__(self, title: str) -> None:
        super().__init__(title)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(title_label("Configuration"))
        main_layout.addWidget(hint_label("Configuration"))
        main_layout.addWidget(horizontal_rule())
        main_layout.addWidget(vertical_spacer())
        self.save_button = QPushButton("Press here")
        self.save_button.clicked.connect(self._on_save_clicked)
        main_layout.addWidget(self.save_button)


    def _build_basic_page(self) -> QWidget:
        page = QWidget()
        layout = QFormLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        return page

    def _on_save_clicked(self) -> None:
        self.settingsSaved.emit(True)
