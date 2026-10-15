from enum import StrEnum

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QPushButton

from theme import Color, Role, Theme, current_theme, rgb, set_role

HOME_ICON: str = "home"
SETTINGS_ICON: str = "settings"
REFRESH_ICON: str = "refresh"
DELETE_ICON: str = "delete"
ERROR_ICON: str = "error"
WARNING_ICON: str = "warning"

ICON_PATHS: dict[str, str] = {
    HOME_ICON: "M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z",
    SETTINGS_ICON: (
        "M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41."
        "12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-"
        "2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57"
        "-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c"
        "-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.2"
        "2.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0"
        " .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.9"
        "2-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3."
        "6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"
    ),
    REFRESH_ICON: (
        "M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-8 8s3.57 8 8 8c3.73 0 6.84-2.5"
        "5 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69"
        " 4.22 1.78L13 11h7V4l-2.35 2.35z"
    ),
    DELETE_ICON: (
        "M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"
    ),
    ERROR_ICON: (
        "M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm1 15h-2v-2h2v2z"
        "m0-4h-2V7h2v6z"
    ),
    WARNING_ICON: (
        "M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"
    ),
}

SVG_TEMPLATE: str = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="{path}"/></svg>'
)
ICON_SIZE: int = 16
BUTTON_SIZE: int = 26
RENDER_SCALE: int = 3


class Tone(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    ON_ACCENT = "on_accent"
    DANGER = "danger"


def tone_color(tone: Tone, theme: Theme) -> Color:
    if tone is Tone.SECONDARY:
        return theme.text_secondary
    if tone is Tone.ON_ACCENT:
        return theme.text_on_accent
    if tone is Tone.DANGER:
        return theme.danger
    return theme.text_primary


def material_icon(name: str, color: Color, size: int = ICON_SIZE) -> QIcon:
    document = SVG_TEMPLATE.format(color=rgb(color), path=ICON_PATHS[name])
    renderer = QSvgRenderer(QByteArray(document.encode("utf-8")))
    pixmap = QPixmap(size * RENDER_SCALE, size * RENDER_SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(RENDER_SCALE)
    return QIcon(pixmap)


def themed_icon(name: str, tone: Tone = Tone.PRIMARY, size: int = ICON_SIZE) -> QIcon:
    return material_icon(name, tone_color(tone, current_theme()), size)


class IconButton(QPushButton):

    def __init__(
        self,
        name: str,
        tooltip: str = "",
        tone: Tone = Tone.PRIMARY,
        size: int = BUTTON_SIZE,
        icon_size: int = ICON_SIZE,
    ) -> None:
        super().__init__()
        self._name: str = name
        self._tone: Tone = tone
        self._icon_size: int = icon_size
        self.setFixedSize(size, size)
        self.setIconSize(QSize(icon_size, icon_size))
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        set_role(self, Role.ICON_BUTTON)
        self.refresh_icon()

    def set_tone(self, tone: Tone) -> None:
        if tone is self._tone:
            return
        self._tone = tone
        self.refresh_icon()

    def refresh_icon(self) -> None:
        self.setIcon(themed_icon(self._name, self._tone, self._icon_size))


def refresh_icon_widgets(application: QApplication) -> None:
    for widget in application.allWidgets():
        if isinstance(widget, IconButton):
            widget.refresh_icon()
