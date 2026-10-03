import pytest
from sqlalchemy import create_engine, text

from tests.fakes import FakeLLM, FakeTranscriber, FakeVision

TABLES = (
    "flashcard_reviews, quiz_attempts, quality_reports, guide_events, generation_jobs, guide_sources, "
    "study_guides, source_segments, sources, user_sessions, users"
)


@pytest.fixture(scope="session")
def _database():
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings

    url = get_settings().database_url
    try:
        create_engine(url).connect().close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Postgres not available at {url}: {exc}")
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    return url


@pytest.fixture
def client(_database):
    from fastapi.testclient import TestClient

    from app.db.session import get_engine
    from app.main import create_app

    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    with TestClient(create_app()) as c:
        c.headers["X-Requested-With"] = "test"
        yield c


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def vision():
    return FakeVision()


@pytest.fixture
def transcriber():
    return FakeTranscriber()


@pytest.fixture
def work(llm, vision, transcriber):
    """Run queued jobs until the queue is empty, like the worker would."""
    from app.core.config import get_settings
    from app.storage.files import get_storage
    from app.worker import run_once

    def _work(max_jobs: int = 20) -> int:
        ran = 0
        while ran < max_jobs and run_once(
            llm, get_storage(), get_settings(), vision=vision, transcriber=transcriber
        ):
            ran += 1
        return ran

    return _work


def signup(client, email="sam@example.com", password="correct horse"):
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "display_name": "Sam", "confirms_age_13_plus": True},
    )
    assert r.status_code == 201, r.text
    return r.json()
