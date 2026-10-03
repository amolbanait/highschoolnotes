import json

from app.llm.prompts.common import render_segments, system_prompt

ROLE = (
    "You are a careful fact-checker and experienced teacher. You review one section of a study guide "
    "that another writer produced from the source material below. You do not rewrite it; you score it and "
    "list specific problems so the writer can fix them."
)

FIELDS = (
    "concept",
    "why_it_matters",
    "how_it_works",
    "examples",
    "analogy",
    "common_mistake",
    "quick_check",
    "levels",
    "diagram",
    "source_refs",
)


def build(section: dict, segments: list[dict], level: str, checks: dict) -> tuple[str, str]:
    written = {k: section.get(k) for k in FIELDS}
    hints = []
    if checks.get("numbers_not_in_source"):
        hints.append(
            "These numbers appear in source-based text but not in the cited segments; check each one: "
            + ", ".join(checks["numbers_not_in_source"])
        )
    if checks.get("reading_grade") is not None and checks.get("reading_level_high"):
        hints.append(
            f"The text reads at about grade {checks['reading_grade']:.0f}, harder than this reader's level."
        )
    parts = [
        render_segments(segments),
        f"Section to review (concept: {section['title']}):",
        json.dumps(written, ensure_ascii=False),
    ]
    if hints:
        parts.append("Automatic checks found:\n- " + "\n- ".join(hints))
    parts.append(
        """Score each criterion from 0 to 100, where 90 or more means a careful teacher would hand it out \
as is, 70 means usable with small fixes, and below 50 means a student could learn something wrong:
- accuracy: every statement agrees with the source; definitions are right; formulas, numbers, dates and \
names are unchanged.
- grounding: nothing is presented as coming from the source that the source does not say. General \
knowledge the writer added is fine only if it is correct and not presented as the source's claim.
- examples: examples and analogies are correct, actually illustrate the concept, and their origin label is \
honest ("source" only if the source contains that example).
- clarity: a student at the stated level could follow it; terms are explained; steps are in order.
- visuals: the diagram is true to the source and helps understanding; null if there is no diagram.

List every real problem; an empty list is right for a good section. Mark a problem "major" only if a \
student could learn something false, or would miss the main idea. Do not report style preferences. \
Quote the exact words at fault inside the problem sentence when you can."""
    )
    return system_prompt(ROLE, level), "\n\n".join(parts)


def feedback(problems: list[dict]) -> str:
    """What the writer is told when its section scored below the threshold and is written again."""
    lines = [f"- {p['where']}: {p['problem']} Fix: {p['fix']}" for p in problems]
    return (
        "A reviewer checked an earlier version of this section against the source and found these "
        "problems. Write the section again, fixing every one, and keep everything else that was right:\n"
        + "\n".join(lines)
    )
