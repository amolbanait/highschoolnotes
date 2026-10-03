"""Model calls behind one small interface, so the pipeline is testable with recorded responses.

AnthropicLLM streams each request (outputs can be long), asks for structured output against a
Pydantic model, retries once with the validation error if the output does not fit, and records
token usage against the guide's budget.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

import anthropic
from anthropic import transform_schema
from pydantic import BaseModel, ValidationError

from app.core.config import Settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class BudgetExceeded(LLMError):
    def __init__(self, used: int, budget: int):
        super().__init__(
            "token_budget_exceeded",
            f"This material needs more processing than one guide allows ({used:,} of {budget:,} tokens). "
            "Try splitting it into smaller parts.",
        )


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    calls: int = 0

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_input_tokens
            + self.cache_creation_input_tokens
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "calls": self.calls,
        }


@dataclass
class TokenMeter:
    """Thread-safe running total for one guide; raises once the budget is spent."""

    budget: int
    usage: Usage = field(default_factory=Usage)
    by_stage: dict[str, Usage] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def from_dict(cls, budget: int, data: dict | None) -> "TokenMeter":
        meter = cls(budget=budget)
        if data:
            meter.usage = Usage(
                **{k: v for k, v in data.get("total", {}).items() if k in Usage.__annotations__}
            )
            for stage, values in data.get("by_stage", {}).items():
                meter.by_stage[stage] = Usage(
                    **{k: v for k, v in values.items() if k in Usage.__annotations__}
                )
        return meter

    def check(self) -> None:
        if self.usage.total > self.budget:
            raise BudgetExceeded(self.usage.total, self.budget)

    def add(self, stage: str, usage: Usage) -> None:
        with self._lock:
            stage_usage = self.by_stage.setdefault(stage, Usage())
            for target in (self.usage, stage_usage):
                target.input_tokens += usage.input_tokens
                target.output_tokens += usage.output_tokens
                target.cache_read_input_tokens += usage.cache_read_input_tokens
                target.cache_creation_input_tokens += usage.cache_creation_input_tokens
                target.calls += usage.calls
        self.check()

    def as_dict(self) -> dict:
        return {
            "total": self.usage.as_dict(),
            "by_stage": {k: v.as_dict() for k, v in self.by_stage.items()},
            "budget": self.budget,
        }


class LLM(Protocol):
    model: str

    def generate(
        self, *, stage: str, system: str, prompt: str, output: type[T], effort: str
    ) -> tuple[T, Usage]: ...


class AnthropicLLM:
    def __init__(
        self, settings: Settings, client: anthropic.Anthropic | None = None, model: str | None = None
    ):
        self.settings = settings
        self.model = model or settings.writer_model
        self.client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=3)

    def generate(
        self, *, stage: str, system: str, prompt: str, output: type[T], effort: str
    ) -> tuple[T, Usage]:
        messages: list[dict] = [{"role": "user", "content": prompt}]
        usage = Usage()
        for attempt in range(2):
            message = self._call(system, messages, output, effort)
            _add_usage(usage, message.usage)
            if message.stop_reason == "refusal":
                raise LLMError("model_refused", "The AI declined to process part of this material.")
            if message.stop_reason == "max_tokens":
                raise LLMError("output_too_long", f"The {stage} step produced more output than allowed.")
            text = "".join(b.text for b in message.content if b.type == "text")
            try:
                return output.model_validate_json(text), usage
            except ValidationError as exc:
                log.warning(
                    "stage %s returned invalid output (attempt %d): %s", stage, attempt + 1, exc.error_count()
                )
                messages = [
                    *messages[:1],
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": f"That output did not match the required schema:\n{exc}\nReturn the corrected JSON.",
                    },
                ]
        raise LLMError("invalid_output", f"The {stage} step returned output that could not be used.")

    def _call(self, system: str, messages: list[dict], output: type[T], effort: str):
        extra: dict = {}
        if self.settings.use_fallbacks:
            extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        try:
            with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=64000,
                # The system prompt is identical across every call of a stage, so cache it.
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
                output_config={
                    "effort": effort,
                    "format": {"type": "json_schema", "schema": transform_schema(output)},
                },
                **extra,
            ) as stream:
                return stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise LLMError("ai_not_configured", "The AI service key is missing or invalid.") from exc
        except TypeError as exc:
            # The SDK raises TypeError before sending when no credentials can be found at all.
            if "authentication" not in str(exc).lower():
                raise
            raise LLMError("ai_not_configured", "The AI service key is not set up.") from exc
        except anthropic.BadRequestError as exc:
            raise LLMError("ai_bad_request", f"The AI service rejected the request: {exc.message}") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("ai_busy", "The AI service is busy. The guide will be retried.") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(
                "ai_unavailable", f"The AI service returned an error ({exc.status_code})."
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("ai_unreachable", "Could not reach the AI service.") from exc


def _add_usage(total: Usage, usage) -> None:
    total.calls += 1
    total.input_tokens += getattr(usage, "input_tokens", 0) or 0
    total.output_tokens += getattr(usage, "output_tokens", 0) or 0
    total.cache_read_input_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
    total.cache_creation_input_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
