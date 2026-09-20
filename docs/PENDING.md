# Pending work

Written 2026-09-20, revised after the final evaluation pass. Everything here is specified and
ready to pick up; none of it blocks a working demo.

## Must do before submitting (needs Sahil)
1. **Deploy on Render** (free): follow "Deploy in 5 minutes" in `README.md`. Paste the five keys from `.env` into Render's environment form. Then `make warm URL=https://<app>.onrender.com` and set the GitHub repository variable `APP_URL` so the keep-warm Action runs.
2. **Fill the two markers that are left**: `<!-- SCREENSHOT -->` and `<!-- DEPLOY_URL -->` in `README.md`, `<!-- DEPLOY_URL -->` in `WRITEUP.md`. The `<!-- EVAL -->` marker is gone: both files now carry the measured numbers, which come from `eval/REPORT.md`.
3. **Record the 3-minute video** from `DEMO_SCRIPT.md`.
4. **Rotate the API keys** that were pasted into chat (Groq, OpenRouter, Hugging Face, NVIDIA, Gemini) after submitting.

## Done today
- ~~Narration claims~~ the narrator is handed computed facts, every ranking word and label-number pairing is checked, a wrong claim is corrected once and then replaced by a rank-aware template (`backend/app/query/narrator.py`).
- ~~Cross-check false alarm on rounding~~ `results_equivalent` now compares at the coarser value's decimal places, so `ROUND(AVG(x), 2)` against the unrounded value is agreement (`backend/app/query/verify.py`).
- ~~A named period the SQL ignores~~ `period_risks()` is in `verify.py` and wired into the pipeline, with one repair attempt and a caveat if the second query still has no date filter.
- ~~Grade the sentence in the eval~~ ten golden questions carry `expect.narration`; a right table under a wrong sentence is its own failure class in the report.
- ~~A harder, never-tuned challenge set~~ sixteen questions in `eval/challenge.yaml`, scored separately, every failure listed and classified.
- ~~Clarification asked twice~~ a fallback model that re-asks a settled choice is told the choice once more and then gives up with a sentence (`pipeline.py`).
- ~~Failover pool and per-user limits review~~ per-model cooldowns from the provider's own hints, token pacing, a bounded wait with a visible retry step, and per-IP hourly/daily/session/upload/concurrency caps.
- ~~Security and operations patches~~ sessions are closed outside the store lock, one ingest at a time (`limits._ingest_slot`), `TRUSTED_PROXY_HOPS` is a setting, `--no-access-log` is in the Dockerfile `CMD`, `pnpm test` runs in the Makefile and in CI, and `EmpNo`/`Manager EmpNo` are recognised as ids.
- ~~Catalog fixes~~ a combined view's `source_file` names the member table, same-schema grouping splits on type instead of failing whole, an empty column no longer satisfies a metric, every role of a metric binds from one table, spellings fold only on case and whitespace runs, and a `manager_id` may now meet a unique `employee_id` as a suggested link.

## Correctness (highest value next)
- **A window wider than the question's period.** The prompt now says to compute a neighbouring-row calculation over the whole series and filter afterwards, but nothing deterministic checks it: valid SQL, an empty first row and a silent cross-check. The shape of the fix is a `verify.py` rule for a window function whose frame is narrowed by the same filter the question named, wired like `fan_out_risks` and `period_risks`.
- **The challenge set is graded on the table only.** No case carries `expect.narration`, so a wrong sentence over a right table passes there; and a time-bucket answer is compared as a multiset without its labels, so right numbers on wrong months would pass. Both are `eval/` work, not app work.
- **One run per question, not three.** The daily free-tier token budget pays for one pass. `--runs 3` is what the design asks for and what a paid key would buy.

## Catalog (known, measured, not guessed)
- **Every table keyed on `EmpNo` is linked to every other one** (`test_files/README.md` finding 13): eleven links where a person would draw eight. A direct link between two fact tables is dropped only when it is N:M, and a one-row-per-employee sheet is 1:N to everything. Doing it properly means ranking candidate masters by key coverage and by whether their key is itself a foreign key.
- **Punch times stay text.** `2025-01-02 09:14:23` is not a date and there is no time type, so the gap between two swipes cannot be computed. Fixing it means a new `ColumnType` in `contracts.py` and in every module that maps types.
- **A `values:` list that is empty because everything was dropped** reads like an empty column. Suppressing the `values:` part when nothing survives is one line in `prompt_context.py`.

## Product (specified in `docs/DESIGN_SYSTEM.md`, fonts already in `frontend/public/fonts`)
- The **"Ledger" UI revamp**: answer as an audited statement (serif figure, double rule, auditor's ticks), ruled rows instead of cards, tabbed sidebar, the "Here's what I found in your files" briefing.
- **Whole-app journey, local-first**: home with projects, history restored from the browser, saved-answers board with print to PDF, the re-attach flow when the server has dropped the data.
- **Learning the product**: first-run tour, "How Verity works" dialog, "What's this?" on every trust signal.
- Retry countdown on a busy-model error (`Answer.retry_after_s` is already sent by the API).

## Deliberately not planned
Accounts, server-side storage of customer files, teams, sharing, scheduled reports, dark mode. Reasons in `DECISIONS.md` 18.
