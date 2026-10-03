"""Recordings, videos, scans and photos: extraction, timestamps and segment refs.

Video and audio tests make small files with ffmpeg. The model and the speech-to-text step are
fakes (tests/fakes.py), so nothing here downloads a model or calls the API.
"""

import shutil

import pytest

from app.core.config import Settings
from app.ingestion.base import Block, ExtractionError, ExtractResult, ExtractTools
from app.ingestion.media import AudioExtractor, VideoExtractor, still_stretches
from app.ingestion.registry import detect_kind, get_extractor, mime_for
from app.ingestion.segment import clock, segment, time_ref
from app.llm.prompts.common import render_segments
from tests.docs import make_audio, make_png, make_scanned_pdf, make_video
from tests.fakes import FakeTranscriber, FakeVision

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def tools(**overrides) -> ExtractTools:
    settings = Settings(**overrides)
    return ExtractTools(settings=settings, vision=FakeVision(), transcriber=FakeTranscriber())


# ---------- refs and segments ----------


def test_time_refs_and_clock():
    assert time_ref("t", 0) == "t0m00s"
    assert time_ref("t", 872.9) == "t14m32s"
    assert time_ref("v", 3725) == "v1h02m05s"
    assert clock(872.9) == "14:32" and clock(3725) == "1:02:05"


def test_speech_is_cut_into_short_stretches_and_slides_name_sections():
    blocks = [Block(text="Welcome everyone.", kind="speech", start=0, end=3)]
    blocks += [
        Block(text=f"Sentence {i} about the water cycle.", kind="speech", start=5 + i * 10, end=12 + i * 10)
        for i in range(30)
    ]
    blocks.insert(5, Block(text="Evaporation\nWater turns to vapour", kind="on_screen", start=45, end=200))
    segs = segment(ExtractResult(blocks=blocks, timed=True, duration=310, media="video"))
    speech = [s for s in segs if not s.locator["on_screen"]]
    screen = [s for s in segs if s.locator["on_screen"]]
    assert [s.ref for s in screen] == ["v0m45s"]
    assert screen[0].locator == {
        "kind": "time",
        "start": 45,
        "end": 200,
        "media": "video",
        "on_screen": True,
        "section": "Evaporation",
    }
    assert speech[0].ref == "t0m00s" and speech[0].heading_path == []
    assert all(s.heading_path == ["Evaporation"] for s in speech[1:])
    assert all(s.locator["end"] - s.locator["start"] <= 120 for s in speech), (
        "a citation stays close to its moment"
    )
    assert len({s.ref for s in segs}) == len(segs)


def test_same_second_refs_stay_unique():
    blocks = [
        Block(text="First slide", kind="on_screen", start=10.2, end=10.6),
        Block(text="Second slide", kind="on_screen", start=10.7, end=20),
    ]
    refs = [s.ref for s in segment(ExtractResult(blocks=blocks, timed=True, media="video"))]
    assert refs == ["v0m10s", "v0m10s-2"]


def test_prompt_shows_times_and_explains_transcripts():
    segs = [
        {
            "ref": "t1m05s",
            "text": "So remember this.",
            "locator": {"kind": "time", "start": 65, "on_screen": False},
        },
        {
            "ref": "v1m10s",
            "text": "Osmosis\n[On screen, described by AI] A cell in water.",
            "locator": {"kind": "time", "start": 70, "on_screen": True},
        },
    ]
    text = render_segments(segs)
    assert '<segment id="t1m05s" time="1:05" type="speech">' in text
    assert '<segment id="v1m10s" time="1:10" type="on screen">' in text
    assert "automatic transcript" in text and "never quote it" in text
    plain = render_segments([{"ref": "s1", "text": "Plain notes."}])
    assert "transcript" not in plain and "described by AI" not in plain


def test_still_stretches_finds_slides_and_skips_quick_cuts():
    red, blue, flash = bytes([200, 0, 0] * 4), bytes([0, 0, 200] * 4), bytes([255] * 12)
    thumbs = [red] * 5 + [flash] + [blue] * 4
    times = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]
    assert still_stretches(thumbs, times, duration=20) == [(0, 10, 4), (12, 20, 9)]


# ---------- file types ----------


@pytest.mark.parametrize(
    ("name", "head", "kind"),
    [
        ("notes.jpg", b"\xff\xd8\xff\xe0", "image"),
        ("notes.PNG", b"\x89PNG\r\n\x1a\n", "image"),
        ("notes.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image"),
        ("lecture.mp3", b"ID3\x04\x00", "audio"),
        ("memo.m4a", b"\x00\x00\x00\x20ftypM4A ", "audio"),
        ("class.wav", b"RIFF\x00\x00\x00\x00WAVEfmt ", "audio"),
        ("class.mp4", b"\x00\x00\x00\x18ftypmp42", "video"),
        ("class.webm", b"\x1a\x45\xdf\xa3\x9f", "video"),
    ],
)
def test_detect_media_and_image_kinds(name, head, kind):
    assert detect_kind(name, head) == kind


@pytest.mark.parametrize(
    ("name", "head"),
    [("photo.jpg", b"%PDF-1.4"), ("talk.mp3", b"<html>"), ("talk.mp4", b"MZ\x90\x00")],
)
def test_renamed_files_are_refused(name, head):
    with pytest.raises(ExtractionError) as exc:
        detect_kind(name, head)
    assert exc.value.code == "unsupported_type"


def test_heic_gets_a_clear_hint():
    with pytest.raises(ExtractionError) as exc:
        detect_kind("IMG_0001.HEIC", b"....")
    assert "JPEG" in exc.value.message


def test_mime_types_follow_the_file():
    assert mime_for("audio", "talk.m4a") == "audio/mp4"
    assert mime_for("video", "class.mov") == "video/quicktime"
    assert mime_for("pdf", "x.pdf") == "application/pdf"


# ---------- scans and photos ----------


def test_photo_is_read_and_descriptions_are_labelled():
    t = tools()
    result = get_extractor("image", t).extract(make_png())
    assert result.paged and result.page_count == 1
    kinds = [b.kind for b in result.blocks]
    assert kinds[0] == "heading"
    texts = [b.text for b in result.blocks]
    assert any(x.startswith("$6CO_2") for x in texts), "formulas stay exact"
    assert any(x.startswith("[Picture, described by AI]") for x in texts)
    assert result.warnings[0]["code"] == "ocr_pages"
    assert result.usage["calls"] == 1
    assert [s.ref for s in segment(result)] == ["p1-s1"]


def test_scanned_pages_in_a_pdf_are_read_in_place():
    t = tools()
    data = make_scanned_pdf(["Typed page one about light. " * 5, None, "Typed page three about water. " * 5])
    result = get_extractor("pdf", t).extract(data)
    pages = [b.page for b in result.blocks]
    assert pages == sorted(pages), "read pages stay in page order"
    assert any(b.page == 2 and "glucose" in b.text for b in result.blocks)
    assert result.warnings == [result.warnings[0]] and result.warnings[0]["pages"] == [2]
    assert t.vision.calls == ["ocr"], "only the scanned page goes to the model"


def test_fully_scanned_pdf_is_read():
    t = tools()
    result = get_extractor("pdf", t).extract(make_scanned_pdf([None, None]))
    assert {b.page for b in result.blocks} == {1, 2}
    assert len(t.vision.calls) == 2


def test_scans_refused_clearly_when_reading_images_is_off():
    with pytest.raises(ExtractionError) as exc:
        get_extractor("pdf", tools(vision_enabled=False)).extract(make_scanned_pdf([None, None]))
    assert exc.value.code == "scanned_document" and "turned off" in exc.value.message
    with pytest.raises(ExtractionError) as exc:
        get_extractor("image", tools(vision_enabled=False)).extract(make_png())
    assert exc.value.code == "ocr_unavailable"


def test_scanned_pdf_over_the_page_limit_is_refused_before_reading():
    t = tools(max_pages=2)
    with pytest.raises(ExtractionError) as exc:
        get_extractor("pdf", t).extract(make_scanned_pdf([None, None, None]))
    assert exc.value.code == "source_too_long"
    assert t.vision.calls == []


# ---------- audio and video ----------


@needs_ffmpeg
def test_audio_is_transcribed_with_times(tmp_path):
    path = tmp_path / "lecture.mp3"
    make_audio(path, 45)
    result = AudioExtractor(tools()).extract_file(path)
    assert result.timed and result.media == "audio" and 44 < result.duration < 46
    segs = segment(result)
    assert segs[0].ref == "t0m01s" and segs[0].locator["media"] == "audio"
    assert "This is important" in segs[0].text


@needs_ffmpeg
def test_recording_over_the_limit_is_refused(tmp_path):
    path = tmp_path / "long.mp3"
    make_audio(path, 70)
    t = tools(max_media_minutes=1)
    with pytest.raises(ExtractionError) as exc:
        AudioExtractor(t).extract_file(path)
    assert exc.value.code == "source_too_long" and "1:10" in exc.value.message
    assert t.transcriber.calls == 0


@needs_ffmpeg
def test_video_combines_speech_with_slides(tmp_path):
    path = tmp_path / "class.mp4"
    # A slide, the teacher talking, another slide, a one-second flash, the slide again.
    make_video(path, [("red", 20), ("gray", 12), ("blue", 16), ("white", 1), ("blue", 12)])
    t = tools()
    result = VideoExtractor(t).extract_file(path)
    assert result.timed and result.media == "video"
    screen = [b for b in result.blocks if b.kind == "on_screen"]
    assert [b.text.split("\n")[0] for b in screen] == ["Photosynthesis", "Chlorophyll"]
    assert screen[0].start == 0 and 30 <= screen[1].start <= 36
    assert screen[1].end > 50, "the same slide after a cut extends the first, not a new block"
    assert "[On screen, described by AI]" in screen[1].text
    assert result.usage["calls"] == len(t.vision.calls) <= 4
    segs = segment(result)
    assert segs[0].ref == "v0m00s"
    assert any(s.ref.startswith("t") and s.heading_path == ["Chlorophyll"] for s in segs)


@needs_ffmpeg
def test_video_frames_are_capped(tmp_path):
    path = tmp_path / "busy.mp4"
    make_video(path, [(c, 8) for c in ("red", "blue", "yellow", "purple", "orange")])
    t = tools(max_video_frames=2)
    VideoExtractor(t).extract_file(path)
    assert len(t.vision.calls) == 2


@needs_ffmpeg
def test_silent_video_uses_the_screen_only(tmp_path):
    path = tmp_path / "silent.mp4"
    make_video(path, [("red", 12)], audio=False)
    t = tools()
    result = VideoExtractor(t).extract_file(path)
    assert [b.kind for b in result.blocks] == ["on_screen"]
    assert result.warnings[0]["code"] == "no_audio"
    assert t.transcriber.calls == 0


@needs_ffmpeg
def test_video_without_slide_reading_still_transcribes(tmp_path):
    path = tmp_path / "class.mp4"
    make_video(path, [("red", 20)])
    t = tools(vision_enabled=False)
    result = VideoExtractor(t).extract_file(path)
    assert {b.kind for b in result.blocks} == {"speech"}
    assert result.warnings[0]["code"] == "screen_skipped"


def test_damaged_recording_is_reported(tmp_path):
    if shutil.which("ffprobe") is None:
        pytest.skip("ffprobe is not installed")
    path = tmp_path / "broken.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100)
    with pytest.raises(ExtractionError) as exc:
        VideoExtractor(tools()).extract_file(path)
    assert exc.value.code == "unreadable_media"


def test_exports_show_times():
    from app.export.common import ExportInfo

    info = ExportInfo(title="Lecture", level="high_school")
    assert info.ref_label("t14m32s") == "14:32"
    assert info.ref_label("v1h02m05s") == "1:02:05 on screen"
    assert info.ref_label("d2-t0m05s-2") == "Source 2, 0:05"
    assert info.cite(["t14m32s", "t14m32s-2"]) == "(Source: 14:32)"
