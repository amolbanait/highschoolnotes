"""Plain text, Markdown and pasted text."""

import re

from app.ingestion.base import Block, ExtractionError, ExtractResult

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def decode_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "\x00" not in text:
            return text
    raise ExtractionError("unreadable_text", "This file is not readable text.")


class TextExtractor:
    kinds = ("txt", "markdown", "paste")

    def __init__(self, markdown: bool = False):
        self.markdown = markdown

    def extract(self, data: bytes) -> ExtractResult:
        return self.extract_text(decode_text(data))

    def extract_text(self, text: str) -> ExtractResult:
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        blocks: list[Block] = []
        para: list[str] = []
        in_code = False

        def flush() -> None:
            if para:
                blocks.append(_block(para, in_code))
                para.clear()

        for line in lines:
            if self.markdown and line.lstrip().startswith("```"):
                flush()
                in_code = not in_code
                continue
            if not line.strip() and not in_code:
                flush()
                continue
            heading = _MD_HEADING.match(line) if self.markdown and not in_code else None
            if heading:
                flush()
                blocks.append(
                    Block(text=heading.group(2), kind="heading", heading_level=len(heading.group(1)))
                )
            else:
                para.append(line.rstrip())
        flush()
        return ExtractResult(blocks=blocks, paged=False)


def _block(lines: list[str], code: bool) -> Block:
    if code:
        return Block(text="\n".join(lines), kind="code")
    lines = [ln for ln in lines if ln.strip()]
    if all(_LIST_ITEM.match(ln) for ln in lines):
        return Block(text="\n".join(ln.strip() for ln in lines), kind="list_item")
    return Block(text=" ".join(ln.strip() for ln in lines), kind="paragraph")
