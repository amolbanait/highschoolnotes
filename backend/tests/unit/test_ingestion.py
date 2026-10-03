import pytest

from app.ingestion.base import ExtractionError
from app.ingestion.registry import detect_kind, get_extractor
from app.ingestion.segment import MAX_TOKENS, estimate_tokens, segment
from app.ingestion.text import TextExtractor
from tests.docs import make_docx, make_pdf

LOREM = "The mitochondria is the powerhouse of the cell. " * 20


def test_markdown_segments_by_heading(sample_text):
    result = TextExtractor(markdown=True).extract(sample_text.encode())
    segs = segment(result)
    assert [s.ref for s in segs] == ["s1", "s2", "s3"]
    # The title heading is held with the first section rather than becoming its own segment.
    assert segs[0].text.startswith("Photosynthesis\nWhat plants need\nPlants make")
    assert segs[1].heading_path == ["Photosynthesis", "Chlorophyll"]
    assert segs[1].locator == {
        "kind": "text",
        "section": "Chlorophyll",
        "char_start": segs[1].locator["char_start"],
        "char_end": segs[1].locator["char_end"],
    }
    assert segs[0].locator["char_end"] < segs[1].locator["char_start"]


def test_plain_text_keeps_hash_lines_as_text():
    result = TextExtractor(markdown=False).extract(b"# not a heading\n\nBody text here.")
    assert [b.kind for b in result.blocks] == ["paragraph", "paragraph"]


def test_long_text_is_split_near_target_size():
    text = "\n\n".join([LOREM] * 12)
    segs = segment(TextExtractor().extract(text.encode()))
    assert len(segs) > 1
    assert all(s.token_count <= MAX_TOKENS + 50 for s in segs)
    assert "".join(s.text for s in segs).count("powerhouse") == 240


def test_one_giant_sentence_is_cut():
    giant = "word " * 5000
    segs = segment(TextExtractor().extract(giant.encode()))
    assert all(estimate_tokens(s.text) <= MAX_TOKENS for s in segs)


def test_pdf_pages_headings_and_running_headers_removed():
    pages = [
        [("Chapter 2: Photosynthesis", 20), ("Plants make food from light. " * 5, 11)],
        [("Chlorophyll", 16), ("Chlorophyll is green. " * 5, 11)],
        [("Light energy splits water. " * 5, 11)],
    ]
    data = make_pdf(pages, header="Biology Grade 10 - Unit 3", footer=True)
    result = get_extractor("pdf").extract(data)
    assert result.page_count == 3 and result.paged
    texts = [b.text for b in result.blocks]
    assert not any("Biology Grade 10" in t for t in texts), "running header must be removed"
    assert not any(t.strip().isdigit() for t in texts), "page numbers must be removed"
    headings = [b for b in result.blocks if b.kind == "heading"]
    assert [h.text for h in headings] == ["Chapter 2: Photosynthesis", "Chlorophyll"]
    segs = segment(result)
    assert [s.ref for s in segs] == ["p1-s1", "p2-s1", "p3-s1"]
    assert segs[1].locator["page"] == 2 and segs[1].locator["section"] == "Chlorophyll"
    assert segs[2].heading_path == ["Chapter 2: Photosynthesis", "Chlorophyll"]


def test_scanned_pdf_is_rejected_clearly():
    data = make_pdf([[], [], [("x", 11)]])
    with pytest.raises(ExtractionError) as exc:
        get_extractor("pdf").extract(data)
    assert exc.value.code == "scanned_document"


def test_partly_scanned_pdf_warns():
    data = make_pdf([[("Real text on this page. " * 4, 11)], [("More real text here. " * 4, 11)], []])
    result = get_extractor("pdf").extract(data)
    assert result.warnings[0]["code"] == "scanned_pages"
    assert result.warnings[0]["pages"] == [3]


def test_docx_headings_lists_and_tables():
    result = get_extractor("docx").extract(make_docx())
    kinds = [(b.kind, b.text) for b in result.blocks]
    assert ("heading", "Cell Biology") in kinds
    assert ("list_item", "- The nucleus holds DNA.") in kinds
    assert ("table", "Organelle | Job\nRibosome | Makes proteins") in kinds
    segs = segment(result)
    assert segs[-1].heading_path == ["Cell Biology", "Organelles"]


@pytest.mark.parametrize(
    "name,data,code",
    [
        ("notes.pptx", b"PK..", "unsupported_type"),
        ("fake.pdf", b"hello", "unsupported_type"),
        ("fake.docx", b"%PDF-1.4", "unsupported_type"),
    ],
)
def test_detect_kind_rejects(name, data, code):
    with pytest.raises(ExtractionError) as exc:
        detect_kind(name, data)
    assert exc.value.code == code


def test_detect_kind_accepts():
    assert detect_kind("Notes.MD", b"# hi") == "markdown"
    assert detect_kind("ch1.pdf", b"%PDF-1.7 ...") == "pdf"


def test_corrupt_files_fail_clearly():
    with pytest.raises(ExtractionError) as exc:
        get_extractor("pdf").extract(b"%PDF-1.4 garbage")
    assert exc.value.code == "unreadable_pdf"
    with pytest.raises(ExtractionError) as exc:
        get_extractor("docx").extract(b"PK not a zip")
    assert exc.value.code == "unreadable_docx"
