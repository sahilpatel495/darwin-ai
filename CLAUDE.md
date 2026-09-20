# Verity

Plain-English questions over messy spreadsheets, with answers you can verify. Take-home for a Forward Deployed Engineer role; the author must be able to explain every module.

Read `docs/DESIGN.md` (what and why) and `docs/PLAN.md` (who builds what, with exact test cases).

## The one rule
The LLM never computes a number and never sees a row. It writes SQL and phrases results. DuckDB computes. Deterministic code verifies. `backend/app/catalog/prompt_context.py` is the only code allowed to turn data descriptions into prompt text.

## Commands (run from the repo root)
- Backend tests: `uv run pytest -q` (one area: `uv run pytest backend/tests/guard -q`)
- API: `uv run --env-file .env uvicorn app.main:app --app-dir backend --reload --port 8000`
- Frontend: `cd frontend && pnpm dev` (no backend: `VITE_MOCK=1 pnpm dev`), `pnpm typecheck`, `pnpm build`
- Regenerate UI fixtures after a contract change: `PYTHONPATH=backend:. uv run python backend/scripts/make_fixtures.py`
- Eval: `PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --split dev`

## Conventions
- Contracts live in `backend/app/contracts.py`, mirrored by hand in `frontend/src/types.ts`. Change both in one commit, then regenerate fixtures.
- Python 3.12, type hints everywhere, small functions, docstrings explain *why*. pandas is 3.0.
- No new dependencies without a recorded reason in `DECISIONS.md`.
- Tests never call a real model (`app.llm.fake.FakeLLM`). Free-tier tokens are scarce.
- No speculative abstractions. A deliberate shortcut gets a `# ponytail:` comment naming its ceiling and upgrade path.
- User-facing errors: what happened, then what to do next.
- Secrets live in `.env` (git-ignored). Never print, log or commit them.
- Record every significant decision in `DECISIONS.md` (context, decision, alternatives, consequences).
