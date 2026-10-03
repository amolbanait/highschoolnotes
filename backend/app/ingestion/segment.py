"""Clean and segment: turn extracted blocks into numbered segments of about 500 tokens.

Segments break on headings and never cross a page, so every citation resolves to one page.
Refs are p12-s3 (page 12, third segment on it) for paged sources and s7 for flowing text.
"""

import math
import re

from app.ingestion.base import Block, ExtractResult, Segment

TARGET_TOKENS = 500
MAX_TOKENS = 750
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def word_count(text: str) -> int:
    return len(text.split())


def segment(result: ExtractResult) -> list[Segment]:
    segments: list[Segment] = []
    heading_path: list[tuple[int, str]] = []
    current: list[str] = []
    current_page: int | None = None
    page_offsets: dict[int | None, int] = {}  # running char offset per page (or None for flowing text)
    per_page_count: dict[int | None, int] = {}

    def flush() -> None:
        nonlocal current
        text = "\n".join(current).strip()
        current = []
        if not text:
            return
        page = current_page if result.paged else None
        start = page_offsets.get(page, 0)
        end = start + len(text)
        page_offsets[page] = end + 1
        per_page_count[page] = per_page_count.get(page, 0) + 1
        section = heading_path[-1][1] if heading_path else None
        if result.paged:
            ref = f"p{page}-s{per_page_count[page]}"
            locator = {"kind": "page", "page": page, "section": section, "char_start": start, "char_end": end}
        else:
            ref = f"s{per_page_count[page]}"
            locator = {"kind": "text", "section": section, "char_start": start, "char_end": end}
        segments.append(
            Segment(
                ordinal=len(segments),
                ref=ref,
                locator=locator,
                heading_path=[h for _, h in heading_path],
                text=text,
                token_count=estimate_tokens(text),
            )
        )

    # Headings are held until body text follows, so no segment is only a heading.
    has_body = False
    for block in _clean(result.blocks):
        if result.paged and block.page != current_page:
            if has_body:
                flush()
                has_body = False
            current_page = block.page
        if block.kind == "heading":
            if has_body:
                flush()
                has_body = False
            level = block.heading_level or 2
            heading_path = [(lvl, h) for lvl, h in heading_path if lvl < level] + [(level, block.text)]
            current.append(block.text)
            continue
        for piece in _split_long(block.text):
            if has_body and estimate_tokens("\n".join(current + [piece])) > TARGET_TOKENS:
                flush()
            current.append(piece)
            has_body = True
    flush()
    return segments


def _clean(blocks: list[Block]) -> list[Block]:
    cleaned = []
    for block in blocks:
        text = re.sub(r"[ \t ]+", " ", block.text).strip()
        if not text:
            continue
        cleaned.append(Block(text=text, kind=block.kind, page=block.page, heading_level=block.heading_level))
    return cleaned


def _split_long(text: str) -> list[str]:
    if estimate_tokens(text) <= MAX_TOKENS:
        return [text]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(text):
        candidate = f"{current} {sentence}".strip()
        if current and estimate_tokens(candidate) > TARGET_TOKENS:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    # A single sentence longer than the limit (rare: tables, lists without punctuation) is cut by length.
    out: list[str] = []
    for piece in pieces:
        while estimate_tokens(piece) > MAX_TOKENS:
            cut = piece.rfind(" ", 0, TARGET_TOKENS * 4)
            cut = cut if cut > 0 else TARGET_TOKENS * 4
            out.append(piece[:cut].strip())
            piece = piece[cut:].strip()
        if piece:
            out.append(piece)
    return out
