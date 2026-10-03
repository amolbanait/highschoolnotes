"""Photos and scans of a single page (PNG, JPEG, WebP), read by Claude's vision."""

from app.ingestion.base import ExtractResult, ExtractTools
from app.ingestion.vision import prepare_image, read_pages, require_vision


class ImageExtractor:
    kinds = ("image",)

    def __init__(self, tools: ExtractTools | None = None):
        self.tools = tools

    def extract(self, data: bytes) -> ExtractResult:
        require_vision(self.tools)
        assert self.tools is not None
        blocks = read_pages(self.tools, {1: prepare_image(data)})[1]
        return ExtractResult(
            blocks=blocks,
            page_count=1,
            paged=True,
            warnings=[ocr_warning([1])],
            usage=self.tools.usage.as_dict() if self.tools.usage else {},
        )


def ocr_warning(pages: list[int]) -> dict:
    return {
        "code": "ocr_pages",
        "message": (
            "This was read from an image. Check names, numbers and formulas against the original."
            if pages == [1]
            else f"{len(pages)} page(s) were read from images. Check names, numbers and formulas "
            "against the original."
        ),
        "pages": pages,
    }
