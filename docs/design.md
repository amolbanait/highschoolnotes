# MVP design

The full design (requirements, ambiguities, risks, architecture, stack, data model, API contracts, AI pipeline, scope, folder layout and decisions) lives in a shared, editable doc:

https://claude.ai/code/artifact/27c8dd67-53fe-41bf-a74d-24c6822b5915

## Key decisions at a glance

- **Stack:** Next.js + TypeScript web app; Python 3.12 FastAPI API and a worker sharing the same code; PostgreSQL 16; Claude via the Anthropic SDK (model ids in config).
- **Study guide = one schema-validated JSON document** (JSONB). Every concept, fact, example, question and flashcard has a stable id, `source_refs`, and an `origin` (`source` or `ai_generated`).
- **Every input becomes source segments** with a polymorphic locator (`page` now; `time` and `slide` later), so new input types are new extractors only.
- **Pipeline:** extract -> clean and segment -> plan (model) -> sequence (code, prerequisites first) -> write each concept (model, parallel) -> assemble -> practice questions and flashcards -> quality check (code checks, then a separate model review; below 70 regenerate once, then flag).
- **Job queue:** a Postgres table claimed with `FOR UPDATE SKIP LOCKED`; progress streamed to the browser over SSE.
- **Diagrams and formulas as text:** Mermaid and KaTeX, validated server-side.
- **Limits:** 20 MB per file, 60 pages or 40,000 words per guide.
- **Privacy:** sign-up 13+, minimal personal data, full delete, no school credentials ever stored.

## Phases

1. PDF, DOCX, TXT, Markdown, pasted text -> full study guide, quiz, flashcards, quality check, export (PDF, Markdown, DOCX, HTML).
2. OCR, PPTX, audio and video with timestamps.
3. Web pages, LMS links with temporary sessions, courses and dashboard.
4. Ask AI tutor, adaptive quizzes, weak areas, spaced repetition, voice.
