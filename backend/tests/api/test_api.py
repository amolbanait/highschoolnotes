"""End to end through the HTTP API and the worker, with the fake model and a real Postgres."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.db.models import GenerationJob, GuideEvent
from app.db.session import get_sessionmaker
from tests.api.conftest import signup
from tests.docs import make_docx, make_pdf


def _paste(client, text, title="Photosynthesis notes"):
    r = client.post("/api/v1/sources", json={"kind": "paste", "title": title, "text": text})
    assert r.status_code == 201, r.text
    return r.json()


def _make_guide(client, work, sample_text, level="high_school"):
    source = _paste(client, sample_text)
    r = client.post("/api/v1/guides", json={"source_ids": [source["id"]], "level": level})
    assert r.status_code == 202, r.text
    work()
    return source, r.json()["guide_id"]


def test_auth_flow(client):
    user = signup(client)
    assert client.get("/api/v1/me").json()["email"] == user["email"]
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/me").status_code == 401
    bad = client.post("/api/v1/auth/login", json={"email": "sam@example.com", "password": "wrong password"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "invalid_credentials"
    ok = client.post("/api/v1/auth/login", json={"email": "SAM@example.com", "password": "correct horse"})
    assert ok.status_code == 200 and client.get("/api/v1/me").status_code == 200


def test_signup_rules(client):
    r = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "kid@example.com",
            "password": "longenough",
            "display_name": "K",
            "confirms_age_13_plus": False,
        },
    )
    assert r.json()["error"]["code"] == "age_requirement"
    signup(client)
    r = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "sam@example.com",
            "password": "longenough",
            "display_name": "S",
            "confirms_age_13_plus": True,
        },
    )
    assert r.status_code == 409
    r = client.post("/api/v1/auth/signup", json={"email": "x@example.com", "password": "short"})
    assert r.status_code == 422 and "short" not in r.text, "submitted values are never echoed back"


def test_csrf_header_required_for_writes(client):
    signup(client)
    del client.headers["X-Requested-With"]
    r = client.post("/api/v1/sources", json={"kind": "paste", "title": "t", "text": "x"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_header_missing"
    assert client.get("/api/v1/me").status_code == 200


def test_paste_to_finished_guide(client, work, llm, sample_text):
    signup(client)
    source, guide_id = _make_guide(client, work, sample_text)

    source = client.get(f"/api/v1/sources/{source['id']}").json()
    assert source["status"] == "ready" and source["word_count"] > 100 and source["kind"] == "paste"

    guide = client.get(f"/api/v1/guides/{guide_id}").json()
    assert guide["status"] == "ready", guide
    content = guide["content"]
    assert [c["title"] for c in content["concepts"]] == [
        "Inputs and outputs",
        "Chlorophyll",
        "Light reactions",
    ]
    assert content["title"] == guide["title"] == "Photosynthesis"
    assert guide["token_usage"]["total"]["calls"] == len(llm.calls)
    assert guide["progress"]["done"][-1] == "check"

    # Click a citation, get the source text and its location.
    ref = content["vocabulary"][0]["source_refs"][0]
    seg = client.get(f"/api/v1/guides/{guide_id}/refs/{ref}").json()
    assert seg["ref"] == ref and "Chlorophyll" in seg["text"] and seg["locator"]["kind"] == "text"
    assert client.get(f"/api/v1/guides/{guide_id}/refs/p99-s9").status_code == 404

    segments = client.get(f"/api/v1/sources/{source['id']}/segments").json()
    assert [s["ref"] for s in segments] == ["s1", "s2", "s3"]

    # Progress stream replays every event and ends at "completed".
    with client.stream("GET", f"/api/v1/guides/{guide_id}/events") as r:
        body = "".join(r.iter_text())
    events = [line.split(": ", 1)[1] for line in body.splitlines() if line.startswith("event: ")]
    assert events[0] == "stage" and "topics_detected" in events and events[-1] == "completed"
    assert events.count("section_ready") == 3
    last_id = int([line for line in body.splitlines() if line.startswith("id: ")][-2].split(": ")[1])
    with client.stream(
        "GET", f"/api/v1/guides/{guide_id}/events", headers={"Last-Event-ID": str(last_id)}
    ) as r:
        assert [ln for ln in "".join(r.iter_text()).splitlines() if ln.startswith("event: ")] == [
            "event: completed"
        ]

    listing = client.get("/api/v1/guides").json()
    assert [g["id"] for g in listing["items"]] == [guide_id] and listing["next_cursor"] is None


def test_quiz_flashcards_and_regenerate(client, work, llm, sample_text):
    signup(client)
    _, guide_id = _make_guide(client, work, sample_text)
    content = client.get(f"/api/v1/guides/{guide_id}").json()["content"]
    mc, open_q = content["questions"]

    r = client.post(
        f"/api/v1/guides/{guide_id}/quiz-attempts", json={"question_id": mc["id"], "answer": " chlorophyll "}
    )
    assert r.json()["is_correct"] is True
    r = client.post(
        f"/api/v1/guides/{guide_id}/quiz-attempts", json={"question_id": mc["id"], "answer": "Water"}
    )
    assert r.json()["is_correct"] is False and r.json()["correct_answer"] == "Chlorophyll"
    r = client.post(
        f"/api/v1/guides/{guide_id}/quiz-attempts", json={"question_id": open_q["id"], "answer": "idk"}
    )
    assert r.json()["is_correct"] is None
    assert (
        client.post(
            f"/api/v1/guides/{guide_id}/quiz-attempts", json={"question_id": "q99", "answer": "x"}
        ).status_code
        == 404
    )

    card = content["flashcards"][0]["id"]
    assert (
        client.post(
            f"/api/v1/guides/{guide_id}/flashcard-reviews", json={"card_id": card, "rating": "good"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/v1/guides/{guide_id}/flashcard-reviews", json={"card_id": card, "rating": "meh"}
        ).status_code
        == 422
    )

    calls_before = len(llm.calls)
    r = client.post(f"/api/v1/guides/{guide_id}/sections/c2/regenerate", json={"instruction": "simpler"})
    assert r.status_code == 202
    assert client.post(f"/api/v1/guides/{guide_id}/sections/c2/regenerate", json={}).status_code == 429
    work()
    assert llm.calls[calls_before:] == ["write"]
    # The web app follows a rewrite by its job id, so its events must carry that id.
    with get_sessionmaker()() as db:
        ready = db.scalars(
            select(GuideEvent).where(GuideEvent.type == "section_ready").order_by(GuideEvent.id.desc())
        ).first()
    assert ready.data["regenerated"] is True
    assert ready.data["job_id"] == r.json()["job_id"]
    assert client.get(f"/api/v1/guides/{guide_id}").json()["status"] == "ready"
    assert client.post(f"/api/v1/guides/{guide_id}/sections/c99/regenerate", json={}).status_code == 404


def test_pdf_and_docx_uploads(client, work):
    signup(client)
    pdf = make_pdf(
        [
            [("Chapter 1", 20), ("Plants take in carbon dioxide and water. " * 4, 11)],
            [("Chlorophyll", 16), ("Chlorophyll is a green pigment. " * 4, 11)],
            [("Light reactions", 16), ("Light energy splits water molecules. " * 4, 11)],
        ]
    )
    r = client.post("/api/v1/sources", files={"file": ("chapter.pdf", pdf, "application/pdf")})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "extracting" and r.json()["title"] == "chapter"
    work()
    source = client.get(f"/api/v1/sources/{r.json()['id']}").json()
    assert source["status"] == "ready" and source["page_count"] == 3
    page2 = client.get(f"/api/v1/sources/{source['id']}/segments", params={"page": 2}).json()
    assert [s["ref"] for s in page2] == ["p2-s1"]
    download = client.get(f"/api/v1/sources/{source['id']}/file")
    assert download.content == pdf and "chapter.pdf" in download.headers["content-disposition"]

    r = client.post(
        "/api/v1/sources",
        files={"file": ("cells.docx", make_docx(), "application/octet-stream")},
        data={"title": "Cells"},
    )
    work()
    source = client.get(f"/api/v1/sources/{r.json()['id']}").json()
    assert source["status"] == "ready" and source["kind"] == "docx" and source["title"] == "Cells"

    # Same file again: extraction is reused, no new job.
    again = client.post("/api/v1/sources", files={"file": ("chapter.pdf", pdf, "application/pdf")}).json()
    assert again["status"] == "ready" and work() == 0


def test_upload_errors(client, work, monkeypatch):
    signup(client)
    r = client.post(
        "/api/v1/sources", files={"file": ("slides.pptx", b"PK\x03\x04", "application/octet-stream")}
    )
    assert r.status_code == 415 and "PowerPoint" in r.json()["error"]["message"]
    r = client.post("/api/v1/sources", content=b"raw", headers={"content-type": "text/plain"})
    assert r.status_code == 415
    r = client.post("/api/v1/sources", json={"kind": "paste", "title": "", "text": "x"})
    assert r.status_code == 422

    monkeypatch.setenv("HSN_MAX_UPLOAD_BYTES", "100")
    from app.core.config import get_settings

    get_settings.cache_clear()
    r = client.post("/api/v1/sources", files={"file": ("big.txt", b"x " * 100, "text/plain")})
    assert r.status_code == 413 and r.json()["error"]["code"] == "source_too_large"
    monkeypatch.delenv("HSN_MAX_UPLOAD_BYTES")
    get_settings.cache_clear()

    scanned = make_pdf([[], [], []])
    r = client.post("/api/v1/sources", files={"file": ("scan.pdf", scanned, "application/pdf")})
    work()
    source = client.get(f"/api/v1/sources/{r.json()['id']}").json()
    assert source["status"] == "failed" and source["error"]["code"] == "scanned_document"
    r = client.post("/api/v1/guides", json={"source_ids": [source["id"]]})
    assert r.status_code == 400 and r.json()["error"]["code"] == "source_failed"


def test_guide_waits_for_extraction_and_limits(client, work, sample_text):
    signup(client)
    r = client.post("/api/v1/sources", files={"file": ("notes.md", sample_text.encode(), "text/markdown")})
    source_id = r.json()["id"]
    # Ask for the guide before extraction has run: the job waits, then completes.
    r = client.post("/api/v1/guides", json={"source_ids": [source_id]})
    guide_id = r.json()["guide_id"]
    assert (
        client.post("/api/v1/guides", json={"source_ids": [source_id]}).json()["error"]["code"]
        == "guide_in_progress"
    )
    # Skip the short wait the generate job sets while extraction is pending.
    for _ in range(3):
        work()
        with get_sessionmaker()() as db:
            db.execute(update(GenerationJob).values(run_after=datetime.now(UTC) - timedelta(seconds=1)))
            db.commit()
    assert client.get(f"/api/v1/guides/{guide_id}").json()["status"] == "ready"


def test_users_cannot_see_each_other(client, work, sample_text):
    signup(client, email="a@example.com")
    source, guide_id = _make_guide(client, work, sample_text)
    client.post("/api/v1/auth/logout")
    signup(client, email="b@example.com")
    assert client.get(f"/api/v1/guides/{guide_id}").status_code == 404
    assert client.get(f"/api/v1/sources/{source['id']}").status_code == 404
    assert client.get(f"/api/v1/guides/{guide_id}/events").status_code == 404
    assert client.delete(f"/api/v1/guides/{guide_id}").status_code == 404
    assert client.get("/api/v1/guides").json()["items"] == []


def test_delete_source_removes_its_guides_and_account_delete(client, work, sample_text):
    signup(client)
    source, guide_id = _make_guide(client, work, sample_text)
    assert client.delete(f"/api/v1/sources/{source['id']}").status_code == 204
    assert client.get(f"/api/v1/guides/{guide_id}").status_code == 404

    _make_guide(client, work, sample_text)
    assert client.delete("/api/v1/me").status_code == 204
    assert client.get("/api/v1/me").status_code == 401
    ok = client.post("/api/v1/auth/login", json={"email": "sam@example.com", "password": "correct horse"})
    assert ok.status_code == 401


def test_failed_generation_reports_clearly(client, work, llm, sample_text, monkeypatch):
    signup(client)
    monkeypatch.setenv("HSN_GUIDE_TOKEN_BUDGET", "1500")
    from app.core.config import get_settings

    get_settings.cache_clear()
    _, guide_id = _make_guide(client, work, sample_text)
    guide = client.get(f"/api/v1/guides/{guide_id}").json()
    assert guide["status"] == "failed" and guide["error"]["code"] == "token_budget_exceeded"
    with client.stream("GET", f"/api/v1/guides/{guide_id}/events") as r:
        assert "event: failed" in "".join(r.iter_text())


def test_outage_mid_guide_resumes_without_redoing_work(client, work, llm, sample_text):
    signup(client)
    llm.fail_on_write_call = 2
    _, guide_id = _make_guide(client, work, sample_text)
    guide = client.get(f"/api/v1/guides/{guide_id}").json()
    assert guide["status"] == "running" and guide["progress"]["done"] == ["plan", "sequence"]
    finished = guide["progress"]["sections"]
    assert len(guide["content"]["concepts"]) == finished >= 1  # partial guide is visible while running

    llm.fail_on_write_call = None
    calls_before = list(llm.calls)
    with get_sessionmaker()() as db:
        db.execute(update(GenerationJob).values(run_after=datetime.now(UTC) - timedelta(seconds=1)))
        db.commit()
    work()
    guide = client.get(f"/api/v1/guides/{guide_id}").json()
    assert guide["status"] == "ready"
    new_calls = llm.calls[len(calls_before) :]
    assert "plan" not in new_calls and new_calls.count("write") == 3 - finished
