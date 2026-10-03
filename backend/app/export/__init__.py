"""Exports of a finished guide: PDF, Word, Markdown and a standalone HTML page."""

from app.export.common import ExportInfo, filename

FORMATS = {
    "pdf": ("application/pdf", "pdf"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "md": ("text/markdown; charset=utf-8", "md"),
    "html": ("text/html; charset=utf-8", "html"),
}


def render(content: dict, fmt: str, info: ExportInfo) -> bytes:
    if fmt == "pdf":
        from app.export.pdf import to_pdf

        return to_pdf(content, info)
    if fmt == "docx":
        from app.export.docx import to_docx

        return to_docx(content, info)
    if fmt == "md":
        from app.export.markdown import to_markdown

        return to_markdown(content, info).encode()
    if fmt == "html":
        from app.export.html import to_html

        return to_html(content, info).encode()
    raise ValueError(f"unknown export format {fmt}")


__all__ = ["FORMATS", "ExportInfo", "filename", "render"]
