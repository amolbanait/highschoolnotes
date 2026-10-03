"""Make a guide from a file without the database, to try prompts and measure cost on real material.

    python -m app.cli path/to/chapter.pdf --level high_school --out guide.json

Needs ANTHROPIC_API_KEY (or HSN_ANTHROPIC_API_KEY). Prints progress, token usage and an
estimated cost; the guide JSON is written to --out.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from app.core.config import get_settings
from app.ingestion.registry import detect_kind, get_extractor
from app.ingestion.segment import segment, word_count
from app.llm.client import AnthropicLLM, TokenMeter
from app.pipeline import orchestrator
from app.schemas.study_guide import LEVELS

# USD per million tokens, for the estimate only: (input, output, cache read, cache write).
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-4-5": (1.00, 5.00, 0.10, 1.25),
}


def estimate_cost(model: str, usage: dict) -> float | None:
    price = PRICES.get(model)
    if price is None:
        return None
    return (
        usage["input_tokens"] * price[0]
        + usage["output_tokens"] * price[1]
        + usage["cache_read_input_tokens"] * price[2]
        + usage["cache_creation_input_tokens"] * price[3]
    ) / 1_000_000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", type=Path)
    parser.add_argument("--level", default="high_school", choices=LEVELS)
    parser.add_argument("--out", type=Path, default=Path("guide.json"))
    args = parser.parse_args(argv)

    settings = get_settings()
    data = args.file.read_bytes()
    kind = detect_kind(args.file.name, data)
    segments = segment(get_extractor(kind).extract(data))
    words = sum(word_count(s.text) for s in segments)
    print(f"{args.file.name}: {len(segments)} segments, {words:,} words", file=sys.stderr)

    started = time.monotonic()

    def emit(type_: str, payload: dict) -> None:
        detail = payload.get("stage") or payload.get("section_id") or ""
        print(f"[{time.monotonic() - started:6.1f}s] {type_} {detail}", file=sys.stderr)

    llm = AnthropicLLM(settings)
    ctx = orchestrator.PipelineContext(
        segments=[{"ref": s.ref, "text": s.text, "heading_path": s.heading_path} for s in segments],
        level=args.level,
        llm=llm,
        meter=TokenMeter(budget=settings.guide_token_budget),
        settings=settings,
        state={},
        save=lambda stage: None,
        emit=emit,
    )
    content = orchestrator.run(ctx)
    args.out.write_text(json.dumps(content, indent=2, ensure_ascii=False))

    usage = ctx.meter.as_dict()
    print(json.dumps(usage, indent=2), file=sys.stderr)
    cost = estimate_cost(llm.model, usage["total"])
    if cost is not None:
        print(f"Estimated cost: ${cost:.3f} with {llm.model}", file=sys.stderr)
    print(f"Wrote {args.out} in {time.monotonic() - started:.0f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
