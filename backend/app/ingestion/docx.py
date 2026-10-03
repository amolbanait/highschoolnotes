"""Word documents via python-docx. Paragraphs, headings, list items and tables, in document order."""

import io
import zipfile

import docx
from docx.document import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ingestion.base import Block, ExtractionError, ExtractResult


class DocxExtractor:
    kinds = ("docx",)

    def extract(self, data: bytes) -> ExtractResult:
        try:
            document = docx.Document(io.BytesIO(data))
        except (zipfile.BadZipFile, KeyError, ValueError) as exc:
            raise ExtractionError(
                "unreadable_docx", "This Word file could not be opened. It may be damaged."
            ) from exc

        blocks: list[Block] = []
        for item in _iter_block_items(document):
            if isinstance(item, Paragraph):
                block = _paragraph_block(item)
                if block:
                    blocks.append(block)
            else:
                rows = []
                for row in item.rows:
                    cells = [" ".join(c.text.split()) for c in row.cells]
                    # Merged cells repeat; keep each distinct cell once per row.
                    deduped = [c for i, c in enumerate(cells) if c and (i == 0 or c != cells[i - 1])]
                    if deduped:
                        rows.append(" | ".join(deduped))
                if rows:
                    blocks.append(Block(text="\n".join(rows), kind="table"))
        return ExtractResult(blocks=blocks, paged=False)


def _iter_block_items(document: DocxDocument):
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            yield Paragraph(child, document)
        elif tag == "tbl":
            yield Table(child, document)


def _paragraph_block(paragraph: Paragraph) -> Block | None:
    text = " ".join(paragraph.text.split())
    if not text:
        return None
    style = (paragraph.style.name if paragraph.style is not None else "") or ""
    lowered = style.lower()
    if lowered == "title":
        return Block(text=text, kind="heading", heading_level=1)
    if lowered.startswith("heading"):
        digits = "".join(ch for ch in style if ch.isdigit())
        return Block(text=text, kind="heading", heading_level=int(digits) if digits else 2)
    if "list" in lowered or paragraph._p.pPr is not None and paragraph._p.pPr.numPr is not None:
        return Block(text=f"- {text}", kind="list_item")
    return Block(text=text, kind="paragraph")
