# Pending work

Written 2026-09-20. Everything here is specified and ready to pick up; none of it blocks a working demo.

## Must do before submitting (needs Sahil)
1. **Deploy on Render** (free): follow "Deploy in 5 minutes" in `README.md`. Paste the five keys from `.env` into Render's environment form. Then `make warm URL=https://<app>.onrender.com` and set the GitHub repository variable `APP_URL` so the keep-warm Action runs.
2. **Fill the markers**: `<!-- EVAL -->`, `<!-- SCREENSHOT -->`, `<!-- DEPLOY_URL -->` in `README.md` and `WRITEUP.md` (numbers are in `eval/REPORT.md`).
3. **Record the 3-minute video** from `DEMO_SCRIPT.md`.
4. **Rotate the API keys** that were pasted into chat (Groq, OpenRouter, Hugging Face, NVIDIA, Gemini) after submitting.

## Correctness (highest value next)
- ~~Narration claims~~ **Done 2026-09-20**: the narrator is given computed facts (highest, lowest, first, last), every ranking word and label-number pairing in the sentence is checked against the result, a wrong claim is corrected once and otherwise replaced by a rank-aware template (`backend/app/query/narrator.py`, 24 tests in `backend/tests/present/test_claims.py`). Still to do: grade the sentence in the eval so a regression is caught there too.
- **Cross-check false alarm on rounding**: `results_equivalent` treats `ROUND(AVG(x), 2)` vs the unrounded value as a disagreement and badges a correct answer Low. Fix in `backend/app/query/verify.py`: equal when one is the other rounded to the coarser value's 1–4 decimals.
- **A named period the SQL ignores** ("total pay in 2025" on a multi-year register with no date filter). Add `period_risks()` in `verify.py`, wire like the fan-out check.
- **Grade the sentence in the eval** and add a harder, never-tuned **challenge set** (16 questions) so the report shows real failures; 40/40 on one synthetic dataset is a regression bar, not proof.
- After the analyst picks a clarification, a fallback model can ask the same question again: regenerate once with the choice stated, then give up with a sentence.

## Product (specified in `docs/DESIGN_SYSTEM.md`, fonts already in `frontend/public/fonts`)
- The **"Ledger" UI revamp**: answer as an audited statement (serif figure, double rule, auditor's ticks), ruled rows instead of cards, tabbed sidebar, the "Here's what I found in your files" briefing.
- **Whole-app journey, local-first**: home with projects, history restored from the browser, saved-answers board with print to PDF, the re-attach flow when the server has dropped the data.
- **Learning the product**: first-run tour, "How Verity works" dialog, "What's this?" on every trust signal.
- Retry countdown on a busy-model error (`Answer.retry_after_s` is already sent by the API).

## Security and operations (from the security review, with patches in the hardening report)
- Failover pool and per-user limits were built but their independent review was cut short: review `backend/app/llm/client.py` and `backend/app/limits.py`.
- Close sessions outside the store-wide lock (`SessionStore._drop` holds the lock while DuckDB waits for a running query).
- One ingest at a time (parsing is the memory peak on a 512 MB host).
- `TRUSTED_PROXY_HOPS` setting: verify on Render which `X-Forwarded-For` entry is the client.
- `--no-access-log` in the Dockerfile `CMD` (the session id is in the URL path).
- Wire `pnpm test` (81 frontend unit tests) into the Makefile and CI.
- `EmpNo` is not recognised as an employee id (`backend/app/profile/roles.py`).

## Deliberately not planned
Accounts, server-side storage of customer files, teams, sharing, scheduled reports, dark mode. Reasons in `DECISIONS.md` 18.
