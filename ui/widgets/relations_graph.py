from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import (
    QFont,
    QFontMetrics,
    QHelpEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QToolTip, QWidget

from core.table_description import Relation, RelationKind
from ui.theme import Theme, current_theme
from ui.widgets.flow_graph import bold_of, color_of, small_of

NODE_WIDTH: int = 230
NODE_PADDING: int = 6
NODE_SPACING: int = 10
HIERARCHY_SPACING: int = 28
COLUMN_GAP: int = 150
MARGIN: int = 12
TITLE_SPACING: int = 10
LEGEND_SPACING: int = 18
LEGEND_LINE: int = 36
LEGEND_GAP: int = 8
LEGEND_ITEM_SPACING: int = 24
TREE_INDENT: int = 28
RADIUS: int = 6
LINE_WIDTH: float = 1.5
CENTER_LINE_WIDTH: int = 2
TRIANGLE_LENGTH: int = 10
TRIANGLE_WIDTH: int = 6
CARDINALITY_OFFSET: int = 12
CARDINALITY_SIZE: int = 16
CURVE_FACTOR: float = 0.5
ONE: str = "1"
MANY: str = "N"
TEXT_SEPARATOR: str = " · "
VIA_SEPARATOR: str = ", "
LEFT_TITLE: str = "Referenced by ({count})"
CENTER_TITLE: str = "Hierarchy"
RIGHT_TITLE: str = "References ({count})"
CENTER_SUBTITLE: str = "described table"
PARENT_SUBTITLE: str = "parent table"
CHILD_SUBTITLE: str = "extends {table}"
VIA_TEXT: str = "via {names}"
KIND_LABELS: dict[RelationKind, str] = {
    RelationKind.ONE_TO_ONE: "One to one",
    RelationKind.ONE_TO_MANY: "One to many",
    RelationKind.MANY_TO_MANY: "Many to many",
    RelationKind.PARENT: "Parent / child",
}
LEGEND_KINDS: tuple[RelationKind, ...] = (
    RelationKind.ONE_TO_ONE,
    RelationKind.ONE_TO_MANY,
    RelationKind.MANY_TO_MANY,
    RelationKind.PARENT,
)
HIERARCHY_KINDS: tuple[RelationKind, ...] = (RelationKind.PARENT, RelationKind.CHILD)
CENTER_FLAGS: int = int(Qt.AlignmentFlag.AlignCenter)
LEFT_FLAGS: int = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


@dataclass(frozen=True)
class GraphNode:
    title: str
    subtitle: str
    rect: QRect
    relation: Relation | None = None


@dataclass(frozen=True)
class GraphLayout:
    center: GraphNode
    ancestors: tuple[GraphNode, ...]
    children: tuple[GraphNode, ...]
    left: tuple[GraphNode, ...]
    right: tuple[GraphNode, ...]
    legend_top: int
    titles: tuple[tuple[str, QRect], ...]
    size: QSize


def cardinality(relation: Relation) -> str:
    if relation.kind is RelationKind.ONE_TO_ONE:
        return ONE
    if relation.kind is RelationKind.ONE_TO_MANY:
        return ONE if relation.outgoing else MANY
    return MANY


def relation_subtitle(relation: Relation) -> str:
    label = KIND_LABELS.get(relation.kind, "")
    if not relation.via:
        return label
    return TEXT_SEPARATOR.join((label, VIA_TEXT.format(names=VIA_SEPARATOR.join(relation.via))))


def edge_pen(kind: RelationKind, theme: Theme) -> QPen:
    if kind is RelationKind.ONE_TO_ONE:
        return QPen(color_of(theme.text_secondary), LINE_WIDTH)
    if kind is RelationKind.MANY_TO_MANY:
        return QPen(color_of(theme.accent), LINE_WIDTH, Qt.PenStyle.DashLine)
    if kind in HIERARCHY_KINDS:
        return QPen(color_of(theme.text_disabled), LINE_WIDTH)
    return QPen(color_of(theme.accent), LINE_WIDTH)


def node_height(font: QFont) -> int:
    title = QFontMetrics(bold_of(font)).height()
    subtitle = QFontMetrics(small_of(font)).height()
    return 2 * NODE_PADDING + title + subtitle


def stacked(
    relations: Sequence[Relation], left: int, top: int, width: int, height: int, spacing: int
) -> list[GraphNode]:
    nodes: list[GraphNode] = []
    for index, relation in enumerate(relations):
        rect = QRect(left, top + index * (height + spacing), width, height)
        nodes.append(GraphNode(relation.table, relation_subtitle(relation), rect, relation))
    return nodes


def layout_graph(table: str, relations: Sequence[Relation], font: QFont) -> GraphLayout:
    height = node_height(font)
    line = QFontMetrics(font).height()
    legend_top = MARGIN
    titles_top = legend_top + line + LEGEND_SPACING
    top = titles_top + line + TITLE_SPACING
    left_x = MARGIN
    center_x = left_x + NODE_WIDTH + COLUMN_GAP
    right_x = center_x + NODE_WIDTH + COLUMN_GAP
    parents = [relation for relation in relations if relation.kind is RelationKind.PARENT]
    children = [relation for relation in relations if relation.kind is RelationKind.CHILD]
    incoming = [
        relation
        for relation in relations
        if relation.kind not in HIERARCHY_KINDS and not relation.outgoing
    ]
    outgoing = [
        relation
        for relation in relations
        if relation.kind not in HIERARCHY_KINDS and relation.outgoing
    ]
    ancestors = stacked(
        list(reversed(parents)), center_x, top, NODE_WIDTH, height, HIERARCHY_SPACING
    )
    ancestors = [
        GraphNode(node.title, PARENT_SUBTITLE, node.rect, node.relation) for node in ancestors
    ]
    center_top = top + len(ancestors) * (height + HIERARCHY_SPACING)
    center = GraphNode(table, CENTER_SUBTITLE, QRect(center_x, center_top, NODE_WIDTH, height))
    child_nodes = [
        GraphNode(node.title, CHILD_SUBTITLE.format(table=table), node.rect, node.relation)
        for node in stacked(
            children,
            center_x + TREE_INDENT,
            center.rect.bottom() + HIERARCHY_SPACING,
            NODE_WIDTH - TREE_INDENT,
            height,
            NODE_SPACING,
        )
    ]
    left_nodes = stacked(incoming, left_x, top, NODE_WIDTH, height, NODE_SPACING)
    right_nodes = stacked(outgoing, right_x, top, NODE_WIDTH, height, NODE_SPACING)
    bottoms = [center.rect.bottom()] + [
        node.rect.bottom() for node in child_nodes + left_nodes + right_nodes
    ]
    titles = (
        (LEFT_TITLE.format(count=len(left_nodes)), QRect(left_x, titles_top, NODE_WIDTH, line)),
        (CENTER_TITLE, QRect(center_x, titles_top, NODE_WIDTH, line)),
        (
            RIGHT_TITLE.format(count=len(right_nodes)),
            QRect(right_x, titles_top, NODE_WIDTH, line),
        ),
    )
    return GraphLayout(
        center=center,
        ancestors=tuple(ancestors),
        children=tuple(child_nodes),
        left=tuple(left_nodes),
        right=tuple(right_nodes),
        legend_top=legend_top,
        titles=titles,
        size=QSize(right_x + NODE_WIDTH + MARGIN, max(bottoms) + MARGIN),
    )


class RelationsGraph(QWidget):

    def __init__(
        self, table: str, relations: Sequence[Relation], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._table: str = table
        self._relations: tuple[Relation, ...] = tuple(relations)
        self._layout: GraphLayout = layout_graph(table, self._relations, self.font())
        self.setMinimumSize(self._layout.size)

    def sizeHint(self) -> QSize:
        return self._layout.size

    def minimumSizeHint(self) -> QSize:
        return self._layout.size

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.StyleChange,
            QEvent.Type.PaletteChange,
            QEvent.Type.FontChange,
        ):
            self._relayout()

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ToolTip and isinstance(event, QHelpEvent):
            node = self._node_at(event.pos())
            if node is None:
                QToolTip.hideText()
            else:
                QToolTip.showText(event.globalPos(), f"{node.title}\n{node.subtitle}", self)
            return True
        return super().event(event)

    def paintEvent(self, event: QEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout = self._layout
        self._paint_legend(painter)
        self._paint_titles(painter)
        self._paint_side(painter, layout.left, left_side=True)
        self._paint_side(painter, layout.right, left_side=False)
        self._paint_ancestors(painter)
        self._paint_children(painter)
        for node in self._nodes():
            self._paint_node(painter, node, node is layout.center)
        painter.end()

    def _relayout(self) -> None:
        self._layout = layout_graph(self._table, self._relations, self.font())
        self.setMinimumSize(self._layout.size)
        self.updateGeometry()
        self.update()

    def _nodes(self) -> tuple[GraphNode, ...]:
        layout = self._layout
        return (
            layout.ancestors + (layout.center,) + layout.children + layout.left + layout.right
        )

    def _node_at(self, point: QPoint) -> GraphNode | None:
        for node in self._nodes():
            if node.rect.contains(point):
                return node
        return None

    def _paint_legend(self, painter: QPainter) -> None:
        theme = current_theme()
        font = self.font()
        metrics = QFontMetrics(font)
        painter.setFont(font)
        left = MARGIN
        top = self._layout.legend_top
        middle = top + metrics.height() / 2
        for kind in LEGEND_KINDS:
            painter.setPen(edge_pen(kind, theme))
            painter.drawLine(QPointF(left, middle), QPointF(left + LEGEND_LINE, middle))
            if kind is RelationKind.PARENT:
                self._paint_triangle(
                    painter, QPointF(left + LEGEND_LINE, middle), QPointF(1, 0)
                )
            left += LEGEND_LINE + LEGEND_GAP
            label = KIND_LABELS[kind]
            width = metrics.horizontalAdvance(label)
            painter.setPen(color_of(theme.text_secondary))
            painter.drawText(QRect(left, top, width, metrics.height()), LEFT_FLAGS, label)
            left += width + LEGEND_ITEM_SPACING

    def _paint_titles(self, painter: QPainter) -> None:
        painter.setFont(bold_of(self.font()))
        painter.setPen(color_of(current_theme().text_secondary))
        for title, rect in self._layout.titles:
            painter.drawText(rect, CENTER_FLAGS, title)

    def _paint_side(
        self, painter: QPainter, nodes: Sequence[GraphNode], left_side: bool
    ) -> None:
        theme = current_theme()
        center = self._layout.center.rect
        start_x = center.left() if left_side else center.right()
        step = center.height() / (len(nodes) + 1)
        for index, node in enumerate(nodes):
            relation = node.relation
            if relation is None:
                continue
            start = QPointF(start_x, center.top() + step * (index + 1))
            end_x = node.rect.right() if left_side else node.rect.left()
            end = QPointF(end_x, node.rect.center().y())
            reach = (end.x() - start.x()) * CURVE_FACTOR
            path = QPainterPath(start)
            path.cubicTo(
                QPointF(start.x() + reach, start.y()), QPointF(end.x() - reach, end.y()), end
            )
            painter.setPen(edge_pen(relation.kind, theme))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            self._paint_cardinality(painter, relation, end, left_side)

    def _paint_cardinality(
        self, painter: QPainter, relation: Relation, end: QPointF, left_side: bool
    ) -> None:
        offset = CARDINALITY_OFFSET if left_side else -CARDINALITY_OFFSET - CARDINALITY_SIZE
        rect = QRect(
            int(end.x() + offset),
            int(end.y() - CARDINALITY_SIZE),
            CARDINALITY_SIZE,
            CARDINALITY_SIZE,
        )
        painter.setFont(bold_of(self.font()))
        painter.setPen(color_of(current_theme().text_primary))
        painter.drawText(rect, CENTER_FLAGS, cardinality(relation))

    def _paint_ancestors(self, painter: QPainter) -> None:
        nodes = self._layout.ancestors + (self._layout.center,)
        painter.setPen(edge_pen(RelationKind.PARENT, current_theme()))
        for parent, child in zip(nodes, nodes[1:]):
            x = parent.rect.center().x()
            tip = QPointF(x, parent.rect.bottom())
            painter.drawLine(QPointF(x, child.rect.top()), tip + QPointF(0, TRIANGLE_LENGTH))
            self._paint_triangle(painter, tip, QPointF(0, -1))

    def _paint_children(self, painter: QPainter) -> None:
        children = self._layout.children
        if not children:
            return
        center = self._layout.center.rect
        trunk = center.left() + TREE_INDENT / 2
        tip = QPointF(trunk, center.bottom())
        painter.setPen(edge_pen(RelationKind.CHILD, current_theme()))
        last = children[-1].rect.center().y()
        painter.drawLine(tip + QPointF(0, TRIANGLE_LENGTH), QPointF(trunk, last))
        for child in children:
            middle = child.rect.center().y()
            painter.drawLine(QPointF(trunk, middle), QPointF(child.rect.left(), middle))
        self._paint_triangle(painter, tip, QPointF(0, -1))

    def _paint_triangle(self, painter: QPainter, tip: QPointF, direction: QPointF) -> None:
        theme = current_theme()
        back = tip - direction * TRIANGLE_LENGTH
        side = QPointF(-direction.y() * TRIANGLE_WIDTH, direction.x() * TRIANGLE_WIDTH)
        painter.save()
        painter.setPen(QPen(color_of(theme.text_disabled), LINE_WIDTH))
        painter.setBrush(color_of(theme.canvas))
        painter.drawPolygon(QPolygonF([tip, back + side, back - side]))
        painter.restore()

    def _paint_node(self, painter: QPainter, node: GraphNode, highlighted: bool) -> None:
        theme = current_theme()
        font = self.font()
        border = theme.accent if highlighted else theme.border
        fill = theme.accent_subtle if highlighted else theme.surface
        width = CENTER_LINE_WIDTH if highlighted else 1
        painter.setPen(QPen(color_of(border), width))
        painter.setBrush(color_of(fill))
        painter.drawRoundedRect(node.rect, RADIUS, RADIUS)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inner = node.rect.adjusted(NODE_PADDING, NODE_PADDING, -NODE_PADDING, -NODE_PADDING)
        title_font = bold_of(font)
        title_height = QFontMetrics(title_font).height()
        painter.setFont(title_font)
        painter.setPen(color_of(theme.text_primary))
        title = QFontMetrics(title_font).elidedText(
            node.title, Qt.TextElideMode.ElideRight, inner.width()
        )
        painter.drawText(
            QRect(inner.left(), inner.top(), inner.width(), title_height), LEFT_FLAGS, title
        )
        subtitle_font = small_of(font)
        painter.setFont(subtitle_font)
        painter.setPen(color_of(theme.text_secondary))
        subtitle = QFontMetrics(subtitle_font).elidedText(
            node.subtitle, Qt.TextElideMode.ElideRight, inner.width()
        )
        painter.drawText(
            QRect(
                inner.left(),
                inner.top() + title_height,
                inner.width(),
                inner.height() - title_height,
            ),
            LEFT_FLAGS,
            subtitle,
        )
