"""The whole pipeline in memory with the fake model: ordering, grounding, resume after a crash."""

import pytest

from app.core.config import Settings
from app.ingestion.segment import segment
from app.ingestion.text import TextExtractor
from app.llm.client import LLMError, TokenMeter
from app.pipeline import orchestrator
from app.schemas.study_guide import StudyGuideContent
from tests.fakes import FakeLLM


def _segments(sample_text):
    segs = segment(TextExtractor(markdown=True).extract(sample_text.encode()))
    return [{"ref": s.ref, "text": s.text, "heading_path": s.heading_path} for s in segs]


def _ctx(sample_text, llm, state=None, events=None, saves=None, budget=1_000_000):
    events = events if events is not None else []
    saves = saves if saves is not None else []
    return orchestrator.PipelineContext(
        segments=_segments(sample_text),
        level="high_school",
        llm=llm,
        meter=TokenMeter(budget=budget),
        settings=Settings(write_concurrency=2),
        state=state if state is not None else {},
        save=saves.append,
        emit=lambda t, d: events.append((t, d)),
    )


def test_full_guide(sample_text):
    events: list = []
    llm = FakeLLM()
    content = orchestrator.run(_ctx(sample_text, llm, events=events))
    guide = StudyGuideContent.model_validate(content)

    # Prerequisites first: inputs -> chlorophyll -> light reactions, whatever order the plan listed.
    assert [c.key for c in guide.concepts] == ["inputs", "chlorophyll", "light-reactions"]
    assert guide.concepts[2].prerequisites == ["c2"]
    assert guide.overview and guide.objectives and guide.summary and guide.review_checklist

    # Citations are real segment ids only.
    refs = {"s1", "s2", "s3"}
    for c in guide.concepts:
        assert set(c.source_refs) <= refs and c.source_refs
    assert "p99-s9" not in str(content) and "made-up" not in str(content)

    # The example that claimed to be from the source but cited nothing is relabelled.
    ex = guide.concepts[0].examples
    assert [e.origin for e in ex] == ["source", "ai_generated", "ai_generated"]
    assert "example_relabelled_ai_generated" in guide.concepts[0].quality.flags

    # Three levels only for the hard concept; diagram only where planned.
    assert guide.concepts[2].levels is not None and guide.concepts[0].levels is None
    assert guide.concepts[2].diagram is not None and guide.concepts[0].diagram is None

    # Vocabulary citation re-pointed to where the quote really is; invented fact unverified; bogus one dropped.
    assert guide.vocabulary[0].source_refs == ["s2"] and guide.vocabulary[0].verified
    assert [f.verified for f in guide.facts] == [True, False]
    assert guide.formulas[0].latex.startswith("6CO_2")
    assert [(r.from_, r.to) for r in guide.relationships] == [("c2", "c3")]

    # Practice: MC answer normalised to the option text; a bad MC becomes an open question.
    q1, q2 = guide.questions
    assert q1.answer == "Chlorophyll" and q1.options
    assert q2.options == [] and q2.concept_id is None and q2.source_refs == []
    assert guide.flashcards[0].id == "f1"
    assert any("could not be matched" in w for w in guide.warnings)

    types = [t for t, _ in events]
    assert types[0] == "stage" and "topics_detected" in types and types.count("section_ready") == 3
    assert llm.calls.count("plan") == 1 and llm.calls.count("write") == 3


def test_resume_after_failure_keeps_finished_work(sample_text):
    state: dict = {}
    with pytest.raises(LLMError):
        orchestrator.run(_ctx(sample_text, FakeLLM(fail_on_write_call=3), state=state))
    assert state["done"] == ["plan", "sequence"]
    finished = len(state["sections"])
    assert finished >= 1  # finished sections were saved before the failure

    llm = FakeLLM()
    content = orchestrator.run(_ctx(sample_text, llm, state=state))
    assert "plan" not in llm.calls, "the plan is not regenerated on resume"
    assert llm.calls.count("write") == 3 - finished
    assert len(content["concepts"]) == 3


def test_regenerate_one_section(sample_text):
    state: dict = {}
    orchestrator.run(_ctx(sample_text, FakeLLM(), state=state))
    llm = FakeLLM()
    content = orchestrator.regenerate_section(_ctx(sample_text, llm, state=state), "c2", "simpler")
    assert llm.calls == ["write"]
    assert content["concepts"][1]["id"] == "c2"


def test_budget_stops_the_guide(sample_text):
    from app.llm.client import BudgetExceeded

    with pytest.raises(BudgetExceeded):
        orchestrator.run(_ctx(sample_text, FakeLLM(), budget=2000))
