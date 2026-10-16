from collections.abc import Callable
from pathlib import Path

from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.background_task import BackgroundTask
from installer.installation import (
    DISPLAY_NAME,
    InstallError,
    InstallOptions,
    InstallResult,
    install,
    is_installed,
    launch,
    mcp_configuration,
    uninstall,
    validate,
)
from ui.dialogs import FramelessDialog, ask_confirmation, show_error
from ui.ui_widgets import (
    danger_button,
    hint_label,
    primary_button,
    script_view,
    section_label,
    show_status,
    title_label,
)

DIALOG_WIDTH: int = 620
CONFIGURATION_HEIGHT: int = 150
SECTION_SPACING: int = 8
ROW_SPACING: int = 8
WINDOW_TITLE: str = f"{DISPLAY_NAME} Setup"
INTRODUCTION: str = (
    "Installs the application and its MCP server in a folder of your choice. Everything "
    "needed is included: Python is not required. Instances, credentials and cache are "
    "stored in the data folder next to the application."
)
DATA_PLACEHOLDER: str = "Optional: a data folder from a previous or portable copy"
MCP_HINT: str = (
    "Add this to the MCP configuration of your client, for example .mcp.json for Claude "
    "Code. It is also saved as mcp.json in the install folder."
)
INSTALL_LABEL: str = "Install"
UPDATE_LABEL: str = "Update"
UNINSTALL_LABEL: str = "Uninstall"
BROWSE_LABEL: str = "Browse"
CANCEL_LABEL: str = "Cancel"
CLOSE_LABEL: str = "Close"
COPY_LABEL: str = "Copy"
COPIED_LABEL: str = "Copied"
LAUNCH_LABEL: str = "Launch"
INSTALLING_MESSAGE: str = "Installing..."
UNINSTALLING_MESSAGE: str = "Uninstalling..."
UPDATE_MESSAGE: str = "An installation was found here: it will be updated and its data kept."


class InstallerDialog(FramelessDialog):

    def __init__(self, target: Path, menu: bool, desktop: bool) -> None:
        super().__init__(WINDOW_TITLE)
        self.setMinimumWidth(DIALOG_WIDTH)
        self._task: BackgroundTask | None = None
        self._result: InstallResult | None = None
        self._pages: QStackedWidget = QStackedWidget()
        self._pages.addWidget(self._build_options_page(target, menu, desktop))
        self._pages.addWidget(self._build_finished_page())
        self.content_layout.addWidget(self._pages)
        self._refresh_target()

    def _build_options_page(self, target: Path, menu: bool, desktop: bool) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SECTION_SPACING)
        layout.addWidget(title_label(DISPLAY_NAME))
        layout.addWidget(hint_label(INTRODUCTION))

        layout.addWidget(section_label("Install folder"))
        self._target: QLineEdit = QLineEdit(str(target))
        self._target.textChanged.connect(self._refresh_target)
        layout.addLayout(self._browse_row(self._target, self._choose_target))
        self._target_status: QLabel = hint_label("")
        layout.addWidget(self._target_status)

        layout.addWidget(section_label("Shortcuts"))
        self._menu: QCheckBox = QCheckBox("Add to the application menu")
        self._menu.setChecked(menu)
        self._desktop: QCheckBox = QCheckBox("Add a desktop shortcut")
        self._desktop.setChecked(desktop)
        layout.addWidget(self._menu)
        layout.addWidget(self._desktop)

        layout.addWidget(section_label("Import data"))
        self._import: QLineEdit = QLineEdit()
        self._import.setPlaceholderText(DATA_PLACEHOLDER)
        self._import_row: QWidget = QWidget()
        self._import_row.setLayout(self._browse_row(self._import, self._choose_import))
        layout.addWidget(self._import_row)

        self._progress: QProgressBar = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.hide()
        layout.addWidget(self._progress)
        self._status: QLabel = hint_label("")
        layout.addWidget(self._status)

        self._uninstall: QPushButton = danger_button(UNINSTALL_LABEL)
        self._uninstall.clicked.connect(self._start_uninstall)
        self._cancel: QPushButton = QPushButton(CANCEL_LABEL)
        self._cancel.clicked.connect(self.reject)
        self._install: QPushButton = primary_button(INSTALL_LABEL)
        self._install.setDefault(True)
        self._install.clicked.connect(self._start_install)
        buttons = QHBoxLayout()
        buttons.setSpacing(ROW_SPACING)
        buttons.addWidget(self._uninstall)
        buttons.addStretch(1)
        buttons.addWidget(self._cancel)
        buttons.addWidget(self._install)
        layout.addLayout(buttons)
        return page

    def _build_finished_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SECTION_SPACING)
        layout.addWidget(title_label("Installation complete"))
        self._summary: QLabel = hint_label("")
        layout.addWidget(self._summary)
        layout.addWidget(section_label("MCP server"))
        layout.addWidget(hint_label(MCP_HINT))
        self._configuration: QPlainTextEdit = script_view()
        self._configuration.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._configuration.setFixedHeight(CONFIGURATION_HEIGHT)
        layout.addWidget(self._configuration)

        self._copy: QPushButton = QPushButton(COPY_LABEL)
        self._copy.clicked.connect(self._copy_configuration)
        close = QPushButton(CLOSE_LABEL)
        close.clicked.connect(self.accept)
        start = primary_button(LAUNCH_LABEL)
        start.setDefault(True)
        start.clicked.connect(self._launch)
        buttons = QHBoxLayout()
        buttons.setSpacing(ROW_SPACING)
        buttons.addWidget(self._copy)
        buttons.addStretch(1)
        buttons.addWidget(close)
        buttons.addWidget(start)
        layout.addLayout(buttons)
        return page

    def _browse_row(self, field: QLineEdit, choose: Callable[[], None]) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(ROW_SPACING)
        browse = QPushButton(BROWSE_LABEL)
        browse.clicked.connect(choose)
        row.addWidget(field, 1)
        row.addWidget(browse)
        return row

    def _choose_target(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Install folder", self._target.text())
        if chosen:
            self._target.setText(chosen)

    def _choose_import(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Data folder", self._import.text())
        if chosen:
            self._import.setText(chosen)

    def _target_path(self) -> Path:
        return Path(self._target.text().strip()).expanduser()

    def _import_path(self) -> Path | None:
        text = self._import.text().strip()
        return Path(text).expanduser() if text else None

    def _refresh_target(self) -> None:
        installed = is_installed(self._target_path())
        self._install.setText(UPDATE_LABEL if installed else INSTALL_LABEL)
        self._uninstall.setVisible(installed)
        self._import_row.setEnabled(not installed)
        self._target_status.setText(UPDATE_MESSAGE if installed else "")
        self._target_status.setVisible(installed)

    def _options(self) -> InstallOptions:
        return InstallOptions(
            target=self._target_path(),
            menu=self._menu.isChecked(),
            desktop=self._desktop.isChecked(),
            import_data=None if is_installed(self._target_path()) else self._import_path(),
        )

    def _set_busy(self, message: str) -> None:
        for widget in (self._target, self._menu, self._desktop, self._import_row):
            widget.setEnabled(False)
        for button in (self._install, self._uninstall, self._cancel):
            button.setEnabled(False)
        self._progress.show()
        show_status(self._status, message)

    def _set_idle(self, message: str = "", failed: bool = False) -> None:
        self._task = None
        for widget in (self._target, self._menu, self._desktop):
            widget.setEnabled(True)
        for button in (self._install, self._uninstall, self._cancel):
            button.setEnabled(True)
        self._progress.hide()
        show_status(self._status, message, failed)
        self._refresh_target()

    def _start_install(self) -> None:
        options = self._options()
        try:
            validate(options)
        except InstallError as error:
            show_error(self, WINDOW_TITLE, str(error))
            return
        self._set_busy(INSTALLING_MESSAGE)
        self._task = BackgroundTask(lambda: install(options), self)
        self._task.finished.connect(self._install_finished)
        self._task.failed.connect(self._task_failed)
        self._task.start()

    def _install_finished(self, result: InstallResult) -> None:
        self._set_idle()
        self._result = result
        places = []
        if result.menu_shortcut is not None:
            places.append("the application menu")
        if result.desktop_shortcut is not None:
            places.append("the desktop")
        lines = [f"Installed in {result.target}"]
        if places:
            lines.append(f"Shortcuts added to {' and '.join(places)}.")
        if result.desktop_missing:
            lines.append("No desktop folder was found, the desktop shortcut was skipped.")
        self._summary.setText("\n".join(lines))
        self._configuration.setPlainText(mcp_configuration(result.target))
        self._pages.setCurrentIndex(1)
        self.adjustSize()

    def _start_uninstall(self) -> None:
        target = self._target_path()
        if not ask_confirmation(
            self,
            UNINSTALL_LABEL,
            f"Remove the application and its shortcuts from {target}?",
            UNINSTALL_LABEL,
            destructive=True,
        ):
            return
        remove_data = ask_confirmation(
            self,
            "Delete data",
            "Also delete the data folder, with your instances, credentials and cache? "
            "Choose Cancel to keep it.",
            "Delete data",
            destructive=True,
        )
        self._set_busy(UNINSTALLING_MESSAGE)
        self._task = BackgroundTask(lambda: uninstall(target, remove_data), self)
        self._task.finished.connect(lambda _: self._set_idle(f"Uninstalled from {target}"))
        self._task.failed.connect(self._task_failed)
        self._task.start()

    def _task_failed(self, message: str) -> None:
        self._set_idle(message, failed=True)
        show_error(self, WINDOW_TITLE, message)

    def _copy_configuration(self) -> None:
        QGuiApplication.clipboard().setText(self._configuration.toPlainText())
        self._copy.setText(COPIED_LABEL)

    def _launch(self) -> None:
        if self._result is None:
            return
        try:
            launch(self._result.target)
        except OSError as error:
            show_error(self, WINDOW_TITLE, f"Could not start the application: {error}")
            return
        self.accept()

    def reject(self) -> None:
        if self._task is None:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._task is None:
            super().closeEvent(event)
        else:
            event.ignore()
