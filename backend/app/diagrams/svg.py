"""Draw parsed diagrams as simple, static SVG for exports (PDF and HTML), where Mermaid cannot run.

The layout is deliberately plain: flowchart nodes go in layers by their longest path from a
start node, timelines on one horizontal line, mindmaps as a top-down tree. Every string is
escaped, and the SVG has no scripts, links or external references.
"""

import textwrap
from html import escape

from app.diagrams.mermaid import Diagram, Flowchart, Mindmap, MindNode, Timeline

FONT = 13
CHAR_W = 7.0
LINE_H = 16
PAD = 10
GAP_MAJOR = 56  # between layers
GAP_MINOR = 18  # between nodes in a layer
WRAP = 20
LOOP = 60  # extra room for edges that loop back to an earlier layer
COLOR = "#334155"
FILL = "#eef2ff"
STROKE = "#6366f1"


def render(diagram: Diagram) -> str:
    if isinstance(diagram, Timeline):
        return _timeline(diagram)
    if isinstance(diagram, Mindmap):
        return _flowchart(_mindmap_as_flowchart(diagram))
    return _flowchart(diagram)


def _lines(label: str) -> list[str]:
    return textwrap.wrap(label, WRAP, break_long_words=True)[:4] or [""]


def _box(label: str) -> tuple[float, float]:
    lines = _lines(label)
    return max(len(line) for line in lines) * CHAR_W + 2 * PAD, len(lines) * LINE_H + 2 * PAD - 4


def _text(x: float, y: float, lines: list[str], size: int = FONT, weight: str = "normal") -> str:
    first = y - (len(lines) - 1) * LINE_H / 2
    spans = "".join(
        f'<tspan x="{x:.1f}" y="{first + i * LINE_H:.1f}">{escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<text font-size="{size}" font-weight="{weight}" fill="{COLOR}" text-anchor="middle" '
        f'dominant-baseline="middle">{spans}</text>'
    )


def _svg(width: float, height: float, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}" font-family="DejaVu Sans, Helvetica, Arial, sans-serif" role="img">'
        f"{body}</svg>"
    )


def _layers(chart: Flowchart) -> dict[str, int]:
    """Longest-path layering; edges that close a cycle are ignored for layering."""
    order = list(chart.nodes)
    outgoing: dict[str, list[str]] = {n: [] for n in order}
    for a, b, _ in chart.edges:
        outgoing[a].append(b)
    forward: dict[str, list[str]] = {n: [] for n in order}
    state: dict[str, int] = {}

    def visit(n: str) -> None:
        state[n] = 1
        for m in outgoing[n]:
            if state.get(m) == 1:
                continue  # back edge
            forward[n].append(m)
            if m not in state:
                visit(m)
        state[n] = 2

    for n in order:
        if n not in state:
            visit(n)
    layer = {n: 0 for n in order}
    for _ in range(len(order)):
        changed = False
        for n in order:
            for m in forward[n]:
                if layer[m] < layer[n] + 1:
                    layer[m] = layer[n] + 1
                    changed = True
        if not changed:
            break
    return layer


def _flowchart(chart: Flowchart) -> str:
    layer = _layers(chart)
    columns: dict[int, list[str]] = {}
    for node in chart.nodes:
        columns.setdefault(layer[node], []).append(node)
    sizes = {n: _box(label) for n, label in chart.nodes.items()}
    horizontal = chart.direction in ("LR", "RL")
    count = max(columns) + 1

    # Thickness of each layer along the main axis, and length of each layer across it.
    thick = [max((sizes[n][0] if horizontal else sizes[n][1]) for n in columns[i]) for i in range(count)]
    spans = [
        sum((sizes[n][1] if horizontal else sizes[n][0]) for n in columns[i])
        + GAP_MINOR * (len(columns[i]) - 1)
        for i in range(count)
    ]
    cross = max(spans)
    main = sum(thick) + GAP_MAJOR * (count - 1)
    centers: dict[str, tuple[float, float]] = {}
    offset = PAD
    for i in range(count):
        along = offset + thick[i] / 2
        pos = PAD + (cross - spans[i]) / 2
        for n in columns[i]:
            extent = sizes[n][1] if horizontal else sizes[n][0]
            mid = pos + extent / 2
            centers[n] = (along, mid) if horizontal else (mid, along)
            pos += extent + GAP_MINOR
        offset += thick[i] + GAP_MAJOR
    width, height = (main, cross) if horizontal else (cross, main)
    width, height = width + 2 * PAD, height + 2 * PAD
    if any(layer[b] <= layer[a] for a, b, _ in chart.edges):
        # Room outside the boxes for edges that loop back.
        if horizontal:
            height += LOOP
        else:
            width += LOOP
    if chart.direction in ("RL", "BT"):
        centers = {
            n: ((width - x, y) if chart.direction == "RL" else (x, height - y))
            for n, (x, y) in centers.items()
        }

    parts = []
    for a, b, label in chart.edges:
        (x1, y1), (x2, y2) = _edge_ends(centers[a], sizes[a], centers[b], sizes[b])
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if layer[b] <= layer[a]:
            # Back to an earlier layer (a cycle): loop around the outside so it crosses no boxes.
            if horizontal:
                ya, yb = centers[a][1] + sizes[a][1] / 2, centers[b][1] + sizes[b][1] / 2
                x1, y1, x2, y2 = centers[a][0], ya, centers[b][0], yb
                cx1, cy1, cx2, cy2 = x1, height - PAD / 2, x2, height - PAD / 2
            else:
                xa, xb = centers[a][0] + sizes[a][0] / 2, centers[b][0] + sizes[b][0] / 2
                x1, y1, x2, y2 = xa, centers[a][1], xb, centers[b][1]
                cx1, cy1, cx2, cy2 = width - PAD / 2, y1, width - PAD / 2, y2
            mx, my = (cx1 + cx2) / 2, (cy1 + cy2) / 2
            path = f"M{x1:.1f},{y1:.1f} C{cx1:.1f},{cy1:.1f} {cx2:.1f},{cy2:.1f} {x2:.1f},{y2:.1f}"
            tail = (cx2, cy2)
        else:
            path = f"M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}"
            tail = (x1, y1)
        parts.append(f'<path d="{path}" fill="none" stroke="{STROKE}" stroke-width="1.5"/>')
        parts.append(_arrowhead(tail, (x2, y2)))
        if label:
            w = len(label) * CHAR_W * 0.85 + 6
            parts.append(
                f'<rect x="{mx - w / 2:.1f}" y="{my - 9:.1f}" width="{w:.1f}" height="18" fill="white"/>'
                + _text(mx, my, [label], size=11)
            )
    for n, label in chart.nodes.items():
        (x, y), (w, h) = centers[n], sizes[n]
        parts.append(
            f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="6" '
            f'fill="{FILL}" stroke="{STROKE}" stroke-width="1.2"/>' + _text(x, y, _lines(label))
        )
    return _svg(width, height, "".join(parts))


def _arrowhead(tail: tuple[float, float], tip: tuple[float, float], size: float = 8) -> str:
    """A filled triangle at `tip`, pointing away from `tail` (drawn directly: not every renderer
    supports SVG markers)."""
    dx, dy = tip[0] - tail[0], tip[1] - tail[1]
    length = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    ux, uy = dx / length, dy / length
    bx, by = tip[0] - ux * size, tip[1] - uy * size
    px, py = -uy * size * 0.5, ux * size * 0.5
    return (
        f'<path d="M{tip[0]:.1f},{tip[1]:.1f} L{bx + px:.1f},{by + py:.1f} L{bx - px:.1f},{by - py:.1f} z" '
        f'fill="{STROKE}"/>'
    )


def _edge_ends(
    a: tuple[float, float], size_a: tuple[float, float], b: tuple[float, float], size_b: tuple[float, float]
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Clip the centre-to-centre line to the two boxes' borders."""

    def clip(c: tuple[float, float], size: tuple[float, float], toward: tuple[float, float]):
        dx, dy = toward[0] - c[0], toward[1] - c[1]
        if dx == 0 and dy == 0:
            return c
        hw, hh = size[0] / 2, size[1] / 2
        scale = min(hw / abs(dx) if dx else float("inf"), hh / abs(dy) if dy else float("inf"))
        return c[0] + dx * scale, c[1] + dy * scale

    return clip(a, size_a, b), clip(b, size_b, a)


def _mindmap_as_flowchart(mindmap: Mindmap) -> Flowchart:
    chart = Flowchart(direction="TB")

    def add(node: MindNode, parent: str | None) -> None:
        node_id = f"n{len(chart.nodes)}"
        chart.nodes[node_id] = node.label
        if parent:
            chart.edges.append((parent, node_id, ""))
        for child in node.children:
            add(child, node_id)

    add(mindmap.root, None)
    return chart


def _timeline(timeline: Timeline) -> str:
    col = WRAP * CHAR_W + 2 * PAD
    title_h = 28 if timeline.title else 0
    events_h = max(sum(len(_lines(e)) for e in events) for _, events in timeline.periods) * LINE_H
    width = col * len(timeline.periods) + 2 * PAD
    axis = PAD + title_h + 40
    height = axis + 24 + events_h + PAD
    parts = []
    if timeline.title:
        parts.append(_text(width / 2, PAD + 10, [timeline.title], size=15, weight="bold"))
    parts.append(
        f'<line x1="{PAD}" y1="{axis}" x2="{width - PAD}" y2="{axis}" stroke="{STROKE}" stroke-width="2"/>'
    )
    for i, (period, events) in enumerate(timeline.periods):
        x = PAD + col * i + col / 2
        parts.append(f'<circle cx="{x:.1f}" cy="{axis}" r="5" fill="{STROKE}"/>')
        parts.append(_text(x, axis - 20, _lines(period)[:2], weight="bold"))
        y = axis + 24
        for event in events:
            lines = _lines(event)
            parts.append(_text(x, y + (len(lines) - 1) * LINE_H / 2, lines, size=12))
            y += len(lines) * LINE_H
    return _svg(width, height, "".join(parts))
