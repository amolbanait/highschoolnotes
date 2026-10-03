"""AnthropicLLM against a stub SDK client: request shape, retry on bad output, refusals, budget."""

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.llm.client import FALLBACK_BETA, AnthropicLLM, BudgetExceeded, LLMError, TokenMeter, Usage
from app.schemas.study_guide import AssembleOutput

GOOD = '{"overview": "o", "objectives": ["Explain x"], "summary": "s", "review_checklist": ["I can x"]}'


def _message(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(
            input_tokens=100, output_tokens=20, cache_read_input_tokens=50, cache_creation_input_tokens=0
        ),
    )


class StubClient:
    def __init__(self, *messages):
        self.messages_to_return = list(messages)
        self.requests: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.requests.append(kwargs)
        message = self.messages_to_return.pop(0)

        class _Ctx:
            def __enter__(self_inner):
                return SimpleNamespace(get_final_message=lambda: message)

            def __exit__(self_inner, *exc):
                return False

        return _Ctx()


def _llm(*messages, **settings):
    stub = StubClient(*messages)
    return AnthropicLLM(Settings(**settings), client=stub), stub


def test_request_shape():
    llm, stub = _llm(_message(GOOD))
    out, usage = llm.generate(
        stage="assemble", system="SYS", prompt="P", output=AssembleOutput, effort="medium"
    )
    assert out.summary == "s" and usage.calls == 1 and usage.cache_read_input_tokens == 50
    req = stub.requests[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert req["output_config"]["effort"] == "medium"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert req["output_config"]["format"]["schema"]["additionalProperties"] is False
    assert req["betas"] == [FALLBACK_BETA] and req["fallbacks"] == "default"
    assert "thinking" not in req and "temperature" not in req


def test_fallbacks_can_be_turned_off():
    llm, stub = _llm(_message(GOOD), use_fallbacks=False)
    llm.generate(stage="assemble", system="S", prompt="P", output=AssembleOutput, effort="low")
    assert "fallbacks" not in stub.requests[0] and "betas" not in stub.requests[0]


def test_retries_once_with_validation_error():
    llm, stub = _llm(_message('{"overview": "o"}'), _message(GOOD))
    out, usage = llm.generate(stage="assemble", system="S", prompt="P", output=AssembleOutput, effort="low")
    assert out.overview == "o" and usage.calls == 2
    retry_messages = stub.requests[1]["messages"]
    assert [m["role"] for m in retry_messages] == ["user", "assistant", "user"]
    assert "did not match the required schema" in retry_messages[2]["content"]


def test_gives_up_after_two_bad_outputs():
    llm, _ = _llm(_message("{}"), _message("{}"))
    with pytest.raises(LLMError) as exc:
        llm.generate(stage="assemble", system="S", prompt="P", output=AssembleOutput, effort="low")
    assert exc.value.code == "invalid_output"


@pytest.mark.parametrize("stop,code", [("refusal", "model_refused"), ("max_tokens", "output_too_long")])
def test_stop_reasons(stop, code):
    llm, _ = _llm(_message("", stop_reason=stop))
    with pytest.raises(LLMError) as exc:
        llm.generate(stage="assemble", system="S", prompt="P", output=AssembleOutput, effort="low")
    assert exc.value.code == code


def test_token_meter_budget_and_round_trip():
    meter = TokenMeter(budget=1500)
    meter.add("plan", Usage(input_tokens=1000, output_tokens=100, calls=1))
    restored = TokenMeter.from_dict(1500, meter.as_dict())
    assert restored.usage.total == 1100 and restored.by_stage["plan"].calls == 1
    with pytest.raises(BudgetExceeded):
        restored.add("write", Usage(input_tokens=500, calls=1))
