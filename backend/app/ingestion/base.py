"""Extractor interface. Every input type becomes text blocks with a location.

Extractors only read. Cleaning and segmenting happen in segment.py, so a new input type
(OCR, audio, slides) is a new extractor and nothing else changes.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


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
    kind: str = "paragraph"  # heading, paragraph, list_item, table
    page: int | None = None  # 1-based page for paged sources
    heading_level: int | None = None  # set when kind == "heading"


@dataclass
class ExtractResult:
    blocks: list[Block]
    page_count: int | None = None
    paged: bool = False
    warnings: list[dict[str, Any]] = field(default_factory=list)


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
