"""Stage 7: practice questions with an answer key, and flashcards. Citations are checked."""

from app.core.config import Settings
from app.llm.client import LLM, TokenMeter
from app.llm.prompts import practice as prompt
from app.pipeline.grounding import SourceIndex, normalize
from app.pipeline.stages.assemble import section_digest
from app.schemas.study_guide import PracticeOutput


def run(
    sections: list[dict],
    vocabulary: list[dict],
    facts: list[dict],
    index: SourceIndex,
    level: str,
    llm: LLM,
    meter: TokenMeter,
    settings: Settings,
) -> dict:
    system, user = prompt.build(
        [section_digest(s) for s in sections],
        [
            {"term": v["term"], "definition": v["definition"], "source_refs": v["source_refs"]}
            for v in vocabulary
        ],
        [{"text": f["text"], "source_refs": f["source_refs"]} for f in facts],
        level,
    )
    output, usage = llm.generate(
        stage="practice", system=system, prompt=user, output=PracticeOutput, effort=settings.write_effort
    )
    meter.add("practice", usage)
    return ground_practice(output.model_dump(), sections, index)


def ground_practice(practice: dict, sections: list[dict], index: SourceIndex) -> dict:
    section_refs = {s["id"]: s["source_refs"] for s in sections}
    questions = []
    for q in practice.get("questions", []):
        concept_id = q.get("concept_id") if q.get("concept_id") in section_refs else None
        refs = index.clean_refs(q.get("source_refs", [])) or section_refs.get(concept_id or "", [])
        options = [o for o in q.get("options", []) if o.strip()]
        answer = q["answer"]
        if options:
            match = [o for o in options if normalize(o) == normalize(answer)]
            if len(match) == 1 and len(options) >= 2:
                answer = match[0]
            else:
                options = []  # The answer is not exactly one option: keep it as an open question.
        questions.append(
            {
                "id": f"q{len(questions) + 1}",
                "type": q["type"],
                "prompt": q["prompt"],
                "options": options,
                "answer": answer,
                "explanation": q["explanation"],
                "concept_id": concept_id,
                "source_refs": refs,
            }
        )
    flashcards = [
        {
            "id": f"f{i + 1}",
            "front": card["front"],
            "back": card["back"],
            "source_refs": index.clean_refs(card.get("source_refs", [])),
        }
        for i, card in enumerate(practice.get("flashcards", []))
    ]
    return {"questions": questions, "flashcards": flashcards}
