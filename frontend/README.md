# Web app

Next.js 16 (App Router), React 19, TypeScript and Tailwind CSS 4. Diagrams render with Mermaid,
formulas with KaTeX, and model-written text as Markdown (raw HTML is never rendered).

## Run it

With the API running on :8000 (see [backend/README.md](../backend/README.md)):

```sh
cd frontend
npm install
npm run dev          # http://localhost:3000
```

`docker compose up --build` from the repository root runs everything, the web app included.

The browser only talks to this app. `next.config.ts` proxies `/api/v1/*` to `API_URL`
(default `http://localhost:8000`), so the session cookie is first-party and no CORS is needed.
Next's own gzip is off because it holds back the progress stream; compress at your reverse
proxy instead and leave `text/event-stream` uncompressed.

## Check it

```sh
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

## Pages

| Path                      | What the student does                                                                                                                                                                                                                                                                                                                                                             |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/signup`, `/login`       | Create an account (13+) or sign in.                                                                                                                                                                                                                                                                                                                                               |
| `/`                       | See their guides; open, practise or delete one.                                                                                                                                                                                                                                                                                                                                   |
| `/new`                    | Upload up to five files or paste text, or reuse earlier material; pick a level.                                                                                                                                                                                                                                                                                                   |
| `/guides/[id]`            | Watch progress live (stages, topics found, sections as they land), then read the guide: overview, vocabulary, concepts with three explanation levels, diagrams, examples labelled by origin, common mistakes, quick checks, key facts, formulas, connections, summary and checklist. Every citation opens the exact source text. "Explain this more simply" rewrites one section. |
| `/guides/[id]/quiz`       | Answer practice questions. Multiple choice is graded; open answers are compared with a model answer and self-marked.                                                                                                                                                                                                                                                              |
| `/guides/[id]/flashcards` | Flip cards and rate them; "Again" cards come back at the end of the deck.                                                                                                                                                                                                                                                                                                         |
| `/account`                | Change name and usual level, sign out, delete everything.                                                                                                                                                                                                                                                                                                                         |

## Types

The API's request, response and guide shapes come from the backend, never by hand:

```sh
cd backend && python -m app.export_schemas ../frontend/lib/schema   # OpenAPI + guide JSON Schema
cd frontend && npm run gen:types                                    # lib/schema/*.d.ts
```

CI fails if either step would change a committed file.
