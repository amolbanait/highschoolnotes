"""The Mermaid subset parser (used to validate diagrams) and the SVG drawer (used by exports)."""

import pytest

from app.diagrams import mermaid, svg


@pytest.mark.parametrize(
    "source",
    [
        "flowchart LR\n  A[Light] --> B[Chlorophyll]",
        "graph TD;A-->B;B-.->C;C==>D",
        'flowchart LR\n A[Sun] -->|energy| B((Leaf)) --> C{Sugar?}\n C -- yes --> D["Glucose (C6)"]\n B & C --> E',
        "flowchart TB\n subgraph Cell\n A[Nucleus] --> B[DNA]\n end\n %% a comment\n classDef x fill:#fff",
        "timeline\n title US history\n 1492 : Columbus : lands\n 1607 : Jamestown\n : first colony",
        "mindmap\n  root((Cells))\n    Nucleus\n      DNA\n    Membrane",
    ],
)
def test_supported_diagrams_parse_and_draw(source):
    diagram = mermaid.parse(source)
    drawn = svg.render(diagram)
    assert drawn.startswith("<svg") and "<script" not in drawn
    assert mermaid.as_text(diagram)


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ("", "empty diagram"),
        ("pie title X", "unsupported diagram type"),
        ("flowchart LR\n A[Sun --> B", "unbalanced brackets"),
        ("flowchart LR\n A --> ", "arrow with nothing after it"),
        ("flowchart LR\n A[<img src=x onerror=alert(1)>] --> B", "labels cannot contain HTML"),
        ("%%{init: {'securityLevel': 'loose'}}%%\nflowchart LR\n A --> B", "not allowed"),
        ("flowchart LR\n A --> B\n click A call alert()", "cannot read"),
        ("flowchart LR\n subgraph X\n A --> B", "'subgraph' without 'end'"),
        ("flowchart XY\n A --> B", "unknown flowchart direction"),
        ("timeline\n just words", "cannot read"),
    ],
)
def test_bad_diagrams_are_rejected(source, reason):
    assert reason in (mermaid.problem(source) or "")


def test_text_version_reads_like_the_picture():
    chart = mermaid.parse("flowchart LR\n A[Sunlight] -->|energy| B[Leaf] --> C[Sugar]\n D[Lonely]")
    assert mermaid.as_text(chart) == ["Sunlight → (energy) → Leaf", "Leaf → Sugar", "Lonely"]


def test_labels_are_escaped_and_cycles_drawn():
    chart = mermaid.parse('flowchart TD\n A["Water & ice"] --> B[Clouds] --> A')
    drawn = svg.render(chart)
    assert "Water &amp; ice" in drawn and drawn.count("<path") == 4  # 2 lines, 2 arrowheads
    assert " C" in drawn  # the edge back to A is a curve


def test_too_many_nodes():
    source = "flowchart LR\n" + "\n".join(f" N{i} --> N{i + 1}" for i in range(40))
    assert mermaid.problem(source) == "diagram has too many nodes"
