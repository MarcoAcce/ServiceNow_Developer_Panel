from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class BackgroundTask(QObject):

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, work: Callable[[], Any], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._work: Callable[[], Any] = work
        self._cancelled: bool = False

    def start(self) -> None:
        QThreadPool.globalInstance().start(TaskRunnable(self))

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            value = self._work()
        except Exception as error:
            if not self._cancelled:
                self.failed.emit(str(error))
            return
        if not self._cancelled:
            self.finished.emit(value)


class TaskRunnable(QRunnable):

    def __init__(self, task: BackgroundTask) -> None:
        super().__init__()
        self._task: BackgroundTask = task

    def run(self) -> None:
        self._task.run()
