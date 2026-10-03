from app.llm.prompts.common import render_segments, system_prompt

ROLE = (
    "You are an expert teacher and curriculum designer. You read learning material and plan a study guide: "
    "what the concepts are, what a student must learn first, and which facts must be preserved exactly."
)


def build(segments: list[dict], level: str) -> tuple[str, str]:
    prompt = f"""{render_segments(segments)}

Plan a study guide for this material.

- concepts: the major ideas a student must understand, 3 to 15 of them. Merge tiny ideas; split ideas that \
are too big to teach in one section. Give each a short unique key. prerequisites lists keys of concepts that \
must be understood first (only concepts in your list). Mark difficulty "hard" only for concepts that need \
several explanations. Choose a diagram kind only when the concept has a process, cycle, hierarchy, comparison, \
timeline or cause and effect that a picture would make clearer; otherwise "none".
- teacher_emphasis is true only when the source itself stresses something ("remember", "important", \
"this will be on the test", repetition). likely_on_test is your own judgement and is kept separate.
- vocabulary: technical terms a student needs, with simple definitions.
- facts: definitions, dates, names, events, numbers, rules, exceptions, cause-and-effect and comparisons \
worth memorizing, each with a verbatim quote.
- formulas: every formula or equation in the source, in LaTeX, copied exactly.
- relationships: how concepts connect (use concept keys).
- not_covered: important things a student would expect that the source does not clearly state.
- topics: the main topics in the order they should be taught (prerequisites first, not source order)."""
    return system_prompt(ROLE, level), prompt
