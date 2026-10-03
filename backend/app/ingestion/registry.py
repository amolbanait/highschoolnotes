"""Picks an extractor from the file name and content. New input types register here."""

from app.ingestion.base import ExtractionError, Extractor
from app.ingestion.docx import DocxExtractor
from app.ingestion.pdf import PdfExtractor
from app.ingestion.text import TextExtractor

_BY_EXTENSION = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".text": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
}

MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "markdown": "text/markdown",
    "paste": "text/plain",
}

UNSUPPORTED_HINTS = {
    ".doc": "Old .doc Word files are not supported. Save it as .docx and upload again.",
    ".pptx": "PowerPoint files arrive in a later version. Export the slides as PDF for now.",
    ".ppt": "PowerPoint files arrive in a later version. Export the slides as PDF for now.",
    ".png": "Images and scans arrive in a later version.",
    ".jpg": "Images and scans arrive in a later version.",
    ".jpeg": "Images and scans arrive in a later version.",
}


def detect_kind(filename: str, data: bytes) -> str:
    name = filename.lower()
    ext = name[name.rfind(".") :] if "." in name else ""
    kind = _BY_EXTENSION.get(ext)
    if kind is None:
        hint = UNSUPPORTED_HINTS.get(ext, "Upload a PDF, Word (.docx), text or Markdown file.")
        raise ExtractionError("unsupported_type", hint, {"extension": ext})
    # Check content matches the extension so a renamed file fails clearly.
    if kind == "pdf" and not data.lstrip()[:5].startswith(b"%PDF-"):
        raise ExtractionError("unsupported_type", "This file is named .pdf but is not a PDF.")
    if kind == "docx" and not data.startswith(b"PK"):
        raise ExtractionError("unsupported_type", "This file is named .docx but is not a Word document.")
    return kind


def get_extractor(kind: str) -> Extractor:
    if kind == "pdf":
        return PdfExtractor()
    if kind == "docx":
        return DocxExtractor()
    if kind == "txt":
        return TextExtractor(markdown=False)
    if kind in ("markdown", "paste"):
        # Pasted text often carries Markdown headings (copied from notes apps and web pages).
        return TextExtractor(markdown=True)
    raise ExtractionError("unsupported_type", f"No extractor for {kind}.")
