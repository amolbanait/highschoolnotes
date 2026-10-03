"""Extractor interface. Every input type becomes text blocks with a location.

Extractors only read. Cleaning and segmenting happen in segment.py, so a new input type
(OCR, audio, slides) is a new extractor and nothing else changes.

Documents arrive as bytes. Recordings can be large, so media extractors read from a file path.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.ingestion.transcribe import Transcriber
    from app.llm.client import LLM, Usage


class ExtractionError(Exception):
    """A problem the student can act on (bad file, scanned PDF, too long)."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass
class Block:
    text: str
    kind: str = "paragraph"  # heading, paragraph, list_item, table, speech, on_screen
    page: int | None = None  # 1-based page for paged sources
    heading_level: int | None = None  # set when kind == "heading"
    start: float | None = None  # seconds into a recording, for timed sources
    end: float | None = None


@dataclass
class ExtractResult:
    blocks: list[Block]
    page_count: int | None = None
    paged: bool = False
    warnings: list[dict[str, Any]] = field(default_factory=list)
    timed: bool = False  # audio or video: blocks carry start and end times
    duration: float | None = None  # seconds
    media: str | None = None  # "audio" or "video", so the web app can pick a player
    usage: dict[str, int] = field(default_factory=dict)  # model tokens spent reading images


@dataclass
class ExtractTools:
    """What extractors beyond plain documents need. Any of them may be missing (tests, the CLI)."""

    settings: "Settings"
    vision: "LLM | None" = None  # reads scanned pages, photos and video frames
    transcriber: "Transcriber | None" = None
    progress: Callable[[str], None] = lambda message: None  # also keeps the job's lock alive
    usage: "Usage | None" = None

    def add_usage(self, usage: "Usage") -> None:
        from app.llm.client import Usage

        if self.usage is None:
            self.usage = Usage()
        self.usage.input_tokens += usage.input_tokens
        self.usage.output_tokens += usage.output_tokens
        self.usage.cache_read_input_tokens += usage.cache_read_input_tokens
        self.usage.cache_creation_input_tokens += usage.cache_creation_input_tokens
        self.usage.calls += usage.calls


@dataclass
class Segment:
    ordinal: int
    ref: str
    locator: dict[str, Any]
    heading_path: list[str]
    text: str
    token_count: int


class Extractor(Protocol):
    kinds: tuple[str, ...]

    def extract(self, data: bytes) -> ExtractResult: ...


class FileExtractor(Protocol):
    """Reads from disk instead of memory: recordings can be hundreds of megabytes."""

    kinds: tuple[str, ...]

    def extract_file(self, path: Path) -> ExtractResult: ...
