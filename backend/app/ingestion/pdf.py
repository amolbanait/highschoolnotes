"""PDFs via PyMuPDF. Pages with no selectable text (scans) are rendered and read by Claude's vision."""

import re
import statistics
from collections import Counter

import pymupdf as fitz

from app.ingestion.base import Block, ExtractionError, ExtractResult, ExtractTools
from app.ingestion.image import ocr_warning
from app.ingestion.vision import MAX_EDGE, read_pages

_PAGE_NUMBER = re.compile(r"^\s*(?:page\s*)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?\s*$", re.IGNORECASE)
_SCANNED_PAGE_CHARS = 25


class PdfExtractor:
    kinds = ("pdf",)

    def __init__(self, tools: ExtractTools | None = None):
        self.tools = tools

    @property
    def can_ocr(self) -> bool:
        return bool(self.tools and self.tools.vision and self.tools.settings.vision_enabled)

    def extract(self, data: bytes) -> ExtractResult:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception as exc:  # PyMuPDF raises several types for corrupt files
            raise ExtractionError(
                "unreadable_pdf", "This PDF could not be opened. It may be damaged."
            ) from exc
        if doc.needs_pass:
            raise ExtractionError(
                "encrypted_pdf", "This PDF is password protected. Remove the password and try again."
            )

        pages: list[list[tuple[str, float]]] = []  # per page: (text, font size)
        sizes: list[float] = []
        for page in doc:
            page_blocks: list[tuple[str, float]] = []
            for block in page.get_text("dict", sort=True)["blocks"]:
                if block.get("type") != 0:
                    continue
                text, size = _block_text(block)
                if text:
                    page_blocks.append((text, size))
                    sizes.extend([size] * max(1, len(text) // 40))
            pages.append(page_blocks)
        page_count = len(pages)

        scanned = [
            i + 1 for i, blocks in enumerate(pages) if sum(len(t) for t, _ in blocks) < _SCANNED_PAGE_CHARS
        ]
        ocr_blocks: dict[int, list[Block]] = {}
        if scanned and self.can_ocr:
            assert self.tools is not None
            max_pages = self.tools.settings.max_pages
            if page_count > max_pages:
                doc.close()
                raise ExtractionError(
                    "source_too_long",
                    f"This file has {page_count} pages. The limit is {max_pages} pages per guide; "
                    "split it into parts and upload each one.",
                )
            # Blank pages (no picture, no drawing) are not worth a model call.
            images = {
                n: _render(doc[n - 1])
                for n in scanned
                if doc[n - 1].get_images() or doc[n - 1].get_drawings()
            }
            doc.close()
            ocr_blocks = read_pages(self.tools, images) if images else {}
        else:
            doc.close()
        if not ocr_blocks and page_count and len(scanned) > page_count / 2:
            raise ExtractionError(
                "scanned_document",
                "This looks like a scanned document with no selectable text, and reading scans is turned off "
                "on this server. Upload a text-based PDF or a Word file instead."
                if not self.can_ocr
                else "No readable text was found in this PDF.",
                {"scanned_pages": scanned},
            )

        repeated = _repeated_edges(pages)
        body_size = statistics.median(sizes) if sizes else 11.0
        heading_sizes = sorted(
            {round(s) for _, s in (b for p in pages for b in p) if s >= body_size * 1.15}, reverse=True
        )

        blocks: list[Block] = []
        for page_no, page_blocks in enumerate(pages, start=1):
            if page_no in ocr_blocks:
                blocks.extend(ocr_blocks[page_no])
                continue
            for index, (text, size) in enumerate(page_blocks):
                edge = index == 0 or index == len(page_blocks) - 1
                if _PAGE_NUMBER.match(text) or (edge and _edge_key(text) in repeated):
                    continue
                if size >= body_size * 1.15 and len(text) <= 120 and "\n" not in text:
                    level = (
                        min(heading_sizes.index(round(size)) + 1, 6) if round(size) in heading_sizes else 3
                    )
                    blocks.append(Block(text=text, kind="heading", page=page_no, heading_level=level))
                else:
                    blocks.append(Block(text=text, kind="paragraph", page=page_no))

        warnings = []
        if ocr_blocks:
            warnings.append(ocr_warning(sorted(ocr_blocks)))
        elif scanned:
            warnings.append(
                {
                    "code": "scanned_pages",
                    "message": f"{len(scanned)} page(s) had no selectable text and were skipped.",
                    "pages": scanned,
                }
            )
        usage = self.tools.usage.as_dict() if self.tools and self.tools.usage else {}
        return ExtractResult(blocks=blocks, page_count=page_count, paged=True, warnings=warnings, usage=usage)


def _render(page) -> bytes:
    """The page as a PNG whose longest edge is about MAX_EDGE pixels."""
    longest = max(page.rect.width, page.rect.height) or 1
    zoom = min(MAX_EDGE / longest, 4.0)
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes("png")


def _block_text(block: dict) -> tuple[str, float]:
    lines: list[str] = []
    span_sizes: list[float] = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        text = "".join(s.get("text", "") for s in spans).strip()
        if text:
            lines.append(text)
            span_sizes.extend(s.get("size", 0.0) for s in spans if s.get("text", "").strip())
    text = ""
    for line in lines:
        if text.endswith("-") and line[:1].islower():
            text = text[:-1] + line  # re-join a word hyphenated across lines
        else:
            text = f"{text} {line}" if text else line
    return text.strip(), (max(span_sizes) if span_sizes else 0.0)


def _edge_key(text: str) -> str:
    return re.sub(r"\d+", "#", text.strip().lower())


def _repeated_edges(pages: list[list[tuple[str, float]]]) -> set[str]:
    """Running headers and footers: first or last block text repeated on most pages."""
    if len(pages) < 3:
        return set()
    counts: Counter[str] = Counter()
    for blocks in pages:
        if not blocks:
            continue
        edges = {_edge_key(blocks[0][0]), _edge_key(blocks[-1][0])}
        counts.update(e for e in edges if len(e) <= 120)
    return {key for key, n in counts.items() if n >= max(3, len(pages) // 2)}
