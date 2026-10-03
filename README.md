# HighSchoolNotes

A web app that turns learning material (PDF, Word, text, pasted text; later video, audio, OCR and LMS content) into teacher-quality study guides for high school students (grades 9-12).

The goal is teaching, not summarizing: logically ordered concepts, simple explanations, examples, vocabulary, diagrams, practice questions and flashcards, with every key point traceable to its source.

- [docs/design.md](docs/design.md): the MVP design.
- [backend/](backend/README.md): API, worker and note pipeline.
- [frontend/](frontend/README.md): the student web app.

## Run locally

```sh
cp .env.example .env        # set ANTHROPIC_API_KEY
docker compose up --build   # app at http://localhost:3000, API docs at http://localhost:8000/docs
```
