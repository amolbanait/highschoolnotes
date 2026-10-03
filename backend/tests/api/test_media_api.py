"""Recordings and photos through the HTTP API and the worker, with fake vision and speech-to-text."""

import shutil

import pytest
from sqlalchemy import select

from app.db.models import GuideEvent
from app.db.session import get_sessionmaker
from tests.api.conftest import signup
from tests.docs import make_video

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


@needs_ffmpeg
def test_video_to_guide_with_timestamps(client, work, tmp_path, llm):
    signup(client)
    path = tmp_path / "Biology lecture.mp4"
    make_video(path, [("red", 30), ("blue", 40)])
    r = client.post("/api/v1/sources", files={"file": (path.name, path.read_bytes(), "video/mp4")})
    assert r.status_code == 201, r.text
    source = r.json()
    assert source["kind"] == "video" and source["title"] == "Biology lecture"

    # The guide is asked for before the video is processed; it waits and shows progress.
    guide_id = client.post("/api/v1/guides", json={"source_ids": [source["id"]]}).json()["guide_id"]
    work()
    source = client.get(f"/api/v1/sources/{source['id']}").json()
    assert source["status"] == "ready", source
    assert 69 < source["duration_seconds"] < 71 and source["page_count"] is None

    segments = client.get(f"/api/v1/sources/{source['id']}/segments").json()
    refs = [s["ref"] for s in segments]
    assert refs[0] == "v0m00s" and "t0m01s" in refs and any(r.startswith("v0m3") for r in refs)
    assert all(s["locator"]["kind"] == "time" and s["locator"]["media"] == "video" for s in segments)

    with get_sessionmaker()() as db:
        details = db.scalars(
            select(GuideEvent.data).where(GuideEvent.type == "stage").order_by(GuideEvent.id)
        ).all()
    assert any(d.get("stage") == "extract" and "Biology lecture" in d.get("detail", "") for d in details)

    guide = client.get(f"/api/v1/guides/{guide_id}").json()
    assert guide["status"] == "ready"
    plan_prompt = next(p for stage, p in llm.prompts if stage == "plan")
    assert 'time="0:00" type="on screen"' in plan_prompt and "automatic transcript" in plan_prompt

    cited = client.get(f"/api/v1/guides/{guide_id}/refs/v0m00s").json()
    assert cited["locator"]["start"] == 0 and cited["text"].startswith("Photosynthesis")

    # The player beside a citation can seek: the media endpoint serves byte ranges inline.
    media = client.get(f"/api/v1/sources/{source['id']}/media", headers={"Range": "bytes=0-99"})
    assert media.status_code == 206 and len(media.content) == 100
    assert media.headers["content-type"] == "video/mp4"
    assert media.headers["content-disposition"].startswith("inline")


def test_photo_of_notes_is_read(client, work, vision):
    signup(client)
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (300, 400), "white").save(buffer, format="JPEG")
    r = client.post("/api/v1/sources", files={"file": ("page.jpg", buffer.getvalue(), "image/jpeg")})
    assert r.status_code == 201, r.text
    work()
    source = client.get(f"/api/v1/sources/{r.json()['id']}").json()
    assert source["status"] == "ready" and source["kind"] == "image"
    assert source["warnings"][0]["code"] == "ocr_pages"
    assert vision.calls == ["ocr"]
    seg = client.get(f"/api/v1/sources/{source['id']}/segments").json()[0]
    assert seg["ref"] == "p1-s1" and "glucose" in seg["text"]
    assert client.get(f"/api/v1/sources/{source['id']}/media").headers["content-type"] == "image/jpeg"


def test_media_endpoint_is_for_recordings_and_images_only(client, work):
    signup(client)
    r = client.post("/api/v1/sources", json={"kind": "paste", "title": "Notes", "text": "Some notes."})
    assert client.get(f"/api/v1/sources/{r.json()['id']}/media").status_code == 404


@needs_ffmpeg
def test_recording_size_limit(client, monkeypatch, tmp_path):
    from app.core.config import get_settings
    from tests.docs import make_audio

    signup(client)
    path = tmp_path / "talk.mp3"
    make_audio(path, 20)
    monkeypatch.setenv("HSN_MAX_MEDIA_BYTES", "1000")
    get_settings.cache_clear()
    try:
        r = client.post("/api/v1/sources", files={"file": ("talk.mp3", path.read_bytes(), "audio/mpeg")})
        assert r.status_code == 413 and "Recordings" in r.json()["error"]["message"]
        assert client.get("/api/v1/sources").json() == [], "nothing is kept from a refused upload"
    finally:
        monkeypatch.delenv("HSN_MAX_MEDIA_BYTES")
        get_settings.cache_clear()
