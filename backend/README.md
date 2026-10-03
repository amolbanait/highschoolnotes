# Backend: API, worker and note pipeline

Python 3.11+, FastAPI, SQLAlchemy 2 on PostgreSQL 16, Claude through the Anthropic SDK.
The API never waits on extraction or the model; it writes jobs to Postgres and a worker runs them.

## Run it

With Docker (from the repository root):

```sh
cp .env.example .env        # set ANTHROPIC_API_KEY
docker compose up --build   # postgres, migrations, api on :8000, one worker
```

Without Docker:

```sh
cd backend
pip install -e ".[dev]"
export HSN_DATABASE_URL=postgresql+psycopg://hsn:hsn@localhost:5432/hsn ANTHROPIC_API_KEY=...
alembic upgrade head
uvicorn app.main:app --reload    # API, docs at http://localhost:8000/docs
python -m app.worker             # in a second terminal; run more for more throughput
```

Try the pipeline on a file without the database, and see what it costs:

```sh
python -m app.cli chapter.pdf --level high_school --out guide.json
```

## Test

```sh
createdb hsn_test   # once; tests run migrations themselves
pytest              # HSN_DATABASE_URL defaults to .../hsn_test
ruff check . && ruff format --check .
```

Pipeline and API tests use `tests/fakes.py`, a stand-in model that returns schema-valid output
built from the prompt's own segments, plus deliberate mistakes (unknown ids, invented quotes,
mislabelled examples) that the code must catch. No test calls the real model.

## How a guide is made

| # | Stage | Where | Notes |
|---|---|---|---|
| 1 | Extract | `ingestion/pdf.py`, `docx.py`, `text.py` | Runs as an `extract` job on upload. Scanned PDFs are detected and refused with a clear message. |
| 2 | Clean and segment | `ingestion/segment.py` | Drops running headers, footers and page numbers; ~500-token segments that never cross a page. Refs: `p12-s3` (PDF) or `s7` (flowing text). |
| 3 | Plan | `pipeline/stages/plan.py` | One model call: concepts with difficulty and prerequisites, vocabulary, verbatim facts and formulas, relationships, gaps. |
| 4 | Sequence | `pipeline/stages/sequence.py` | Code: topological sort (prerequisites first, source order breaks ties, cycles broken with a warning); every citation and quote checked. |
| 5 | Write sections | `pipeline/stages/write.py` | One call per concept, in parallel, with the outline and that concept's segments. Three levels only for hard concepts; Mermaid only where planned. |
| 6 | Assemble | `pipeline/stages/assemble.py` | Overview, objectives, summary, review checklist. |
| 7 | Practice | `pipeline/stages/practice.py` | Six question types with answer key, flashcards. A multiple-choice answer that is not exactly one option becomes an open question. |
| 8 | Check | `pipeline/orchestrator.py` | Deterministic checks only for now; the model review and regenerate-or-flag loop is the next build step. |

Each stage's output is saved to the job's `state`, so a crashed or rate-limited job resumes
where it stopped, and finished sections are never paid for twice. Progress events go to the
`guide_events` table and stream to the browser over SSE.

**Grounding done by code** (`pipeline/grounding.py`): unknown segment ids are dropped; a quote
must appear in a segment it cites (case, whitespace and quote-style insensitive), is re-pointed
if found in another segment, and is marked `verified: false` if found nowhere; an example that
claims to come from the source but cites nothing is relabelled `ai_generated`; source text is
escaped inside `<segment>` tags so it cannot break out of them.

**Model calls** (`llm/client.py`): structured output against the Pydantic schemas in
`schemas/study_guide.py`, streamed, with the system prompt cached, one retry with the
validation error, server-side refusal fallbacks, and a per-guide token budget.

## API

All under `/api/v1`; OpenAPI at `/api/v1/openapi.json`. Errors are always
`{"error": {"code", "message", "details"}}`.

Auth is an HTTP-only session cookie. Requests that change data must also send an
`X-Requested-With` header (any value): a cross-site form cannot set it, so this blocks CSRF.

| Method and path | Notes |
|---|---|
| `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout` | Signup requires `confirms_age_13_plus: true`. |
| `GET /me`, `PATCH /me`, `DELETE /me` | Delete removes the account, files, guides and history. |
| `POST /sources` | Multipart `file` (+ optional `title`), or JSON `{kind: "paste", title, text}`. 201 with `status: "extracting"`. |
| `GET /sources`, `GET /sources/{id}`, `GET /sources/{id}/segments?page=&ref=`, `GET /sources/{id}/file`, `DELETE /sources/{id}` | Delete also removes guides built only from that source. |
| `POST /guides` | `{source_ids, level}`. 202 `{guide_id, job_id}`. Can be called while sources are still extracting. |
| `GET /guides?cursor=`, `GET /guides/{id}`, `DELETE /guides/{id}` | `content` is the guide document, partial while running. |
| `GET /guides/{id}/refs/{ref}` | Resolve a citation to its segment text and location (the "view in source" panel). |
| `GET /guides/{id}/events` | SSE: `stage`, `topics_detected`, `section_ready`, `completed`, `failed`. Supports `Last-Event-ID`. |
| `POST /guides/{id}/sections/{section_id}/regenerate` | `{instruction?: "simpler"}`. 202 `{job_id}`. |
| `POST /guides/{id}/quiz-attempts`, `POST /guides/{id}/flashcard-reviews` | Multiple choice is graded; open answers return the model answer for self-checking. |

Limits: 20 MB per upload, 60 pages or 40,000 words per guide, one running guide per user,
10 guides per user per hour. All are settings (`app/core/config.py`, env prefix `HSN_`).

## Where this differs from the design doc

- **Model:** the writer defaults to `claude-opus-5-5` (one setting, `HSN_WRITER_MODEL`). Change it to
  a cheaper model once `app.cli` has measured cost and quality on real material.
- **Two extra tables:** `user_sessions` (so logout and account deletion revoke cookies at once) and
  `guide_events` (so the progress stream can replay after a reconnect).
- **Jobs table:** `generation_jobs` also carries `kind`, `source_id`, `params`, `state` and `run_after`,
  because extraction and section regeneration run through the same queue.
- **Refs for non-paged sources** are `s7` with a `text` locator (section and character range), since
  Word and text files have no reliable pages.
- **Pasted text** is read as Markdown, so pasted headings become sections.
- **Long inputs** are planned in one call (40,000 words fits comfortably), not summary-then-plan.
- **Not yet here** (next steps in the plan): the model quality review and `quality_reports` writes, Mermaid
  parsing, export, and the web app.
