"""The quality review: score, rewrite once below the threshold, then flag."""

from app.core.config import Settings
from app.llm.client import LLMError, TokenMeter
from app.pipeline import orchestrator
from app.pipeline.stages import review
from app.schemas.study_guide import StudyGuideContent
from tests.fakes import FakeLLM
from tests.pipeline.test_orchestrator import _ctx


def _by_title(content):
    return {c["title"]: c for c in content["concepts"]}


def test_good_sections_pass_with_a_score(sample_text):
    llm = FakeLLM()
    state: dict = {}
    content = orchestrator.run(_ctx(sample_text, llm, state=state))
    assert llm.calls.count("review") == 3 and llm.calls.count("write") == 3
    for concept in content["concepts"]:
        assert concept["quality"]["reviewed"] and concept["quality"]["score"] == 90
        assert not concept["quality"]["needs_checking"]
    assert {r["action"] for r in state["reviews"].values()} == {"passed"}
    assert orchestrator.quality_score(state) == 90
    assert state["check"]["quality_score"] == 90
    StudyGuideContent.model_validate(content)


def test_low_section_is_rewritten_once_with_the_problems(sample_text):
    llm = FakeLLM(review_scores={"Light reactions": [55, 88]})
    state: dict = {}
    events: list = []
    content = orchestrator.run(_ctx(sample_text, llm, state=state, events=events))
    light = _by_title(content)["Light reactions"]
    assert light["quality"]["score"] == 88 and light["quality"]["rewritten"]
    assert not light["quality"]["needs_checking"]
    assert llm.calls.count("write") == 4 and llm.calls.count("review") == 4
    rewrite_prompt = [p for stage, p in llm.prompts if stage == "write"][-1]
    assert "A reviewer checked an earlier version" in rewrite_prompt
    assert "says something the source does not say" in rewrite_prompt
    report = state["reviews"][light["id"]]
    assert report["action"] == "regenerated" and [a["score"] for a in report["attempts"]] == [55, 88]
    assert ("section_ready", {"stage": "review", "section_id": light["id"], "regenerated": True}) in events


def test_still_low_after_rewrite_is_flagged_for_the_student(sample_text):
    llm = FakeLLM(review_scores={"Chlorophyll": [50, 40]})
    state: dict = {}
    events: list = []
    content = orchestrator.run(_ctx(sample_text, llm, state=state, events=events))
    chlorophyll = _by_title(content)["Chlorophyll"]
    quality = chlorophyll["quality"]
    # The better version (the first) is kept, and flagged.
    assert quality["score"] == 50 and not quality["rewritten"] and quality["needs_checking"]
    assert "needs_checking" in quality["flags"]
    assert quality["problems"] == ["'Chlorophyll' says something the source does not say."]
    assert state["reviews"][chlorophyll["id"]]["action"] == "flagged"
    assert any("could not be fully confirmed" in w for w in content["warnings"])
    flags = [d for t, d in events if t == "quality_flag"]
    assert [f["section_id"] for f in flags] == [chlorophyll["id"]]


def test_reviewer_is_a_separate_model(sample_text):
    writer, reviewer = FakeLLM(), FakeLLM()
    ctx = _ctx(sample_text, writer)
    ctx.reviewer = reviewer
    orchestrator.run(ctx)
    assert "review" not in writer.calls and reviewer.calls == ["review"] * 3


def test_review_can_be_turned_off(sample_text):
    llm = FakeLLM()
    ctx = _ctx(sample_text, llm)
    ctx.settings = Settings(write_concurrency=2, review_enabled=False)
    content = orchestrator.run(ctx)
    assert "review" not in llm.calls
    assert all(c["quality"]["score"] is None for c in content["concepts"])


def test_a_refused_review_leaves_the_section_unreviewed(sample_text):
    class Refuses(FakeLLM):
        def generate(self, *, stage, **kwargs):
            if stage == "review":
                raise LLMError("model_refused", "no")
            return super().generate(stage=stage, **kwargs)

    content = orchestrator.run(_ctx(sample_text, Refuses()))
    assert all("not_reviewed" in c["quality"]["flags"] for c in content["concepts"])


def test_resume_does_not_review_twice(sample_text):
    state: dict = {}
    calls = {"n": 0}

    class FailsOnSecondReview(FakeLLM):
        def generate(self, *, stage, **kwargs):
            if stage == "review":
                calls["n"] += 1
                if calls["n"] == 2:
                    raise LLMError("ai_unavailable", "outage")
            return super().generate(stage=stage, **kwargs)

    ctx = _ctx(sample_text, FailsOnSecondReview(), state=state)
    ctx.settings = Settings(write_concurrency=1)
    try:
        orchestrator.run(ctx)
    except LLMError:
        pass
    finished = len(state["reviews"])
    assert 1 <= finished < 3  # reviews that finished before the failure were saved
    llm = FakeLLM()
    orchestrator.run(_ctx(sample_text, llm, state=state))
    assert llm.calls.count("review") == 3 - finished and "write" not in llm.calls


def test_score_weights_and_caps():
    good = {"accuracy": 90, "grounding": 90, "examples": 90, "clarity": 90, "visuals": None}
    assert review.score({"scores": good, "problems": []}, {}) == 90
    major = {"kind": "inaccurate", "severity": "major", "where": "x", "problem": "p", "fix": "f"}
    assert review.score({"scores": good, "problems": [major]}, {}) == review.FAILING_CAP
    minor_clarity = {**major, "kind": "unclear_for_level"}
    assert review.score({"scores": good, "problems": [minor_clarity]}, {}) == 90
    assert review.score({"scores": good, "problems": []}, {"no_source_reference": True}) == review.FAILING_CAP
    mixed = {"accuracy": 100, "grounding": 100, "examples": 0, "clarity": 0, "visuals": 0}
    assert review.score({"scores": mixed, "problems": []}, {}) == 60
    assert review.score({"scores": {**good, "accuracy": 400}, "problems": []}, {}) == 94


def test_regenerate_section_is_reviewed(sample_text):
    state: dict = {}
    orchestrator.run(_ctx(sample_text, FakeLLM(), state=state))
    llm = FakeLLM(review_scores={"Chlorophyll": [30, 95]})
    meter = TokenMeter(budget=1_000_000)
    ctx = _ctx(sample_text, llm, state=state)
    ctx.meter = meter
    content = orchestrator.regenerate_section(ctx, "c2", "simpler")
    assert llm.calls == ["write", "review", "write", "review"]
    rewrite = [p for stage, p in llm.prompts if stage == "write"][-1]
    assert "simpler" in rewrite and "A reviewer checked" in rewrite
    assert _by_title(content)["Chlorophyll"]["quality"]["score"] == 95
    assert "review" in meter.by_stage
