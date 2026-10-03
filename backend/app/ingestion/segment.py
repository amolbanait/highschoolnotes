"""Clean and segment: turn extracted blocks into numbered segments of about 500 tokens.

Segments break on headings and never cross a page, so every citation resolves to one page.
Refs are p12-s3 (page 12, third segment on it) for paged sources and s7 for flowing text.

Recordings are cut into stretches of speech of at most two minutes, so a citation lands close to
the moment it refers to. Refs carry the start time: t14m32s is speech from 14:32, v14m32s is what
was on screen from 14:32, and t1h02m05s is past the hour.
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


MAX_SPEECH_SECONDS = 120


def segment(result: ExtractResult) -> list[Segment]:
    if result.timed:
        return segment_timed(result)
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
        cleaned.append(
            Block(
                text=text,
                kind=block.kind,
                page=block.page,
                heading_level=block.heading_level,
                start=block.start,
                end=block.end,
            )
        )
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


def clock(seconds: float) -> str:
    """14:32, or 1:02:05 past the hour."""
    total = int(seconds)
    h, m, s = total // 3600, total % 3600 // 60, total % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def time_ref(prefix: str, seconds: float) -> str:
    total = int(seconds)
    h, m, s = total // 3600, total % 3600 // 60, total % 60
    return f"{prefix}{h}h{m:02d}m{s:02d}s" if h else f"{prefix}{m}m{s:02d}s"


def segment_timed(result: ExtractResult) -> list[Segment]:
    """Speech in stretches of about 500 tokens or two minutes; each on-screen picture on its own.

    A slide's title becomes the section for the speech that follows it, so the outline of a
    lecture follows its slides.
    """
    segments: list[Segment] = []
    used: set[str] = set()
    section: str | None = None
    pending: list[Block] = []

    def add(prefix: str, blocks: list[Block], on_screen: bool) -> None:
        text = (
            "\n".join(b.text for b in blocks).strip()
            if on_screen
            else " ".join(b.text for b in blocks).strip()
        )
        if not text:
            return
        start = blocks[0].start or 0.0
        end = max((b.end or b.start or 0.0) for b in blocks)
        ref = base = time_ref(prefix, start)
        n = 2
        while ref in used:
            ref = f"{base}-{n}"
            n += 1
        used.add(ref)
        locator = {
            "kind": "time",
            "start": round(start, 2),
            "end": round(end, 2),
            "media": result.media,
            "on_screen": on_screen,
            "section": section,
        }
        segments.append(
            Segment(
                ordinal=len(segments),
                ref=ref,
                locator=locator,
                heading_path=[section] if section else [],
                text=text,
                token_count=estimate_tokens(text),
            )
        )

    def flush() -> None:
        nonlocal pending
        if pending:
            add("t", pending, on_screen=False)
        pending = []

    for block in _clean(result.blocks):
        if block.kind == "on_screen":
            flush()
            title = block.text.split("\n", 1)[0]
            if len(title) <= 120 and not title.startswith("["):
                section = title
            add("v", [block], on_screen=True)
            continue
        if pending:
            span = (block.end or block.start or 0.0) - (pending[0].start or 0.0)
            tokens = estimate_tokens(" ".join(b.text for b in pending + [block]))
            if span > MAX_SPEECH_SECONDS or tokens > TARGET_TOKENS:
                flush()
        pending.append(block)
    flush()
    return segments
