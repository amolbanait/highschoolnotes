"""Stage 5: one model call per concept, given the outline and that concept's segments."""

from app.core.config import Settings
from app.llm.client import LLM, TokenMeter
from app.llm.prompts import write as prompt
from app.pipeline.grounding import SourceIndex, mermaid_problem
from app.schemas.study_guide import ConceptOutput


def outline(concepts: list[dict]) -> list[dict]:
    return [{"id": c["id"], "title": c["title"], "summary": c["summary"]} for c in concepts]


def run_one(
    concept: dict,
    concepts: list[dict],
    index: SourceIndex,
    level: str,
    llm: LLM,
    meter: TokenMeter,
    settings: Settings,
    instruction: str | None = None,
) -> dict:
    segments = index.context_for(concept["source_refs"]) or index.segments[:24]
    system, user = prompt.build(concept, outline(concepts), segments, level, instruction)
    output, usage = llm.generate(
        stage="write", system=system, prompt=user, output=ConceptOutput, effort=settings.write_effort
    )
    meter.add("write", usage)
    return ground_section(concept, output.model_dump(), index)


def ground_section(concept: dict, written: dict, index: SourceIndex) -> dict:
    flags: list[str] = []
    refs = index.clean_refs(written.get("source_refs", [])) or concept["source_refs"]
    if not refs:
        flags.append("no_source_reference")

    examples = []
    for example in written.get("examples", []):
        example_refs = index.clean_refs(example.get("source_refs", []))
        if example["origin"] == "source" and not example_refs:
            # Claimed to come from the source but cites nothing real: label it honestly.
            example = {**example, "origin": "ai_generated"}
            flags.append("example_relabelled_ai_generated")
        examples.append({**example, "source_refs": example_refs if example["origin"] == "source" else []})

    analogy = written.get("analogy")
    if analogy and analogy.get("origin") == "source" and not refs:
        analogy = {**analogy, "origin": "ai_generated"}

    diagram = written.get("diagram")
    if diagram:
        problem = mermaid_problem(diagram.get("mermaid", ""))
        if problem or diagram.get("type") == "none":
            flags.append(f"diagram_dropped: {problem or 'no diagram type'}")
            diagram = None

    levels = written.get("levels") if concept["difficulty"] == "hard" else None

    return {
        "id": concept["id"],
        "key": concept["key"],
        "title": concept["title"],
        "difficulty": concept["difficulty"],
        "prerequisites": concept["prerequisites"],
        "teacher_emphasis": concept["teacher_emphasis"],
        "likely_on_test": concept["likely_on_test"],
        "concept": written["concept"],
        "why_it_matters": written["why_it_matters"],
        "how_it_works": written["how_it_works"],
        "examples": examples,
        "analogy": analogy,
        "common_mistake": written["common_mistake"],
        "quick_check": written["quick_check"],
        "levels": levels,
        "diagram": diagram,
        "source_refs": refs,
        "quality": {"score": None, "flags": flags},
    }
