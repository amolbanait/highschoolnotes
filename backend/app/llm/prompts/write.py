import json

from app.llm.prompts.common import render_segments, system_prompt

ROLE = (
    "You are an expert teacher writing one section of a study guide. You explain one concept so clearly "
    "that a student who reads only this section understands it."
)

DIAGRAM_HINT = {
    "process": "a Mermaid flowchart (flowchart LR) showing the steps in order",
    "cycle": "a Mermaid flowchart whose last step links back to the first",
    "hierarchy": "a Mermaid flowchart (flowchart TD) from the general idea down to its parts",
    "comparison": "a Mermaid flowchart with two or three branches showing what differs",
    "timeline": "a Mermaid timeline",
    "cause_effect": "a Mermaid flowchart (flowchart LR) of Cause --> Event --> Result",
}


def build(
    concept: dict,
    outline: list[dict],
    segments: list[dict],
    level: str,
    instruction: str | None = None,
    feedback: str | None = None,
) -> tuple[str, str]:
    diagram = concept.get("diagram", "none")
    parts = [
        render_segments(segments),
        "Guide outline (for context; write only the section for the concept below):",
        json.dumps(outline, ensure_ascii=False),
        "Concept to write:",
        json.dumps(
            {k: concept[k] for k in ("key", "title", "summary", "difficulty", "prerequisites")},
            ensure_ascii=False,
        ),
        """Write the section:
- concept: the idea in simple language.
- why_it_matters: why a student should care.
- how_it_works: step by step, one step per item.
- examples: at least one; two or three for difficult concepts. Prefer examples from school, sports, money, \
technology, everyday life, science experiments and real situations. Label each example's origin truthfully.
- analogy: an everyday analogy when it genuinely helps, otherwise null.
- common_mistake: something students commonly get wrong about this concept.
- quick_check: one or two short questions with answers.
- source_refs: the segment ids this section is based on.
- You may assume the prerequisite concepts were already explained; refer back to them rather than \
re-teaching them.""",
    ]
    if concept.get("difficulty") == "hard":
        parts.append(
            "- levels: this concept is difficult, so give three explanations: new (very simple), understand "
            "(normal for this reader) and deeper (more detail)."
        )
    else:
        parts.append("- levels: null (this concept is not marked difficult).")
    if diagram != "none":
        parts.append(
            f'- diagram: type "{diagram}", drawn as {DIAGRAM_HINT[diagram]}. Keep it under 12 nodes, use short '
            "labels in square brackets, and make every node and arrow true to the source."
        )
    else:
        parts.append("- diagram: null.")
    if instruction:
        parts.append(f"The student asked for this section to be rewritten with this request: {instruction}")
    if feedback:
        parts.append(feedback)
    return system_prompt(ROLE, level), "\n\n".join(parts)
