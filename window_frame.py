from enum import StrEnum

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app_paths import icon_image_path
from theme import (
    TITLEBAR_HEIGHT,
    TITLEBAR_POINT_SIZE_DELTA,
    Role,
    Theme,
    set_role,
)

RESIZE_MARGIN: int = 5
DRAG_THRESHOLD: int = 4
GLYPH_SIZE: int = 10
GLYPH_PEN_WIDTH: float = 1.4
TITLE_ICON_SIZE: int = 20
TITLE_SPACING: int = 10
TITLE_MARGIN: int = 10
FRAME_BORDER: int = 1


class Glyph(StrEnum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"
    RESTORE = "restore"
    CLOSE = "close"


EDGE_CURSORS: tuple[tuple[tuple[Qt.Edge, ...], Qt.CursorShape], ...] = (
    ((Qt.Edge.LeftEdge, Qt.Edge.TopEdge), Qt.CursorShape.SizeFDiagCursor),
    ((Qt.Edge.RightEdge, Qt.Edge.BottomEdge), Qt.CursorShape.SizeFDiagCursor),
    ((Qt.Edge.RightEdge, Qt.Edge.TopEdge), Qt.CursorShape.SizeBDiagCursor),
    ((Qt.Edge.LeftEdge, Qt.Edge.BottomEdge), Qt.CursorShape.SizeBDiagCursor),
    ((Qt.Edge.LeftEdge,), Qt.CursorShape.SizeHorCursor),
    ((Qt.Edge.RightEdge,), Qt.CursorShape.SizeHorCursor),
    ((Qt.Edge.TopEdge,), Qt.CursorShape.SizeVerCursor),
    ((Qt.Edge.BottomEdge,), Qt.CursorShape.SizeVerCursor),
)


def combine(edges: tuple[Qt.Edge, ...]) -> Qt.Edge:
    combined = edges[0]
    for edge in edges[1:]:
        combined = combined | edge
    return combined


def cursor_of_edges(edges: tuple[Qt.Edge, ...]) -> Qt.CursorShape:
    for candidate, cursor in EDGE_CURSORS:
        if set(candidate) == set(edges):
            return cursor
    return Qt.CursorShape.ArrowCursor


class WindowButton(QPushButton):

    def __init__(self, glyph: Glyph, role: Role) -> None:
        super().__init__()
        self._glyph: Glyph = glyph
        self._color: QColor = QColor(Qt.GlobalColor.white)
        self.setFlat(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        set_role(self, role)

    def set_glyph(self, glyph: Glyph) -> None:
        self._glyph = glyph
        self.update()

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(self._color, GLYPH_PEN_WIDTH))
        center = QRectF(self.rect()).center()
        half = GLYPH_SIZE / 2
        box = QRectF(center.x() - half, center.y() - half, GLYPH_SIZE, GLYPH_SIZE)
        if self._glyph is Glyph.MINIMIZE:
            painter.drawLine(box.left(), center.y(), box.right(), center.y())
        elif self._glyph is Glyph.MAXIMIZE:
            painter.drawRect(box)
        elif self._glyph is Glyph.RESTORE:
            painter.drawRect(box.adjusted(0, 3, -3, 0))
            painter.drawPolyline(
                [
                    QPoint(int(box.left() + 3), int(box.top() + 3)),
                    QPoint(int(box.left() + 3), int(box.top())),
                    QPoint(int(box.right()), int(box.top())),
                    QPoint(int(box.right()), int(box.bottom() - 3)),
                    QPoint(int(box.right() - 3), int(box.bottom() - 3)),
                ]
            )
        else:
            painter.drawLine(box.topLeft(), box.bottomRight())
            painter.drawLine(box.topRight(), box.bottomLeft())
        painter.end()


class TitleBar(QWidget):

    def __init__(self, window: QWidget, resizable: bool = True) -> None:
        super().__init__()
        self._window: QWidget = window
        self._resizable: bool = resizable
        self._press_position: QPoint | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(TITLEBAR_HEIGHT)
        set_role(self, Role.TITLEBAR)
        self._build_ui()

    def _build_ui(self) -> None:
        self._icon: QLabel = QLabel()
        self._icon.setFixedSize(TITLE_ICON_SIZE, TITLE_ICON_SIZE)
        self._title: QLabel = QLabel(self._window.windowTitle())
        font = self._title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + TITLEBAR_POINT_SIZE_DELTA)
        self._title.setFont(font)

        self._minimize: WindowButton | None = None
        self._maximize: WindowButton | None = None
        self._close: WindowButton = WindowButton(Glyph.CLOSE, Role.WINDOW_CLOSE)
        self._close.setToolTip("Close")
        self._close.clicked.connect(self._window.close)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(TITLE_MARGIN, 0, 0, 0)
        layout.setSpacing(TITLE_SPACING)
        layout.addWidget(self._icon)
        layout.addWidget(self._title)
        layout.addStretch(1)
        if self._resizable:
            self._minimize = WindowButton(Glyph.MINIMIZE, Role.WINDOW_BUTTON)
            self._maximize = WindowButton(Glyph.MAXIMIZE, Role.WINDOW_BUTTON)
            self._minimize.setToolTip("Minimize")
            self._maximize.setToolTip("Maximize")
            self._minimize.clicked.connect(self._window.showMinimized)
            self._maximize.clicked.connect(self.toggle_maximized)
            layout.addWidget(self._minimize)
            layout.addWidget(self._maximize)
        layout.addWidget(self._close)

        self._window.windowTitleChanged.connect(self._title.setText)
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        source = QPixmap(str(icon_image_path()))
        if source.isNull():
            return
        ratio = self.devicePixelRatioF()
        extent = int(TITLE_ICON_SIZE * ratio)
        pixmap = source.scaled(
            extent,
            extent,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        pixmap.setDevicePixelRatio(ratio)
        self._icon.setPixmap(pixmap)

    def set_theme(self, theme: Theme) -> None:
        color = QColor(*theme.titlebar_text)
        for button in (self._minimize, self._maximize, self._close):
            if button is not None:
                button.set_color(color)

    def refresh_window_state(self) -> None:
        if self._maximize is None:
            return
        maximized = self._window.isMaximized() or self._window.isFullScreen()
        self._maximize.set_glyph(Glyph.RESTORE if maximized else Glyph.MAXIMIZE)
        self._maximize.setToolTip("Restore" if maximized else "Maximize")

    def toggle_maximized(self) -> None:
        if not self._resizable:
            return
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        self._refresh_icon()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_position is None:
            super().mouseMoveEvent(event)
            return
        if not bool(event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        moved = event.position().toPoint() - self._press_position
        if moved.manhattanLength() < DRAG_THRESHOLD:
            super().mouseMoveEvent(event)
            return
        self._press_position = None
        self._start_move()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._press_position = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = None
            self.toggle_maximized()
            return
        super().mouseDoubleClickEvent(event)

    def _start_move(self) -> None:
        if self._resizable and self._window.isMaximized():
            self._window.showNormal()
        handle = self._window.windowHandle()
        if handle is not None:
            handle.startSystemMove()


class ResizeGrip(QWidget):

    def __init__(self, parent: QWidget, edges: tuple[Qt.Edge, ...]) -> None:
        super().__init__(parent)
        self.edges: tuple[Qt.Edge, ...] = edges
        self._combined: Qt.Edge = combine(edges)
        self.setCursor(cursor_of_edges(edges))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        handle = self.window().windowHandle()
        if handle is not None:
            handle.startSystemResize(self._combined)


GRIP_EDGES: tuple[tuple[Qt.Edge, ...], ...] = (
    (Qt.Edge.TopEdge,),
    (Qt.Edge.BottomEdge,),
    (Qt.Edge.LeftEdge,),
    (Qt.Edge.RightEdge,),
    (Qt.Edge.LeftEdge, Qt.Edge.TopEdge),
    (Qt.Edge.RightEdge, Qt.Edge.TopEdge),
    (Qt.Edge.LeftEdge, Qt.Edge.BottomEdge),
    (Qt.Edge.RightEdge, Qt.Edge.BottomEdge),
)


class WindowFrame(QWidget):

    def __init__(self, window: QWidget, resizable: bool = True) -> None:
        super().__init__()
        self._window: QWidget = window
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        set_role(self, Role.WINDOW)
        self.title_bar: TitleBar = TitleBar(window, resizable)
        self._body: QWidget = QWidget()
        self._body_layout: QVBoxLayout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(FRAME_BORDER, FRAME_BORDER, FRAME_BORDER, FRAME_BORDER)
        layout.setSpacing(0)
        layout.addWidget(self.title_bar)
        layout.addWidget(self._body, 1)

        self._grips: list[ResizeGrip] = (
            [ResizeGrip(self, edges) for edges in GRIP_EDGES] if resizable else []
        )
        self.refresh_window_state()

    def set_body(self, widget: QWidget) -> None:
        self._body_layout.addWidget(widget)

    def refresh_window_state(self) -> None:
        self.title_bar.refresh_window_state()
        self._layout_grips()

    def resizeEvent(self, event: QEvent) -> None:
        super().resizeEvent(event)
        self._layout_grips()

    def _layout_grips(self) -> None:
        resizable = not (self._window.isMaximized() or self._window.isFullScreen())
        for grip in self._grips:
            grip.setVisible(resizable)
            if resizable:
                grip.setGeometry(self._grip_geometry(grip.edges))
                grip.raise_()

    def _grip_geometry(self, edges: tuple[Qt.Edge, ...]) -> QRect:
        margin = RESIZE_MARGIN
        width = self.width()
        height = self.height()
        left = Qt.Edge.LeftEdge in edges
        right = Qt.Edge.RightEdge in edges
        top = Qt.Edge.TopEdge in edges
        bottom = Qt.Edge.BottomEdge in edges
        x = 0 if left else (width - margin if right else margin)
        y = 0 if top else (height - margin if bottom else margin)
        grip_width = margin if left or right else max(width - 2 * margin, 0)
        grip_height = margin if top or bottom else max(height - 2 * margin, 0)
        return QRect(x, y, grip_width, grip_height)


class FramelessWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self._frame: WindowFrame = WindowFrame(self)
        self.title_bar: TitleBar = self._frame.title_bar
        super().setCentralWidget(self._frame)

    def set_body(self, widget: QWidget) -> None:
        self._frame.set_body(widget)

    def apply_window_theme(self, theme: Theme) -> None:
        self.title_bar.set_theme(theme)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._frame.refresh_window_state()
