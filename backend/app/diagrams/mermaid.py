"""A parser for the small part of Mermaid the guides use: flowcharts, timelines and mindmaps.

The web app draws diagrams with Mermaid itself; this parser exists so the server can reject a
diagram that would not draw (before the student sees a broken picture) and so exports, which
cannot run Mermaid, can draw the same diagram as SVG or as text.

Anything outside the supported subset is a parse error, including features that can run code
or load content in the browser (click handlers, links, %%{init}%% directives).
"""

import re
from dataclasses import dataclass, field

MAX_NODES = 30
MAX_SOURCE = 4000


class MermaidError(ValueError):
    pass


@dataclass
class Flowchart:
    direction: str  # LR, RL, TB, BT
    nodes: dict[str, str] = field(default_factory=dict)  # id -> label, in first-seen order
    edges: list[tuple[str, str, str]] = field(default_factory=list)  # (from, to, label)


@dataclass
class Timeline:
    title: str = ""
    periods: list[tuple[str, list[str]]] = field(default_factory=list)  # (period, events)


@dataclass
class MindNode:
    label: str
    children: list["MindNode"] = field(default_factory=list)


@dataclass
class Mindmap:
    root: MindNode


Diagram = Flowchart | Timeline | Mindmap

_HEADER = re.compile(r"^(flowchart|graph|timeline|mindmap)\b\s*(.*)$", re.IGNORECASE)
# Directives can reconfigure Mermaid in the browser; click/call lines fail to parse anyway.
_FORBIDDEN = re.compile(r"%%\{|javascript:", re.IGNORECASE)


def parse(source: str) -> Diagram:
    if not source or not source.strip():
        raise MermaidError("empty diagram")
    if len(source) > MAX_SOURCE:
        raise MermaidError("diagram too large")
    if _FORBIDDEN.search(source):
        raise MermaidError("diagram uses a feature that is not allowed")
    lines = [ln for ln in source.replace("\r\n", "\n").split("\n") if not ln.strip().startswith("%%")]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        raise MermaidError("empty diagram")
    first, _, after = lines[0].partition(";")  # "graph TD;A-->B" puts statements on the header line
    if after.strip():
        lines[1:1] = [after]
    match = _HEADER.match(first.strip())
    if not match:
        raise MermaidError("unsupported diagram type")
    kind, rest = match.group(1).lower(), match.group(2).strip()
    body = lines[1:]
    if kind in ("flowchart", "graph"):
        return _flowchart(rest, body)
    if kind == "timeline":
        return _timeline(rest, body)
    return _mindmap(body)


def problem(source: str) -> str | None:
    """None if the diagram parses, otherwise a short reason."""
    try:
        parse(source)
    except MermaidError as exc:
        return str(exc)
    return None


# ---------- flowchart ----------

_DIRECTIONS = {"LR": "LR", "RL": "RL", "TB": "TB", "TD": "TB", "BT": "BT"}
# Opening and closing delimiters of node shapes, longest first so "((" wins over "(".
_SHAPES = (
    ("([", "])"),
    ("[[", "]]"),
    ("[(", ")]"),
    ("((", "))"),
    ("{{", "}}"),
    ("[/", "/]"),
    ("[\\", "\\]"),
    ("[/", "\\]"),
    ("[\\", "/]"),
    ("[", "]"),
    ("(", ")"),
    ("{", "}"),
    (">", "]"),
)
_NODE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-.]*")
_EDGE_WITH_TEXT = re.compile(r"\s*(?:--|==)\s+(?P<text>[^\s\-=>|][^>|]*?)\s+(?:-{2,}|={2,})[>ox]?\s*")
_EDGE_DOTTED_TEXT = re.compile(r"\s*-\.\s+(?P<text>[^>|]+?)\s+\.-+>?\s*")
_EDGE = re.compile(r"\s*<?(?:-{2,}|={2,}|-\.+-|~~~)[>ox]?\s*(?:\|(?P<text>[^|]*)\|\s*)?")
_IGNORED = re.compile(r"^(classDef|class|style|linkStyle|direction)\b")


def _flowchart(header: str, body: list[str]) -> Flowchart:
    direction = _DIRECTIONS.get(header.split()[0].upper() if header else "TB")
    if direction is None:
        raise MermaidError(f"unknown flowchart direction '{header}'")
    chart = Flowchart(direction=direction)
    depth = 0
    for raw in body:
        for statement in raw.split(";"):
            line = statement.strip()
            if not line or _IGNORED.match(line):
                continue
            if line.startswith("subgraph"):
                depth += 1
                continue
            if line == "end":
                if depth == 0:
                    raise MermaidError("'end' without 'subgraph'")
                depth -= 1
                continue
            _statement(line, chart)
    if depth:
        raise MermaidError("'subgraph' without 'end'")
    if not chart.nodes:
        raise MermaidError("diagram has no nodes")
    if len(chart.nodes) > MAX_NODES:
        raise MermaidError("diagram has too many nodes")
    return chart


def _statement(line: str, chart: Flowchart) -> None:
    pos = 0
    previous: list[str] | None = None
    pending_label = ""
    while True:
        group, pos = _node_group(line, pos, chart)
        if previous is not None:
            for a in previous:
                for b in group:
                    chart.edges.append((a, b, pending_label))
        if pos >= len(line.rstrip()):
            return
        edge = (
            _EDGE_WITH_TEXT.match(line, pos) or _EDGE_DOTTED_TEXT.match(line, pos) or _EDGE.match(line, pos)
        )
        if not edge or edge.end() == pos:
            raise MermaidError(f"cannot read '{line[pos : pos + 30]}'")
        pending_label = _clean_label(edge.group("text") or "")
        previous, pos = group, edge.end()
        if pos >= len(line):
            raise MermaidError("arrow with nothing after it")


def _node_group(line: str, pos: int, chart: Flowchart) -> tuple[list[str], int]:
    ids: list[str] = []
    while True:
        node_id, pos = _node(line, pos, chart)
        ids.append(node_id)
        amp = re.compile(r"\s*&\s*").match(line, pos)
        if not amp:
            return ids, pos
        pos = amp.end()


def _node(line: str, pos: int, chart: Flowchart) -> tuple[str, int]:
    while pos < len(line) and line[pos] == " ":
        pos += 1
    match = _NODE_ID.match(line, pos)
    if not match:
        raise MermaidError(f"expected a node at '{line[pos : pos + 30]}'")
    node_id = match.group(0)
    # A node id may not swallow the start of an arrow ("A--" + ">B").
    for arrow in ("--", "==", "-."):
        cut = node_id.find(arrow)
        if cut > 0:
            node_id = node_id[:cut]
    pos = match.start() + len(node_id)
    label = None
    for opening, closing in _SHAPES:
        if line.startswith(opening, pos):
            start = pos + len(opening)
            if line.startswith('"', start):
                end_quote = line.find('"', start + 1)
                if end_quote < 0:
                    raise MermaidError("unbalanced quotes")
                label = line[start + 1 : end_quote]
                end = end_quote + 1
                if not line.startswith(closing, end):
                    raise MermaidError("unbalanced brackets")
            else:
                end = line.find(closing, start)
                if end < 0:
                    raise MermaidError("unbalanced brackets")
                label = line[start:end]
                if '"' in label:
                    raise MermaidError("unbalanced quotes")
            pos = end + len(closing)
            break
    if label is not None:
        chart.nodes[node_id] = _clean_label(label) or node_id
    else:
        chart.nodes.setdefault(node_id, node_id)
    return node_id, pos


def _clean_label(label: str) -> str:
    label = re.sub(r"<br\s*/?>", " ", label, flags=re.IGNORECASE)
    label = label.replace("#quot;", '"').replace("#amp;", "&")
    if re.search(r"[<>]", label):
        raise MermaidError("labels cannot contain HTML")
    return " ".join(label.split())


# ---------- timeline ----------


def _timeline(header: str, body: list[str]) -> Timeline:
    timeline = Timeline()
    if header:
        raise MermaidError("unexpected text after 'timeline'")
    for raw in body:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("title "):
            timeline.title = _clean_label(line[6:])
        elif line.startswith("section "):
            continue  # sections only group periods visually
        elif line.startswith(":"):
            if not timeline.periods:
                raise MermaidError("event before any period")
            timeline.periods[-1][1].extend(_events(line[1:]))
        elif ":" in line:
            period, events = line.split(":", 1)
            timeline.periods.append((_clean_label(period), _events(events)))
        else:
            raise MermaidError(f"cannot read '{line[:30]}'")
    if not timeline.periods:
        raise MermaidError("timeline has no periods")
    if len(timeline.periods) > MAX_NODES:
        raise MermaidError("diagram has too many nodes")
    return timeline


def _events(text: str) -> list[str]:
    return [_clean_label(e) for e in text.split(":") if e.strip()]


# ---------- mindmap ----------

_MIND_SHAPE = re.compile(
    r"^[A-Za-z0-9_]*(?:\(\((.*)\)\)|\(\[(.*)\]\)|\[(.*)\]|\((.*)\)|\{\{(.*)\}\}|\)\)(.*)\(\()$"
)


def _mindmap(body: list[str]) -> Mindmap:
    stack: list[tuple[int, MindNode]] = []
    root: MindNode | None = None
    count = 0
    for raw in body:
        if not raw.strip() or raw.strip().startswith("::icon"):
            continue
        indent = len(raw) - len(raw.lstrip())
        text = raw.strip()
        shaped = _MIND_SHAPE.match(text)
        label = next((g for g in shaped.groups() if g is not None), text) if shaped else text
        node = MindNode(_clean_label(label.strip('"')))
        count += 1
        if root is None:
            root = node
            stack = [(indent, node)]
            continue
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if not stack:
            raise MermaidError("mindmap has more than one root")
        stack[-1][1].children.append(node)
        stack.append((indent, node))
    if root is None:
        raise MermaidError("mindmap is empty")
    if count > MAX_NODES:
        raise MermaidError("diagram has too many nodes")
    return Mindmap(root)


# ---------- as text, for exports that cannot draw ----------


def as_text(diagram: Diagram) -> list[str]:
    """The diagram as short readable lines, e.g. 'Light → Chlorophyll'."""
    if isinstance(diagram, Flowchart):
        lines = []
        for a, b, label in diagram.edges:
            arrow = f" → ({label}) → " if label else " → "
            lines.append(f"{diagram.nodes[a]}{arrow}{diagram.nodes[b]}")
        linked = {n for a, b, _ in diagram.edges for n in (a, b)}
        lines += [label for node_id, label in diagram.nodes.items() if node_id not in linked]
        return lines
    if isinstance(diagram, Timeline):
        return [f"{period}: {'; '.join(events)}" if events else period for period, events in diagram.periods]
    lines: list[str] = []

    def walk(node: MindNode, depth: int) -> None:
        lines.append(("  " * depth) + ("• " if depth else "") + node.label)
        for child in node.children:
            walk(child, depth + 1)

    walk(diagram.root, 0)
    return lines
