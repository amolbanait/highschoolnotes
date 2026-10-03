"""Quality checks done by code: reading level, numbers that are not in the source, coverage.

These are cheap and deterministic. Their results go to the model reviewer as hints and into the
quality report; only a missing citation lowers a section's score directly.
"""

import re

from app.pipeline.grounding import SourceIndex, normalize

# Highest comfortable Flesch-Kincaid grade for each reading level. A section more than
# READING_SLACK grades above it is reported as too hard.
READING_CEILING = {"middle_school": 8, "high_school": 10, "honors": 12, "ap": 13, "college_intro": 14}
READING_SLACK = 2

_WORD = re.compile(r"[A-Za-z]+(?:'[a-z]+)?")
_SENTENCE_END = re.compile(r"[.!?]+(?:\s|$)")
_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w])")


def syllables(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and not word.endswith(("le", "ee", "ye")) and count > 1:
        count -= 1
    return max(1, count)


def reading_grade(text: str) -> float | None:
    """Flesch-Kincaid grade level, or None if there is too little text to judge."""
    words = _WORD.findall(text)
    if len(words) < 30:
        return None
    sentences = max(1, len(_SENTENCE_END.findall(text)))
    syl = sum(syllables(w) for w in words)
    return 0.39 * len(words) / sentences + 11.8 * syl / len(words) - 15.59


def _source_text(section: dict) -> list[str]:
    """The parts of a section that claim to teach the source (AI-written examples excluded)."""
    parts = [section.get("concept", ""), section.get("why_it_matters", "")]
    parts += section.get("how_it_works", [])
    levels = section.get("levels") or {}
    parts += [levels.get("understand", ""), levels.get("deeper", "")]
    parts += [e["text"] for e in section.get("examples", []) if e.get("origin") == "source"]
    return [p for p in parts if p]


def _explanation_text(section: dict) -> str:
    levels = section.get("levels") or {}
    parts = [section.get("concept", ""), section.get("why_it_matters", "")]
    parts += section.get("how_it_works", [])
    parts.append(levels.get("understand", ""))
    return " ".join(p.strip().rstrip(".") + "." for p in parts if p and p.strip())


def section_checks(section: dict, index: SourceIndex, level: str) -> dict:
    checks: dict = {}
    if not section.get("source_refs"):
        checks["no_source_reference"] = True

    cited = " ".join(index.by_ref[r]["text"] for r in section.get("source_refs", []) if r in index.by_ref)
    context = " ".join(s["text"] for s in index.context_for(section.get("source_refs", []))) or cited
    known = {n.replace(",", "") for n in _NUMBER.findall(context)}
    missing: list[str] = []
    for text in _source_text(section):
        for number in _NUMBER.findall(text):
            plain = number.replace(",", "")
            # Step numbers and other tiny counts are not worth checking.
            if plain not in known and plain not in missing and not (plain.isdigit() and int(plain) < 10):
                missing.append(plain)
    if missing:
        checks["numbers_not_in_source"] = missing[:10]

    grade = reading_grade(_explanation_text(section))
    if grade is not None:
        checks["reading_grade"] = round(grade, 1)
        if grade > READING_CEILING[level] + READING_SLACK:
            checks["reading_level_high"] = True
    return checks


def coverage(state: dict, index: SourceIndex, min_words: int = 60) -> dict:
    """Which substantial parts of the source no concept, fact or vocabulary item cites."""
    seq = state["sequence"]
    cited: set[str] = set()
    for section in state.get("sections", {}).values():
        cited.update(section.get("source_refs", []))
        for example in section.get("examples", []):
            cited.update(example.get("source_refs", []))
    for item in [*seq["facts"], *seq["vocabulary"], *seq["formulas"]]:
        cited.update(item.get("source_refs", []))
    for concept in seq["concepts"]:
        cited.update(concept.get("source_refs", []))

    total = 0
    uncovered: list[dict] = []
    for seg in index.segments:
        words = len(normalize(seg["text"]).split())
        total += words
        if seg["ref"] not in cited and words >= min_words:
            uncovered.append(
                {"ref": seg["ref"], "words": words, "heading": " > ".join(seg.get("heading_path") or [])}
            )
    uncovered_words = sum(u["words"] for u in uncovered)
    return {
        "uncited_segments": [u["ref"] for u in uncovered],
        "uncited_share": round(uncovered_words / total, 3) if total else 0.0,
        "uncited_headings": list(dict.fromkeys(u["heading"] for u in uncovered if u["heading"]))[:8],
    }
