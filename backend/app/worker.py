"""Job loop: claim a job, run it, repeat. Run several of these for more throughput."""

import logging
import signal
import time

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import get_sessionmaker
from app.llm.client import LLM, AnthropicLLM
from app.pipeline import jobs
from app.storage.files import Storage, get_storage

log = logging.getLogger("worker")


def run_once(llm: LLM, storage: Storage, settings: Settings) -> bool:
    """Claim and run one job. Returns False when the queue is empty."""
    Session_ = get_sessionmaker()
    with Session_() as db:
        job = jobs.claim(db, settings)
        if job is None:
            return False
        job_id, kind = job.id, job.kind
    log.info("running job %s (%s)", job_id, kind)
    started = time.monotonic()
    jobs.run_job(Session_, job_id, llm, storage, settings)
    log.info("job %s finished in %.1fs", job_id, time.monotonic() - started)
    return True


def main() -> None:
    configure_logging()
    settings = get_settings()
    llm = AnthropicLLM(settings)
    storage = get_storage()
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True
        log.info("stopping after the current job")

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("worker %s started (model %s)", jobs.WORKER_ID, settings.writer_model)
    while not stopping:
        try:
            if not run_once(llm, storage, settings):
                time.sleep(settings.worker_poll_seconds)
        except Exception:
            log.exception("worker loop error")
            time.sleep(5)


if __name__ == "__main__":
    main()
