"""Builds small PDF and DOCX files in memory, so tests need no binary fixtures."""

import io

import docx
import pymupdf


def make_pdf(pages: list[list[tuple[str, float]]], header: str | None = None, footer: bool = False) -> bytes:
    """pages: per page, a list of (text, font size). Larger sizes become headings."""
    doc = pymupdf.open()
    for number, blocks in enumerate(pages, start=1):
        page = doc.new_page()
        y = 50.0
        if header:
            page.insert_text((72, 30), header, fontsize=9)
        for text, size in blocks:
            box = pymupdf.Rect(72, y, 540, y + 400)
            used = page.insert_textbox(box, text, fontsize=size)
            y += (400 - used) + size * 1.5
        if footer:
            page.insert_text((300, 800), str(number), fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


def make_docx() -> bytes:
    document = docx.Document()
    document.add_heading("Cell Biology", level=1)
    document.add_paragraph("Cells are the basic unit of life. Every living thing is made of cells.")
    document.add_heading("Organelles", level=2)
    document.add_paragraph("The nucleus holds DNA.", style="List Bullet")
    document.add_paragraph("Mitochondria release energy.", style="List Bullet")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Organelle"
    table.cell(0, 1).text = "Job"
    table.cell(1, 0).text = "Ribosome"
    table.cell(1, 1).text = "Makes proteins"
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
