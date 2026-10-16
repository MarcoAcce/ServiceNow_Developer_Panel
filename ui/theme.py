from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from core.app_paths import fonts_directory

Color = tuple[int, int, int]

ROLE_PROPERTY: str = "role"
FONT_FAMILY: str = "Lato"
FALLBACK_FAMILIES: tuple[str, ...] = ("Noto Sans", "DejaVu Sans", "Segoe UI", "sans-serif")
MONOSPACE_FAMILIES: str = "monospace"
FONT_FILE_PATTERN: str = "*.ttf"
FALLBACK_POINT_SIZE: int = 9
BODY_POINT_SIZE_DELTA: int = 2
SIDEBAR_POINT_SIZE_DELTA: int = 2


class Role(StrEnum):
    TITLE = "title"
    WINDOW = "window"
    TITLEBAR = "titlebar"
    WINDOW_BUTTON = "window_button"
    WINDOW_CLOSE = "window_close"
    SECTION = "section"
    HINT = "hint"
    ERROR = "error"
    RULE = "rule"
    CARD = "card"
    ROW = "row"
    PRIMARY = "primary"
    DANGER = "danger"
    MONOSPACE = "monospace"
    ICON_BUTTON = "icon_button"
    ITEM_TITLE = "item_title"
    ITEM_TITLE_SELECTED = "item_title_selected"
    ITEM_HINT = "item_hint"
    ITEM_HINT_SELECTED = "item_hint_selected"

BORDER_RADIUS: int = 4
CARD_RADIUS: int = 6
CONTROL_HEIGHT: int = 28
SCROLLBAR_WIDTH: int = 10
ITEM_PADDING_VERTICAL: int = 10
ITEM_PADDING_HORIZONTAL: int = 12
ITEM_MARGIN_VERTICAL: int = 2
ITEM_MARGIN_HORIZONTAL: int = 4
ITEM_EXTRA_HEIGHT: int = 2 * (ITEM_PADDING_VERTICAL + ITEM_MARGIN_VERTICAL)
TITLEBAR_HEIGHT: int = 38
TITLEBAR_BUTTON_WIDTH: int = 46
TITLEBAR_POINT_SIZE_DELTA: int = 1


@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    canvas: Color
    surface: Color
    surface_hover: Color
    surface_sunken: Color
    border: Color
    divider: Color
    text_primary: Color
    text_secondary: Color
    text_disabled: Color
    text_on_accent: Color
    accent: Color
    accent_hover: Color
    accent_pressed: Color
    accent_subtle: Color
    danger: Color
    danger_hover: Color
    danger_pressed: Color
    row_alternate: Color
    header: Color
    focus: Color
    titlebar: Color
    titlebar_hover: Color
    titlebar_text: Color
    titlebar_border: Color


LIGHT_THEME: Theme = Theme(
    key="light",
    label="Light",
    canvas=(247, 247, 248),
    surface=(255, 255, 255),
    surface_hover=(240, 241, 242),
    surface_sunken=(252, 252, 253),
    border=(201, 203, 207),
    divider=(228, 229, 231),
    text_primary=(41, 43, 46),
    text_secondary=(92, 95, 102),
    text_disabled=(159, 162, 168),
    text_on_accent=(255, 255, 255),
    accent=(79, 82, 189),
    accent_hover=(63, 65, 167),
    accent_pressed=(53, 55, 141),
    accent_subtle=(236, 237, 248),
    danger=(204, 62, 69),
    danger_hover=(177, 47, 54),
    danger_pressed=(145, 39, 44),
    row_alternate=(247, 247, 248),
    header=(240, 241, 242),
    focus=(129, 131, 208),
    titlebar=(31, 110, 84),
    titlebar_hover=(43, 133, 102),
    titlebar_text=(240, 248, 244),
    titlebar_border=(14, 58, 44),
)

DARK_THEME: Theme = Theme(
    key="dark",
    label="Dark",
    canvas=(25, 26, 28),
    surface=(33, 34, 36),
    surface_hover=(53, 55, 59),
    surface_sunken=(18, 19, 20),
    border=(68, 70, 75),
    divider=(53, 55, 59),
    text_primary=(240, 241, 242),
    text_secondary=(159, 162, 168),
    text_disabled=(121, 125, 134),
    text_on_accent=(18, 19, 20),
    accent=(129, 131, 208),
    accent_hover=(159, 160, 219),
    accent_pressed=(107, 109, 199),
    accent_subtle=(53, 55, 141),
    danger=(212, 94, 100),
    danger_hover=(223, 134, 139),
    danger_pressed=(204, 62, 69),
    row_alternate=(29, 30, 32),
    header=(41, 43, 46),
    focus=(159, 160, 219),
    titlebar=(19, 80, 60),
    titlebar_hover=(31, 110, 84),
    titlebar_text=(226, 240, 234),
    titlebar_border=(10, 44, 33),
)

THEMES: tuple[Theme, ...] = (LIGHT_THEME, DARK_THEME)
DEFAULT_THEME: Theme = LIGHT_THEME

_fonts_loaded: bool = False
_current_theme: Theme = DEFAULT_THEME


def current_theme() -> Theme:
    return _current_theme


def theme_of_key(key: str) -> Theme:
    for theme in THEMES:
        if theme.key == key:
            return theme
    return DEFAULT_THEME


def rgb(color: Color) -> str:
    return f"rgb({color[0]}, {color[1]}, {color[2]})"


def set_role(widget: QWidget, role: Role) -> None:
    widget.setProperty(ROLE_PROPERTY, str(role))


def refresh_role(widget: QWidget, role: Role) -> None:
    set_role(widget, role)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def load_fonts() -> bool:
    global _fonts_loaded
    if _fonts_loaded:
        return True
    directory = fonts_directory()
    if not directory.is_dir():
        return False
    for path in sorted(directory.glob(FONT_FILE_PATTERN)):
        if QFontDatabase.addApplicationFont(str(path)) >= 0:
            _fonts_loaded = True
    return _fonts_loaded


def base_point_size() -> int:
    system = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).pointSize()
    return (system if system > 0 else FALLBACK_POINT_SIZE) + BODY_POINT_SIZE_DELTA


def build_font(application: QApplication) -> QFont:
    font = QFont(application.font())
    font.setFamilies([FONT_FAMILY, *FALLBACK_FAMILIES])
    font.setPointSize(base_point_size())
    return font


def apply_theme(application: QApplication, theme: Theme) -> None:
    global _current_theme
    _current_theme = theme
    load_fonts()
    application.setFont(build_font(application))
    application.setPalette(build_palette(theme))
    application.setStyleSheet(build_stylesheet(theme))


def build_palette(theme: Theme) -> QPalette:
    palette = QPalette()
    groups = (
        QPalette.ColorGroup.Active,
        QPalette.ColorGroup.Inactive,
        QPalette.ColorGroup.Normal,
    )
    colors = {
        QPalette.ColorRole.Window: theme.canvas,
        QPalette.ColorRole.WindowText: theme.text_primary,
        QPalette.ColorRole.Base: theme.surface,
        QPalette.ColorRole.AlternateBase: theme.row_alternate,
        QPalette.ColorRole.Text: theme.text_primary,
        QPalette.ColorRole.PlaceholderText: theme.text_disabled,
        QPalette.ColorRole.Button: theme.surface,
        QPalette.ColorRole.ButtonText: theme.text_primary,
        QPalette.ColorRole.Highlight: theme.accent,
        QPalette.ColorRole.HighlightedText: theme.text_on_accent,
        QPalette.ColorRole.ToolTipBase: theme.surface,
        QPalette.ColorRole.ToolTipText: theme.text_primary,
        QPalette.ColorRole.Link: theme.accent,
        QPalette.ColorRole.LinkVisited: theme.accent_pressed,
        QPalette.ColorRole.Mid: theme.border,
        QPalette.ColorRole.Dark: theme.border,
        QPalette.ColorRole.Light: theme.surface,
    }
    for group in groups:
        for role, color in colors.items():
            palette.setColor(group, role, QColor(*color))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(*theme.text_disabled))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor(*theme.canvas))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor(*theme.canvas))
    return palette


def build_stylesheet(theme: Theme) -> str:
    sidebar_point_size = base_point_size() + SIDEBAR_POINT_SIZE_DELTA
    return f"""
QWidget {{
    color: {rgb(theme.text_primary)};
    font-family: "{FONT_FAMILY}";
}}
QMainWindow, QDialog, QMessageBox {{
    background-color: {rgb(theme.canvas)};
}}
QWidget[{ROLE_PROPERTY}="{Role.WINDOW}"] {{
    background-color: {rgb(theme.canvas)};
    border: 1px solid {rgb(theme.titlebar_border)};
}}
QWidget[{ROLE_PROPERTY}="{Role.TITLEBAR}"] {{
    background-color: {rgb(theme.titlebar)};
    border-bottom: 1px solid {rgb(theme.titlebar_border)};
}}
QWidget[{ROLE_PROPERTY}="{Role.TITLEBAR}"] QLabel {{
    color: {rgb(theme.titlebar_text)};
    background-color: transparent;
}}
QPushButton[{ROLE_PROPERTY}="{Role.WINDOW_BUTTON}"],
QPushButton[{ROLE_PROPERTY}="{Role.WINDOW_CLOSE}"] {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
    min-width: {TITLEBAR_BUTTON_WIDTH}px;
    max-width: {TITLEBAR_BUTTON_WIDTH}px;
    min-height: {TITLEBAR_HEIGHT - 1}px;
}}
QPushButton[{ROLE_PROPERTY}="{Role.WINDOW_BUTTON}"]:hover {{
    background-color: {rgb(theme.titlebar_hover)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.WINDOW_BUTTON}"]:pressed {{
    background-color: {rgb(theme.titlebar_border)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.WINDOW_CLOSE}"]:hover {{
    background-color: {rgb(theme.danger)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.WINDOW_CLOSE}"]:pressed {{
    background-color: {rgb(theme.danger_pressed)};
}}
QToolTip {{
    background-color: {rgb(theme.surface)};
    color: {rgb(theme.text_primary)};
    border: 1px solid {rgb(theme.border)};
    padding: 4px;
}}
QLabel {{
    background-color: transparent;
}}
QLabel[{ROLE_PROPERTY}="{Role.HINT}"] {{
    color: {rgb(theme.text_secondary)};
}}
QLabel[{ROLE_PROPERTY}="{Role.ERROR}"] {{
    color: {rgb(theme.danger)};
}}
QLabel[{ROLE_PROPERTY}="{Role.ITEM_TITLE}"] {{
    color: {rgb(theme.text_primary)};
    font-size: {sidebar_point_size}pt;
}}
QLabel[{ROLE_PROPERTY}="{Role.ITEM_TITLE_SELECTED}"] {{
    color: {rgb(theme.text_on_accent)};
    font-size: {sidebar_point_size}pt;
}}
QLabel[{ROLE_PROPERTY}="{Role.ITEM_HINT}"] {{
    color: {rgb(theme.text_secondary)};
}}
QLabel[{ROLE_PROPERTY}="{Role.ITEM_HINT_SELECTED}"] {{
    color: {rgb(theme.text_on_accent)};
}}
QFrame[{ROLE_PROPERTY}="{Role.RULE}"] {{
    background-color: {rgb(theme.divider)};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}
QFrame[{ROLE_PROPERTY}="{Role.CARD}"] {{
    background-color: {rgb(theme.surface)};
    border: 1px solid {rgb(theme.divider)};
    border-radius: {CARD_RADIUS}px;
}}
QFrame[{ROLE_PROPERTY}="{Role.ROW}"] {{
    background-color: {rgb(theme.canvas)};
    border: 1px solid {rgb(theme.divider)};
    border-radius: {BORDER_RADIUS}px;
}}
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
QGroupBox {{
    background-color: {rgb(theme.surface)};
    border: 1px solid {rgb(theme.divider)};
    border-radius: {CARD_RADIUS}px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0px 4px;
    background-color: {rgb(theme.canvas)};
    color: {rgb(theme.text_secondary)};
}}
QPushButton {{
    background-color: {rgb(theme.surface)};
    color: {rgb(theme.text_primary)};
    border: 1px solid {rgb(theme.border)};
    border-radius: {BORDER_RADIUS}px;
    padding: 5px 12px;
    min-height: {CONTROL_HEIGHT - 12}px;
}}
QPushButton:hover {{
    background-color: {rgb(theme.surface_hover)};
    border-color: {rgb(theme.accent)};
}}
QPushButton:pressed {{
    background-color: {rgb(theme.accent_subtle)};
}}
QPushButton:focus {{
    border-color: {rgb(theme.focus)};
}}
QPushButton:disabled {{
    color: {rgb(theme.text_disabled)};
    border-color: {rgb(theme.divider)};
    background-color: {rgb(theme.canvas)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.PRIMARY}"] {{
    background-color: {rgb(theme.accent)};
    color: {rgb(theme.text_on_accent)};
    border-color: {rgb(theme.accent)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.PRIMARY}"]:hover {{
    background-color: {rgb(theme.accent_hover)};
    border-color: {rgb(theme.accent_hover)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.PRIMARY}"]:pressed {{
    background-color: {rgb(theme.accent_pressed)};
    border-color: {rgb(theme.accent_pressed)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.PRIMARY}"]:disabled {{
    background-color: {rgb(theme.canvas)};
    color: {rgb(theme.text_disabled)};
    border-color: {rgb(theme.divider)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.DANGER}"] {{
    color: {rgb(theme.danger)};
    border-color: {rgb(theme.danger)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.DANGER}"]:hover {{
    background-color: {rgb(theme.danger)};
    color: {rgb(theme.text_on_accent)};
    border-color: {rgb(theme.danger)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.ICON_BUTTON}"] {{
    background-color: transparent;
    border: none;
    border-radius: {BORDER_RADIUS}px;
    padding: 0px;
    min-height: 0px;
}}
QPushButton[{ROLE_PROPERTY}="{Role.ICON_BUTTON}"]:hover {{
    background-color: {rgb(theme.surface_hover)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.ICON_BUTTON}"]:pressed {{
    background-color: {rgb(theme.accent_subtle)};
}}
QPushButton[{ROLE_PROPERTY}="{Role.ICON_BUTTON}"]:disabled {{
    background-color: transparent;
}}
QPushButton[{ROLE_PROPERTY}="{Role.DANGER}"]:pressed {{
    background-color: {rgb(theme.danger_pressed)};
    border-color: {rgb(theme.danger_pressed)};
}}
QLineEdit, QComboBox, QPlainTextEdit {{
    background-color: {rgb(theme.surface)};
    color: {rgb(theme.text_primary)};
    border: 1px solid {rgb(theme.border)};
    border-radius: {BORDER_RADIUS}px;
    padding: 4px 6px;
    selection-background-color: {rgb(theme.accent)};
    selection-color: {rgb(theme.text_on_accent)};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border-color: {rgb(theme.accent)};
}}
QLineEdit:disabled, QComboBox:disabled {{
    background-color: {rgb(theme.canvas)};
    color: {rgb(theme.text_disabled)};
}}
QLineEdit:read-only {{
    background-color: {rgb(theme.surface_hover)};
    color: {rgb(theme.text_secondary)};
}}
QPlainTextEdit[{ROLE_PROPERTY}="{Role.MONOSPACE}"],
QLineEdit[{ROLE_PROPERTY}="{Role.MONOSPACE}"] {{
    background-color: {rgb(theme.surface_sunken)};
    color: {rgb(theme.text_primary)};
    font-family: {MONOSPACE_FAMILIES};
}}
QComboBox QAbstractItemView {{
    background-color: {rgb(theme.surface)};
    border: 1px solid {rgb(theme.border)};
    selection-background-color: {rgb(theme.accent)};
    selection-color: {rgb(theme.text_on_accent)};
}}
QCheckBox {{
    background-color: transparent;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {rgb(theme.border)};
    border-radius: 3px;
    background-color: {rgb(theme.surface)};
}}
QCheckBox::indicator:hover {{
    border-color: {rgb(theme.accent)};
}}
QCheckBox::indicator:checked {{
    background-color: {rgb(theme.accent)};
    border-color: {rgb(theme.accent)};
}}
QCheckBox::indicator:disabled {{
    background-color: {rgb(theme.canvas)};
    border-color: {rgb(theme.divider)};
}}
QRadioButton {{
    background-color: transparent;
    spacing: 6px;
}}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {rgb(theme.border)};
    border-radius: 8px;
    background-color: {rgb(theme.surface)};
}}
QRadioButton::indicator:hover {{
    border-color: {rgb(theme.accent)};
}}
QRadioButton::indicator:checked {{
    background-color: {rgb(theme.accent)};
    border-color: {rgb(theme.accent)};
}}
QRadioButton::indicator:disabled {{
    background-color: {rgb(theme.canvas)};
    border-color: {rgb(theme.divider)};
}}
QListWidget {{
    background-color: {rgb(theme.header)};
    border: none;
    border-right: 1px solid {rgb(theme.divider)};
    outline: none;
}}
QListWidget::item {{
    color: {rgb(theme.text_primary)};
    font-size: {sidebar_point_size}pt;
    padding: {ITEM_PADDING_VERTICAL}px {ITEM_PADDING_HORIZONTAL}px;
    margin: {ITEM_MARGIN_VERTICAL}px {ITEM_MARGIN_HORIZONTAL}px;
    border-radius: {BORDER_RADIUS}px;
}}
QListWidget::item:hover {{
    background-color: {rgb(theme.surface_hover)};
}}
QListWidget::item:selected {{
    background-color: {rgb(theme.accent)};
    color: {rgb(theme.text_on_accent)};
}}
QTableWidget {{
    background-color: {rgb(theme.surface)};
    alternate-background-color: {rgb(theme.row_alternate)};
    gridline-color: {rgb(theme.divider)};
    border: 1px solid {rgb(theme.divider)};
    border-radius: {BORDER_RADIUS}px;
}}
QTableWidget::item {{
    padding: 2px 4px;
}}
QTableWidget::item:selected {{
    background-color: {rgb(theme.accent_subtle)};
    color: {rgb(theme.text_primary)};
}}
QHeaderView::section {{
    background-color: {rgb(theme.header)};
    color: {rgb(theme.text_secondary)};
    border: none;
    border-right: 1px solid {rgb(theme.divider)};
    border-bottom: 1px solid {rgb(theme.border)};
    padding: 5px 6px;
}}
QTableCornerButton::section {{
    background-color: {rgb(theme.header)};
    border: none;
}}
QScrollBar:vertical {{
    background-color: transparent;
    width: {SCROLLBAR_WIDTH}px;
    margin: 0px;
}}
QScrollBar:horizontal {{
    background-color: transparent;
    height: {SCROLLBAR_WIDTH}px;
    margin: 0px;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background-color: {rgb(theme.border)};
    border-radius: {SCROLLBAR_WIDTH // 2}px;
    min-height: 24px;
    min-width: 24px;
}}
QScrollBar::handle:hover {{
    background-color: {rgb(theme.text_disabled)};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0px;
    width: 0px;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background-color: transparent;
}}
QMenu {{
    background-color: {rgb(theme.surface)};
    border: 1px solid {rgb(theme.border)};
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 18px;
    border-radius: {BORDER_RADIUS}px;
}}
QMenu::item:selected {{
    background-color: {rgb(theme.accent)};
    color: {rgb(theme.text_on_accent)};
}}
"""
