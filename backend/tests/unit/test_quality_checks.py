"""Code checks that feed the quality review."""

from app.pipeline.grounding import SourceIndex
from app.quality.checks import coverage, reading_grade, section_checks, syllables

SEGMENTS = [
    {
        "ref": "s1",
        "text": "Plants make glucose. The leaf absorbs 450 nanometre light.",
        "heading_path": ["Light"],
    },
    {
        "ref": "s2",
        "text": " ".join(["Water moves up the stem through the xylem."] * 10),
        "heading_path": ["Water"],
    },
]


def _section(**kw):
    base = {
        "id": "c1",
        "title": "Light",
        "concept": "Leaves absorb light.",
        "why_it_matters": "Plants feed us.",
        "how_it_works": ["Step 1 happens.", "Light at 450 nanometres and 700 nanometres is absorbed."],
        "examples": [{"text": "A phone costs 300 dollars.", "origin": "ai_generated", "source_refs": []}],
        "levels": None,
        "source_refs": ["s1"],
    }
    return {**base, **kw}


def test_numbers_not_in_the_source_are_reported_but_ai_examples_are_not_checked():
    checks = section_checks(_section(), SourceIndex(SEGMENTS), "high_school")
    assert checks["numbers_not_in_source"] == ["700"]  # 450 is in the source; 300 is an AI example


def test_missing_citation():
    assert section_checks(_section(source_refs=[]), SourceIndex(SEGMENTS), "high_school")[
        "no_source_reference"
    ]


def test_reading_level():
    simple = "The cat sat on the mat. It was a good day. " * 6
    hard = (
        "Photosynthetic organisms utilize electromagnetic radiation, facilitating thermodynamically unfavorable "
        "biochemical transformations through sophisticated photochemical intermediates. "
    ) * 3
    assert reading_grade("Too short.") is None
    assert reading_grade(simple) < 3 < 14 < reading_grade(hard)
    assert syllables("photosynthesis") >= 4 and syllables("cat") == 1
    checks = section_checks(_section(concept=hard), SourceIndex(SEGMENTS), "middle_school")
    assert checks["reading_level_high"] is True


def test_coverage_finds_unused_parts_of_the_source():
    state = {
        "sequence": {"facts": [], "vocabulary": [], "formulas": [], "concepts": [{"source_refs": ["s1"]}]},
        "sections": {"c1": _section()},
    }
    result = coverage(state, SourceIndex(SEGMENTS))
    assert result["uncited_segments"] == ["s2"] and result["uncited_headings"] == ["Water"]
    assert 0.8 < result["uncited_share"] < 1
