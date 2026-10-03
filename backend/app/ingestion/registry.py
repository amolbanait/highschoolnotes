"""Picks an extractor from the file name and content. New input types register here."""

from app.ingestion.base import ExtractionError, Extractor, ExtractTools, FileExtractor
from app.ingestion.docx import DocxExtractor
from app.ingestion.image import ImageExtractor
from app.ingestion.media import AudioExtractor, VideoExtractor
from app.ingestion.pdf import PdfExtractor
from app.ingestion.text import TextExtractor

# Kinds read from a file on disk (large) rather than from memory.
MEDIA_KINDS = ("audio", "video")

_BY_EXTENSION = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".text": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".mp3": "audio",
    ".m4a": "audio",
    ".wav": "audio",
    ".ogg": "audio",
    ".oga": "audio",
    ".opus": "audio",
    ".flac": "audio",
    ".aac": "audio",
    ".mp4": "video",
    ".m4v": "video",
    ".mov": "video",
    ".webm": "video",
    ".mkv": "video",
}

MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "markdown": "text/markdown",
    "paste": "text/plain",
}

# Media types by extension, so the browser can play the original back at a timestamp.
EXTENSION_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
}

UNSUPPORTED_HINTS = {
    ".doc": "Old .doc Word files are not supported. Save it as .docx and upload again.",
    ".pptx": "PowerPoint files arrive in a later version. Export the slides as PDF for now.",
    ".ppt": "PowerPoint files arrive in a later version. Export the slides as PDF for now.",
    ".heic": "iPhone HEIC photos are not supported. Export the photo as JPEG and upload again.",
    ".heif": "iPhone HEIC photos are not supported. Export the photo as JPEG and upload again.",
    ".gif": "GIF images are not supported. Use PNG or JPEG.",
    ".avi": "AVI videos are not supported. Convert it to MP4 and upload again.",
    ".wmv": "WMV videos are not supported. Convert it to MP4 and upload again.",
}

SUPPORTED_HINT = (
    "Upload a PDF, Word (.docx), text or Markdown file, a photo or scan (PNG, JPEG, WebP), "
    "a recording (MP3, M4A, WAV) or a video (MP4, MOV, WebM)."
)


def extension(filename: str) -> str:
    name = filename.lower()
    return name[name.rfind(".") :] if "." in name else ""


def mime_for(kind: str, filename: str | None) -> str:
    return EXTENSION_MIME.get(extension(filename or "")) or MIME_TYPES.get(kind, "application/octet-stream")


def kind_for_name(filename: str) -> str:
    ext = extension(filename)
    kind = _BY_EXTENSION.get(ext)
    if kind is None:
        raise ExtractionError(
            "unsupported_type", UNSUPPORTED_HINTS.get(ext, SUPPORTED_HINT), {"extension": ext}
        )
    return kind


def detect_kind(filename: str, data: bytes) -> str:
    """data may be just the start of the file: the checks only look at the first bytes."""
    kind = kind_for_name(filename)
    # Check content matches the extension so a renamed file fails clearly.
    if kind == "pdf" and not data.lstrip()[:5].startswith(b"%PDF-"):
        raise ExtractionError("unsupported_type", "This file is named .pdf but is not a PDF.")
    if kind == "docx" and not data.startswith(b"PK"):
        raise ExtractionError("unsupported_type", "This file is named .docx but is not a Word document.")
    if kind == "image" and not _looks_like_image(data):
        raise ExtractionError(
            "unsupported_type", "This file is named like an image but is not a PNG, JPEG or WebP."
        )
    if kind in MEDIA_KINDS and not _looks_like_media(data):
        raise ExtractionError("unsupported_type", "This file is named like a recording but is not one.")
    return kind


def _looks_like_image(data: bytes) -> bool:
    return (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8\xff")
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    )


def _looks_like_media(data: bytes) -> bool:
    """Common audio and video containers. ffprobe checks the rest when the file is processed."""
    head = data[:16]
    return (
        head[4:8] == b"ftyp"  # MP4, M4A, MOV
        or head.startswith(b"ID3")  # MP3 with tags
        or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)  # MP3 or AAC frame
        or (head[:4] == b"RIFF" and head[8:12] == b"WAVE")
        or head.startswith(b"OggS")
        or head.startswith(b"fLaC")
        or head.startswith(b"\x1a\x45\xdf\xa3")  # WebM, MKV
        or head[4:8] in (b"moov", b"wide", b"mdat", b"free")  # old QuickTime
    )


def get_extractor(kind: str, tools: ExtractTools | None = None) -> Extractor:
    if kind == "pdf":
        return PdfExtractor(tools)
    if kind == "image":
        return ImageExtractor(tools)
    if kind == "docx":
        return DocxExtractor()
    if kind == "txt":
        return TextExtractor(markdown=False)
    if kind in ("markdown", "paste"):
        # Pasted text often carries Markdown headings (copied from notes apps and web pages).
        return TextExtractor(markdown=True)
    raise ExtractionError("unsupported_type", f"No extractor for {kind}.")


def get_file_extractor(kind: str, tools: ExtractTools) -> FileExtractor:
    if kind == "audio":
        return AudioExtractor(tools)
    if kind == "video":
        return VideoExtractor(tools)
    raise ExtractionError("unsupported_type", f"No extractor for {kind}.")
