from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from core.acl.acl_verification import FlowNode, FlowStage
from ui.theme import Color, current_theme

NODE_WIDTH: int = 270
NODE_PADDING: int = 8
NODE_SPACING: int = 30
STAGE_SPACING: int = 54
MARGIN: int = 10
TITLE_SPACING: int = 8
TEXT_SPACING: int = 2
RADIUS: int = 6
LINE_WIDTH: int = 1
ARROW_LENGTH: int = 9
ARROW_WIDTH: int = 5
ARROW_MARGIN: int = 5
REFERENCE_POINT_SIZE_DELTA: int = -1
MINIMUM_POINT_SIZE: int = 6
EMPTY_WIDTH: int = 2 * NODE_WIDTH
EMPTY_TEXT: str = "No dynamic condition or script has to be evaluated."
TEXT_FLAGS: Qt.TextFlag = Qt.TextFlag.TextWordWrap
CENTER_FLAGS: int = int(Qt.AlignmentFlag.AlignCenter) | int(TEXT_FLAGS)
REFERENCE_FLAGS: int = int(Qt.AlignmentFlag.AlignCenter) | int(
    Qt.TextFlag.TextWrapAnywhere
)


@dataclass(frozen=True)
class NodeBox:
    node: FlowNode
    rect: QRect
    title_rect: QRect
    reference_rect: QRect
    detail_rect: QRect


@dataclass(frozen=True)
class StageBox:
    stage: FlowStage
    rect: QRect
    title_rect: QRect
    boxes: tuple[NodeBox, ...]


def color_of(color: Color) -> QColor:
    return QColor(color[0], color[1], color[2])


def bold_of(font: QFont) -> QFont:
    bold = QFont(font)
    bold.setBold(True)
    return bold


def small_of(font: QFont) -> QFont:
    small = QFont(font)
    small.setPointSize(
        max(MINIMUM_POINT_SIZE, font.pointSize() + REFERENCE_POINT_SIZE_DELTA)
    )
    return small


def wrapped_height(
    metrics: QFontMetrics, text: str, width: int, flags: int = CENTER_FLAGS
) -> int:
    if not text:
        return 0
    return metrics.boundingRect(QRect(0, 0, width, 0), flags, text).height()


def node_heights(
    nodes: Sequence[FlowNode],
    title: QFontMetrics,
    reference: QFontMetrics,
    detail: QFontMetrics,
    width: int,
) -> list[tuple[int, int, int, int]]:
    heights: list[tuple[int, int, int, int]] = []
    for node in nodes:
        title_height = wrapped_height(title, node.title, width)
        reference_height = wrapped_height(
            reference, node.reference, width, REFERENCE_FLAGS
        )
        detail_height = wrapped_height(detail, node.detail, width)
        lines = [title_height, reference_height, detail_height]
        total = sum(lines) + 2 * NODE_PADDING
        total += TEXT_SPACING * max(0, len([line for line in lines if line]) - 1)
        heights.append((total, title_height, reference_height, detail_height))
    return heights


def layout_stages(
    stages: Sequence[FlowStage], font: QFont
) -> tuple[tuple[StageBox, ...], QSize]:
    detail_metrics = QFontMetrics(font)
    title_metrics = QFontMetrics(bold_of(font))
    reference_metrics = QFontMetrics(small_of(font))
    text_width = NODE_WIDTH - 2 * NODE_PADDING
    if not stages:
        height = wrapped_height(detail_metrics, EMPTY_TEXT, EMPTY_WIDTH)
        return (), QSize(EMPTY_WIDTH + 2 * MARGIN, height + 2 * MARGIN)
    measures = [
        node_heights(
            stage.nodes, title_metrics, reference_metrics, detail_metrics, text_width
        )
        for stage in stages
    ]
    columns = [
        sum(height for height, _, _, _ in measure) + NODE_SPACING * (len(measure) - 1)
        for measure in measures
    ]
    titles = [
        wrapped_height(detail_metrics, stage.title, NODE_WIDTH) for stage in stages
    ]
    title_band = max(titles)
    body_height = max(columns)
    boxes: list[StageBox] = []
    for index, stage in enumerate(stages):
        left = MARGIN + index * (NODE_WIDTH + STAGE_SPACING)
        top = MARGIN + title_band + TITLE_SPACING
        offset = top + (body_height - columns[index]) // 2
        nodes: list[NodeBox] = []
        for node, measure in zip(stage.nodes, measures[index]):
            height, title_height, reference_height, detail_height = measure
            line = offset + NODE_PADDING
            title_rect = QRect(left + NODE_PADDING, line, text_width, title_height)
            line = title_rect.bottom() + TEXT_SPACING
            reference_rect = QRect(
                left + NODE_PADDING, line, text_width, reference_height
            )
            line = reference_rect.bottom() + TEXT_SPACING
            detail_rect = QRect(left + NODE_PADDING, line, text_width, detail_height)
            nodes.append(
                NodeBox(
                    node=node,
                    rect=QRect(left, offset, NODE_WIDTH, height),
                    title_rect=title_rect,
                    reference_rect=reference_rect,
                    detail_rect=detail_rect,
                )
            )
            offset += height + NODE_SPACING
        boxes.append(
            StageBox(
                stage=stage,
                rect=QRect(
                    left, MARGIN, NODE_WIDTH, title_band + TITLE_SPACING + body_height
                ),
                title_rect=QRect(left, MARGIN, NODE_WIDTH, title_band),
                boxes=tuple(nodes),
            )
        )
    width = MARGIN * 2 + len(stages) * NODE_WIDTH + (len(stages) - 1) * STAGE_SPACING
    height = MARGIN * 2 + title_band + TITLE_SPACING + body_height
    return tuple(boxes), QSize(width, height)


class FlowGraph(QWidget):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stages: tuple[FlowStage, ...] = ()
        self._boxes: tuple[StageBox, ...] = ()
        self._size: QSize = QSize(EMPTY_WIDTH, EMPTY_WIDTH)
        self._relayout()

    def set_stages(self, stages: Sequence[FlowStage]) -> None:
        self._stages = tuple(stages)
        self._relayout()

    def sizeHint(self) -> QSize:
        return self._size

    def minimumSizeHint(self) -> QSize:
        return self._size

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.StyleChange,
            QEvent.Type.PaletteChange,
            QEvent.Type.FontChange,
        ):
            self._relayout()

    def paintEvent(self, event: QEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._boxes:
            self._paint_empty(painter)
            painter.end()
            return
        for index, stage in enumerate(self._boxes):
            self._paint_stage(painter, stage)
            if index + 1 < len(self._boxes):
                self._paint_arrow(painter, stage, self._boxes[index + 1])
        painter.end()

    def _relayout(self) -> None:
        self._boxes, self._size = layout_stages(self._stages, self.font())
        self.setMinimumSize(self._size)
        self.updateGeometry()
        self.update()

    def _paint_empty(self, painter: QPainter) -> None:
        painter.setPen(color_of(current_theme().text_secondary))
        painter.drawText(self.rect(), CENTER_FLAGS, EMPTY_TEXT)

    def _paint_stage(self, painter: QPainter, stage: StageBox) -> None:
        theme = current_theme()
        font = self.font()
        painter.setFont(font)
        painter.setPen(color_of(theme.text_secondary))
        painter.drawText(stage.title_rect, CENTER_FLAGS, stage.stage.title)
        for index, box in enumerate(stage.boxes):
            painter.setPen(QPen(color_of(theme.border), LINE_WIDTH))
            painter.setBrush(color_of(theme.surface))
            painter.drawRoundedRect(box.rect, RADIUS, RADIUS)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setFont(bold_of(font))
            painter.setPen(color_of(theme.text_primary))
            painter.drawText(box.title_rect, CENTER_FLAGS, box.node.title)
            painter.setFont(small_of(font))
            painter.setPen(color_of(theme.text_disabled))
            painter.drawText(box.reference_rect, REFERENCE_FLAGS, box.node.reference)
            painter.setFont(font)
            painter.setPen(color_of(theme.text_secondary))
            painter.drawText(box.detail_rect, CENTER_FLAGS, box.node.detail)
            if index + 1 < len(stage.boxes):
                self._paint_joiner(painter, stage, box, stage.boxes[index + 1])

    def _paint_joiner(
        self, painter: QPainter, stage: StageBox, box: NodeBox, following: NodeBox
    ) -> None:
        gap = QRect(
            box.rect.left(),
            box.rect.bottom(),
            NODE_WIDTH,
            following.rect.top() - box.rect.bottom(),
        )
        painter.setFont(bold_of(self.font()))
        painter.setPen(color_of(current_theme().accent))
        painter.drawText(gap, CENTER_FLAGS, stage.stage.joiner)

    def _paint_arrow(
        self, painter: QPainter, stage: StageBox, following: StageBox
    ) -> None:
        theme = current_theme()
        middle = stage.rect.top() + stage.rect.height() / 2
        start = stage.rect.right() + ARROW_MARGIN
        end = following.rect.left() - ARROW_MARGIN
        painter.setPen(QPen(color_of(theme.text_secondary), LINE_WIDTH))
        painter.setBrush(color_of(theme.text_secondary))
        painter.drawLine(QPointF(start, middle), QPointF(end - ARROW_LENGTH, middle))
        head = QPolygonF(
            [
                QPointF(end, middle),
                QPointF(end - ARROW_LENGTH, middle - ARROW_WIDTH),
                QPointF(end - ARROW_LENGTH, middle + ARROW_WIDTH),
            ]
        )
        painter.drawPolygon(head)
        painter.setBrush(Qt.BrushStyle.NoBrush)
