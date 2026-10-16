from collections.abc import Sequence

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDateEdit,
    QHBoxLayout,
    QRadioButton,
    QWidget,
)

TRUE_VALUE: str = "true"
FALSE_VALUE: str = "false"
DATE_FORMAT: str = "yyyy-MM-dd"
DATE_VALUE_TEMPLATE: str = "javascript:gs.dateGenerate('{date}','00:00:00')"
DEFAULT_DAYS_BACK: int = 7
APPLY_TEXT: str = "Apply"
APPLY_TOOLTIP: str = "Send this filter with the request"
DATE_TOOLTIP: str = "Type the date or pick it from the calendar"
ROW_SPACING: int = 6
CHOICE_SPACING: int = 14
DATE_WIDTH: int = 140


class BooleanFilterField(QCheckBox):

    changed = Signal()

    def __init__(self, checked: bool = True) -> None:
        super().__init__()
        self.setChecked(checked)
        self._refresh_text()
        self.toggled.connect(self._on_toggled)

    def value(self) -> str:
        return TRUE_VALUE if self.isChecked() else FALSE_VALUE

    def _on_toggled(self) -> None:
        self._refresh_text()
        self.changed.emit()

    def _refresh_text(self) -> None:
        self.setText(self.value())


class DateFilterField(QWidget):

    changed = Signal()

    def __init__(self, days_back: int = DEFAULT_DAYS_BACK) -> None:
        super().__init__()
        self.apply_box: QCheckBox = QCheckBox(APPLY_TEXT)
        self.date_input: QDateEdit = QDateEdit()
        self._build_ui(days_back)

    def is_applied(self) -> bool:
        return self.apply_box.isChecked()

    def date(self) -> QDate:
        return self.date_input.date()

    def value(self) -> str:
        if not self.is_applied():
            return ""
        return DATE_VALUE_TEMPLATE.format(date=self.date().toString(DATE_FORMAT))

    def _build_ui(self, days_back: int) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ROW_SPACING)
        self.apply_box.setToolTip(APPLY_TOOLTIP)
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat(DATE_FORMAT)
        self.date_input.setDate(QDate.currentDate().addDays(-days_back))
        self.date_input.setMaximumDate(QDate.currentDate())
        self.date_input.setToolTip(DATE_TOOLTIP)
        self.date_input.setMinimumWidth(DATE_WIDTH)
        self.date_input.setEnabled(False)
        layout.addWidget(self.apply_box)
        layout.addWidget(self.date_input)
        layout.addStretch(1)
        self.apply_box.toggled.connect(self._on_applied_changed)
        self.date_input.dateChanged.connect(self.changed)

    def _on_applied_changed(self, applied: bool) -> None:
        self.date_input.setEnabled(applied)
        self.changed.emit()


class RadioChoiceField(QWidget):

    changed = Signal()

    def __init__(self, choices: Sequence[tuple[str, str]], checked: int = 0) -> None:
        super().__init__()
        self._choices: tuple[tuple[str, str], ...] = tuple(choices)
        self._group: QButtonGroup = QButtonGroup(self)
        self._build_ui(checked)

    def value(self) -> str:
        checked = self._group.checkedId()
        return self._choices[checked][0] if checked >= 0 else ""

    def set_value(self, key: str) -> None:
        for index, choice in enumerate(self._choices):
            if choice[0] == key:
                button = self._group.button(index)
                if button is not None:
                    button.setChecked(True)
                return

    def _build_ui(self, checked: int) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(CHOICE_SPACING)
        for index, (_, label) in enumerate(self._choices):
            button = QRadioButton(label)
            button.setChecked(index == checked)
            self._group.addButton(button, index)
            layout.addWidget(button)
        layout.addStretch(1)
        self._group.idToggled.connect(self._on_toggled)

    def _on_toggled(self, index: int, checked: bool) -> None:
        if checked:
            self.changed.emit()
