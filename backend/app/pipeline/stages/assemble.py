"""Stage 6: overview, objectives, summary and review checklist, from the finished sections."""

from app.core.config import Settings
from app.llm.client import LLM, TokenMeter
from app.llm.prompts import assemble as prompt
from app.schemas.study_guide import AssembleOutput


def section_digest(section: dict) -> dict:
    return {
        "id": section["id"],
        "title": section["title"],
        "concept": section["concept"],
        "how_it_works": section["how_it_works"],
        "source_refs": section["source_refs"],
    }


def run(
    title: str, sections: list[dict], level: str, llm: LLM, meter: TokenMeter, settings: Settings
) -> dict:
    system, user = prompt.build(title, [section_digest(s) for s in sections], level)
    output, usage = llm.generate(
        stage="assemble", system=system, prompt=user, output=AssembleOutput, effort=settings.write_effort
    )
    meter.add("assemble", usage)
    return output.model_dump()
