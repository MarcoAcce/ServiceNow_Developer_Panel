from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class Tab(QWidget):

    menuTitleChanged = Signal(object)

    def __init__(self, title: str) -> None:
        super().__init__()
        self._menu_title: str = title

    @property
    def menu_title(self) -> str:
        return self._menu_title

    @menu_title.setter
    def menu_title(self, title: str) -> None:
        self._menu_title = title
        self.menuTitleChanged.emit(self)

    @property
    def menu_table(self) -> str:
        return ""

    @property
    def menu_detail(self) -> str:
        return ""

    @property
    def menu_tooltip(self) -> str:
        return self._menu_title

    def is_closable(self) -> bool:
        return False
