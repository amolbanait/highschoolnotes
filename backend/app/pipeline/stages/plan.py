"""Stage 3: one model call maps concepts, prerequisites, vocabulary, facts and formulas."""

from app.core.config import Settings
from app.llm.client import LLM, TokenMeter
from app.llm.prompts import plan as prompt
from app.schemas.study_guide import PlanOutput


def run(segments: list[dict], level: str, llm: LLM, meter: TokenMeter, settings: Settings) -> dict:
    system, user = prompt.build(segments, level)
    output, usage = llm.generate(
        stage="plan", system=system, prompt=user, output=PlanOutput, effort=settings.plan_effort
    )
    meter.add("plan", usage)
    return output.model_dump()
