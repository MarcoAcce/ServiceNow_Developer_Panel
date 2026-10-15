from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from icons import DELETE_ICON, IconButton, Tone
from ui_widgets import as_row, section_label

ROLE_PLACEHOLDER: str = "Role name, for example itil"
ADD_ROLE_LABEL: str = "Add role"
ADD_ROLE_TOOLTIP: str = "Check another role held by this user"
ADD_ROLE_DISABLED_TOOLTIP: str = "Name the role you just added before adding another one"
ADD_USER_LABEL: str = "Add user"
ADD_USER_TOOLTIP: str = "Check another user, holding a different set of roles"
ADD_USER_DISABLED_TOOLTIP: str = "Name a role of the last user before adding another one"
REMOVE_ROLE_TOOLTIP: str = "Remove this role"
REMOVE_USER_TOOLTIP: str = "Remove this user"
USER_TITLE: str = "User {index}"
ROW_SPACING: int = 6
CARD_MARGIN: int = 8
HEADER_SPACING: int = 6


class RoleRow(QWidget):

    changed = Signal()
    removeRequested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.name_field: QLineEdit = QLineEdit()
        self.remove_button: IconButton = IconButton(
            DELETE_ICON, REMOVE_ROLE_TOOLTIP, Tone.DANGER
        )
        self._build_ui()

    def role(self) -> str:
        return self.name_field.text().strip().lower()

    def is_empty(self) -> bool:
        return not self.role()

    def focus_name(self) -> None:
        self.name_field.setFocus()

    def set_removable(self, removable: bool) -> None:
        self.remove_button.setEnabled(removable)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ROW_SPACING)
        self.name_field.setPlaceholderText(ROLE_PLACEHOLDER)
        self.name_field.setClearButtonEnabled(True)
        layout.addWidget(self.name_field, 1)
        layout.addWidget(self.remove_button)
        self.name_field.textChanged.connect(self.changed)
        self.remove_button.clicked.connect(lambda: self.removeRequested.emit(self))


class UserCard(QFrame):

    changed = Signal()
    removeRequested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[RoleRow] = []
        self._rows_layout: QVBoxLayout = QVBoxLayout()
        self.title_label = section_label("")
        self.add_button: QPushButton = QPushButton(ADD_ROLE_LABEL)
        self.remove_button: IconButton = IconButton(
            DELETE_ICON, REMOVE_USER_TOOLTIP, Tone.DANGER
        )
        self._build_ui()
        self._add_row()

    def roles(self) -> tuple[str, ...]:
        collected: dict[str, None] = {}
        for row in self._rows:
            role = row.role()
            if role:
                collected.setdefault(role, None)
        return tuple(collected)

    def is_empty(self) -> bool:
        return not self.roles()

    def set_index(self, index: int) -> None:
        self.title_label.setText(USER_TITLE.format(index=index))

    def set_removable(self, removable: bool) -> None:
        self.remove_button.setEnabled(removable)

    def focus_role(self) -> None:
        if self._rows:
            self._rows[-1].focus_name()

    def _build_ui(self) -> None:
        as_row(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(CARD_MARGIN, CARD_MARGIN, CARD_MARGIN, CARD_MARGIN)
        layout.setSpacing(ROW_SPACING)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(HEADER_SPACING)
        header.addWidget(self.title_label, 1)
        header.addWidget(self.remove_button)
        layout.addLayout(header)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(ROW_SPACING)
        layout.addLayout(self._rows_layout)
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addStretch(1)
        footer.addWidget(self.add_button)
        layout.addLayout(footer)
        self.add_button.clicked.connect(self._on_add_clicked)
        self.remove_button.clicked.connect(lambda: self.removeRequested.emit(self))

    def _add_row(self) -> None:
        row = RoleRow()
        row.changed.connect(self._on_changed)
        row.removeRequested.connect(self._on_remove_requested)
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        self._refresh_state()
        row.focus_name()

    def _on_add_clicked(self) -> None:
        self._add_row()

    def _on_changed(self) -> None:
        self._refresh_state()
        self.changed.emit()

    def _on_remove_requested(self, row: RoleRow) -> None:
        if len(self._rows) <= 1:
            return
        self._rows.remove(row)
        self._rows_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()
        self._refresh_state()
        self.changed.emit()

    def _refresh_state(self) -> None:
        addable = not self._rows or not self._rows[-1].is_empty()
        self.add_button.setEnabled(addable)
        self.add_button.setToolTip(
            ADD_ROLE_TOOLTIP if addable else ADD_ROLE_DISABLED_TOOLTIP
        )
        for row in self._rows:
            row.set_removable(len(self._rows) > 1)


class UserRoleField(QWidget):

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._cards: list[UserCard] = []
        self._cards_layout: QVBoxLayout = QVBoxLayout()
        self.add_button: QPushButton = QPushButton(ADD_USER_LABEL)
        self._build_ui()
        self._add_card()

    def profiles(self) -> tuple[tuple[str, ...], ...]:
        return tuple(card.roles() for card in self._cards if not card.is_empty())

    def focus_role(self) -> None:
        if self._cards:
            self._cards[0].focus_role()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ROW_SPACING)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(ROW_SPACING)
        layout.addLayout(self._cards_layout)
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addStretch(1)
        footer.addWidget(self.add_button)
        layout.addLayout(footer)
        self.add_button.clicked.connect(self._on_add_clicked)

    def _add_card(self) -> None:
        card = UserCard()
        card.changed.connect(self._on_changed)
        card.removeRequested.connect(self._on_remove_requested)
        self._cards.append(card)
        self._cards_layout.addWidget(card)
        self._refresh_state()
        card.focus_role()

    def _on_add_clicked(self) -> None:
        self._add_card()

    def _on_changed(self) -> None:
        self._refresh_state()
        self.changed.emit()

    def _on_remove_requested(self, card: UserCard) -> None:
        if len(self._cards) <= 1:
            return
        self._cards.remove(card)
        self._cards_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()
        self._refresh_state()
        self.changed.emit()

    def _refresh_state(self) -> None:
        addable = not self._cards or not self._cards[-1].is_empty()
        self.add_button.setEnabled(addable)
        self.add_button.setToolTip(
            ADD_USER_TOOLTIP if addable else ADD_USER_DISABLED_TOOLTIP
        )
        for index, card in enumerate(self._cards):
            card.set_index(index + 1)
            card.set_removable(len(self._cards) > 1)
