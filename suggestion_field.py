from collections.abc import Callable, Sequence

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtGui import QFocusEvent, QMouseEvent
from PySide6.QtWidgets import QCompleter, QLineEdit, QWidget

VISIBLE_SUGGESTIONS: int = 8
QUIET_FOCUS_REASONS: tuple[Qt.FocusReason, ...] = (
    Qt.FocusReason.MouseFocusReason,
    Qt.FocusReason.PopupFocusReason,
    Qt.FocusReason.ActiveWindowFocusReason,
)


class SuggestionField(QLineEdit):

    def __init__(
        self, provider: Callable[[], Sequence[str]], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._provider: Callable[[], Sequence[str]] = provider
        self._model: QStringListModel = QStringListModel(self)
        self.setClearButtonEnabled(True)
        completer = QCompleter(self._model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(VISIBLE_SUGGESTIONS)
        self.setCompleter(completer)

    def suggestions(self) -> list[str]:
        return self._model.stringList()

    def show_suggestions(self) -> None:
        completer = self.completer()
        if completer is None:
            return
        self._model.setStringList([name for name in self._provider() if name])
        if not self._model.stringList():
            return
        completer.setCompletionPrefix(self.text().strip())
        completer.complete()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        self.show_suggestions()

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        if event.reason() not in QUIET_FOCUS_REASONS:
            self.show_suggestions()
