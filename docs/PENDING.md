# Pending work

Rewritten 2026-09-20, 23:00 IST, after the day's second half (the no-AI screens, the Clarity
redesign, the correctness and catalog fixes). This is the honest list of what is left, in the
order it matters. Nothing here stops the app running; two things stop the *submission* being
complete, and they are first.

## 1. Needs Sahil (nobody else can do these)

1. **Deploy on Render.** Follow "Deploy in 5 minutes" in `README.md`. `render.yaml` is written
   and needs no editing. Paste the keys from `.env` into Render's form (it asks for
   `GROQ_API_KEY`, `NVIDIA_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`; one is enough).
   Then `make warm URL=https://<app>.onrender.com` and set the GitHub repository variable
   `APP_URL` so `.github/workflows/keepwarm.yml` starts pinging.
2. **Fill the two markers.** `<!-- SCREENSHOT -->` and `<!-- DEPLOY_URL -->` in `README.md`, and
   `<!-- DEPLOY_URL -->` in `WRITEUP.md`. Take the screenshot on the Overview page or on an
   answer card with "How I got this" open — those are the two screens that make the argument.
3. **Record the 3-minute video** from `DEMO_SCRIPT.md`.
4. **Rotate the five API keys** that were pasted into chat today (Groq, OpenRouter, Hugging
   Face, NVIDIA, Gemini). Do it after submitting, not before, or the demo goes dark.

## 2. Re-run the evaluation on the final code

`eval/REPORT.md` was generated at **17:55 and 18:05 IST**. Two commits after it change what the
model is sent: `0b7c556` (18:56, the combined-view follow-ups) and `df2bef1` (21:29, the batched
SQL-prompt rules). The numbers are therefore honest about the code *at 18:00*, not about the
final commit, and every document that quotes them says so.

A re-run was started twice tonight and finished neither time: Groq's daily free allowance was
spent and Google's Gemma endpoint was taking minutes per call. Scheduled for the morning:

```
PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --split all --sleep 20 --hide-holdout-failures
PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --set challenge --sleep 20
```

Two things to know before running it. `eval/.llm_cache` holds the old SQL, so the prompt change
means most of it misses and the run costs close to a full day's allowance — budget for that.
And `eval/REPORT.md` carries hand-added lines (the dev/holdout split, the sentence-grading line,
the "which models answered" table, the challenge classification and the ceiling paragraph) that
`eval/report.py` does not produce; a regeneration drops them and they have to go back by hand.

If the numbers move, the four places to update are `README.md` ("Results"), `WRITEUP.md`
("Results"), `DECISIONS.md` (a new dated pass under "Eval iterations") and this file.

## 3. Half-finished, decide before submitting

- **The tenth guided analysis cannot be run.** `compare` ("Compare two groups") is published by
  `backend/app/insights/analyses.py` with `group_a` and `group_b` as options carrying an **empty
  choice list** — the backend expects the UI to fill them from the chosen column's own distinct
  values, and `AnalysisForm.tsx` renders them as two segmented controls with nothing in them.
  The form's `ready` check looks only at inputs, so Run is enabled and the engine answers
  "Choose a value for "First group"." every time. It also has no icon of its own
  (`kindIcons.tsx` falls back to a generic chart glyph) and no preview sentence
  (`form.ts` falls back to `"<kind name>: <columns>"`).
  Two ways out, in order of cost: **drop `compare` from `KINDS`** in `analyses.py`, which is one
  line and obeys the project's own rule about not shipping half a feature; or have `catalog()`
  fill the two choice lists from the column's distinct values, which is the real fix and needs
  the choices recomputed when the column picker changes. Until one of them is done, the documents
  say that nine of the ten in the picker run and name this one as unfinished — they do not claim
  nine exist, because the analyst can see ten cards.

- **Four files still say "Verity".** The rename to DarwinLens (`DECISIONS.md` 31) skipped the
  files that were being edited for accounts at the time, so the old name survives in
  `backend/app/main.py` (the FastAPI `title=` and `logging.getLogger("verity")`, plus one error
  sentence), `backend/app/config.py` (the `WORK_DIR` default `/tmp/verity`, which `auth_db_path`
  builds on — the Dockerfile already sets `/tmp/darwinlens`), `render.yaml` (`name: verity`, which
  `README.md` step 6 already calls `darwinlens`) and `.env.example` (the header line and the two
  `/tmp/verity` comments). `backend/app/auth.py`'s docstrings mention both the old storage-key
  prefix and `/tmp/verity`. None of it changes behaviour; all of it is visible to a reader. Do it
  in one pass when the accounts work lands, and re-run `uv run pytest backend/tests .github/scripts`.

## 4. Correctness (highest value next)

- **A window wider than the question's period.** The one challenge-set failure (`ch-06`). The
  prompt now says to compute a neighbouring-row calculation over the whole series and filter
  afterwards, but nothing deterministic checks it: valid SQL, an empty first row, a silent
  cross-check. The shape of the fix is a `verify.py` rule for a window function whose frame is
  narrowed by the same filter the question named, wired like `fan_out_risks` and `period_risks`.
- **A guided cross-file sum can still double-count.** `insights/sqlbuild.from_clause` refuses an
  N:M link and a missing link, but a 1:N join is allowed, so summing a measure from the *one*
  side (each employee's CTC against their payslips) repeats it once per child row. The chat path
  catches this — `verify.fan_out_risks` runs in `runner.run_tile` and adds a caveat — but a
  caveat under a wrong total is weaker than a refusal, and the guided path is the one where the
  analyst did not choose the join. The fix is to check the same fan-out condition in
  `from_clause` and refuse with the sentence the picker already knows how to show.
- **The challenge set is graded on the table only.** No case carries `expect.narration`, so a
  wrong sentence over a right table passes there; and a time-bucket answer is compared as a
  multiset without its labels, so right numbers on wrong months would pass. Both are `eval/`
  work, not app work.
- **One run per question, not three.** The daily free-tier token budget pays for one. `--runs 3`
  is what the design asks for and what a paid key would buy. See `DECISIONS.md` 30.

## 5. Open security and operations notes

- **`TRUSTED_PROXY_HOPS` has to be verified on Render.** It defaults to `1`, meaning the nearest
  proxy appended the client's address to `X-Forwarded-For`, and `limits.client_ip` counts from
  the right. One hop too many and every visitor can pick their own identity by writing the
  header; one too few and every visitor shares Render's router address and the per-IP limits
  become one global limit. After the first deploy, check the header Render actually sends and
  set the variable if it is not 1. This is the only limit setting that is wrong-by-default-if-guessed.
- **The preview, catalog and insights routes are unmetered.** `GET /tables/{name}/preview`,
  `GET /catalog`, `GET /dashboard`, `GET /analyses` and `POST /analyses/run` spend no model
  tokens, which is why they are outside the question budget, but they are inside *no* limit
  either. `POST /analyses/run` is a DuckDB query with a 10 s timeout, so a loop over it is free
  CPU on a 0.1-CPU instance. The upload and session limits are the only thing in front of them
  today. A per-IP window on `analyses/run` and `preview`, sized in seconds rather than hours, is
  the small version; the proxy is the real one.
- **No authentication at all.** Stated in the README as deliberate. The session id in the URL is
  the only credential, and anyone with it can read that session until it expires.

## 6. Queued polish (small, visible, none of it blocking)

- **Month labels read "01 Jan 2025".** A month bucket is `date_trunc('month', …)`, so it is a
  date, and `presentation.to_display` formats a date as `%d %b %Y`. On a monthly axis the day is
  noise and slightly wrong. The fix is a `month` value kind that formats `Jan 2025`, set where
  `date_bucket(…, 'month')` names a column, in `presentation.py` and `insights/sqlbuild.py`.
- **Analysis titles are title-cased.** `analyses._phrase` builds a title from the file's own
  header text (`Annual CTC`, `Gross Pay`), so titles come out "Total Gross Pay by Department"
  while `docs/DESIGN_SYSTEM.md` §3 asks for sentence case everywhere. Lower-casing a header is
  not safe in general (CTC, LOP, PF), so the fix is a small rule: lower-case a word only when it
  is longer than three characters and not all-capitals.
- **Cross-file attendance is not offered in the guided path.** `analyses.catalog` leaves union
  views out so a column is not listed three times, which also means "days present across both
  quarters" has to be asked in the chat. The `ponytail:` comment in `catalog()` names the
  upgrade: offer the view and drop the member tables' duplicated columns.
- **The saved board orders answers and tiles separately**, so a tile cannot be moved above an
  answer (`board/order.ts`). Fine for a report; worth one line if anyone asks.
- **Stored history is capped** at 60 turns per project, 24 saved tiles and 200 rows per stored
  table, and a quota error drops the oldest half of the biggest project's turns. The
  `ponytail:` comment in `lib/projects.ts` names IndexedDB as the upgrade.

## 7. Catalog (known, measured, not guessed)

These come from pushing `test_files/` through ingest with no model in the loop. That file's
"Still wrong" section is the long version; two of its five entries have since been fixed.

- **Punch times stay text.** `2025-01-02 09:14:23` is not a date and there is no time type, so
  the gap between two swipes cannot be computed in SQL. Only the pre-computed `Hours Worked`
  column can answer an hours question. Fixing it means a new `ColumnType` in `contracts.py` and
  in every module that maps types to DuckDB, formatting and charts.
- **A `values:` list that is empty because everything was dropped** reads to the model like an
  empty column (`test_files` finding 12: a free-text `Remarks` column whose twelve values are
  all too long to send). Suppressing the `values:` part when nothing survives is one line in
  `prompt_context.py`.
- **Every table keyed on `EmpNo` is linked to every other one** (finding 13): eleven links where
  a person would draw eight. A direct link between two fact tables is dropped only when it is
  N:M, and a one-row-per-employee sheet is 1:N to everything. Doing it properly means ranking
  candidate masters by key coverage and by whether their key is itself a foreign key. Nothing
  here is false, and the one dangerous link is on by default.
- ~~The stores-to-staff link is not offered~~ (finding 14) — **fixed** this evening:
  `relationships._is_manager_link` lets a `manager_id` meet an `employee_id` when the employee
  side is unique, as a *suggested* link only. `test_files/README.md` still lists it as open;
  that file is owned by whoever owns `test_files/` and has not been regenerated since.
- **Span of control cannot be computed from these files** (finding 15) and now says so, which is
  the right answer: no file in that set records who reports to whom.

## 8. The next feature, not today's work

**An MCP endpoint over the same engine.** The pipeline already takes a session and a model
client as arguments (`answer_question(session, req, llm, emit)`), so an MCP server is a second
transport over it, not a second engine: `ask`, `overview` and `run_analysis` as tools, the same
guard and the same catalog. It is the first thing named in `WRITEUP.md` as what comes next,
because a company that already ships an HCM MCP server gets its agents answering with each
customer's vetted metric definitions instead of a fresh guess per call.

## Deliberately not planned

Accounts, server-side storage of customer files, teams, sharing, scheduled reports. Reasons in
`DECISIONS.md` 18. (Dark mode was on this list and came free with the Clarity token layer;
`DECISIONS.md` 26.)
