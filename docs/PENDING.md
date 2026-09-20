# Pending work

Rewritten 2026-09-21, after the deploy, the accounts work, the v3 "Canvas" rebuild and the MCP
endpoint. This is the honest list of what is left, in the order it matters. Nothing here stops the
app running, and the two things that used to block the submission — the deploy and the demo URL —
are done.

## Morning report, 21 September (read this first)

**State at 03:00 IST.** The v3 "Canvas" UI is merged to `main`, CI is green and it is live. Checked
on the live site after the deploy: guest sign-in, the sample company (8 tables in about 9 seconds),
ten guided analyses, and one real question end to end ("total gross pay by department in 2025":
an answer, high confidence, a bar chart, every pipeline step green). Frontend 235 tests, backend
and packaging 1,651 tests, production build clean. Keep-warm pings every 10 minutes.

**What the browser pass fixed overnight:** a guest could not sign up; a new member never saw
onboarding; a failed demo start was silent; the app bar covered the sign-in form; sideways scroll on
phones in Overview and Analyses; double focus rings on the composer and the command palette; three
"Pay" suggestions out of four; tables miscounted as files; the composer now stays docked however
long the conversation is.

**Your 45 minutes before submitting (by 11:30):**
1. Open the live link 2 minutes early (cold start), run the demo path once: landing, **Try the
   live demo**, a suggestion card, **How I got this**, Overview, Analyses, **Data**.
2. Read `WRITEUP.md`, then "Questions to expect" in `DEMO_SCRIPT.md`, then the titles in
   `DECISIONS.md`. Being able to explain it matters more than any remaining feature.
3. Take the README screenshot (an answer card with "How I got this" open, or the Overview) and
   replace `<!-- SCREENSHOT -->`; candidates are in `.worktrees/ui/.playwright-mcp/v3-*.png`.
4. Record the 3-minute video from `DEMO_SCRIPT.md` while the model quota is fresh.
5. Submit: the live link, the repo link, `WRITEUP.md`, the video.
6. Afterwards: rotate the five API keys pasted in chat, and drop the leftover `git stash` entry
   (a duplicate of committed work).

**Test data for trying it by hand:** `~/Downloads/DarwinLens-test-data/` (the sample company, the
second messy set, and eight packs with `EXPECTED.md`). What the app reads wrong in those packs is
listed in `test_files/packs/README.md`.

**Live:** <https://darwinlens.onrender.com> (Render free, Docker, Singapore region, auto-deploys
from `main`). Checked after the first deploy: `/healthz`, guest sign-in, the sample company loading
to 8 tables and 4 links in about 8 seconds, the Overview computing its 14 tiles, a JSON 404 on an
unknown route, and a 401 with `WWW-Authenticate` on `/mcp` without a token.

## 1. Needs Sahil (nobody else can do these)

1. **Fill `<!-- SCREENSHOT -->` in `README.md`.** `<!-- DEPLOY_URL -->` is done. Take the shot on
   the Overview page or on an answer card with "How I got this" open — those are the two screens
   that make the argument.
2. **Record the 3-minute video** from `DEMO_SCRIPT.md`. Warm the instance first
   (`make warm URL=https://darwinlens.onrender.com`); it sleeps after 15 idle minutes and takes
   about a minute to wake.
3. **Done: the GitHub repository variable `APP_URL`** is set to the live URL, and
   `.github/workflows/keepwarm.yml` pings `/healthz` every 10 minutes (first successful run
   01:33 IST on 21 September). GitHub runs scheduled jobs late, so a free uptime monitor on the
   same address is still worth adding.
4. **Rotate the five API keys** that were pasted into chat (Groq, OpenRouter, Hugging Face, NVIDIA,
   Gemini). After submitting, not before, or the demo goes dark.

## 2. Re-run the evaluation on the final code

Deliberately not done, and the reasons are in `DECISIONS.md` 30 and 36. `eval/REPORT.md` was
generated at **17:55 and 18:05 IST on 20 September**. Two commits after it change what the model is
sent: `0b7c556` (18:56, the combined-view follow-ups) and `df2bef1` (21:29, the batched SQL-prompt
rules). The numbers are honest about the code *at 18:00*, not about the final commit, and every
document that quotes them says so.

```
PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --split all --sleep 20 --hide-holdout-failures
PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --set challenge --sleep 20
```

Two things to know before running it. `eval/.llm_cache` holds the old SQL, so the prompt change
means most of it misses and the run costs close to a full day's free allowance — budget for that.
And `eval/REPORT.md` carries hand-added lines (the dev/holdout split, the sentence-grading line,
the "which models answered" table, the challenge classification and the ceiling paragraph) that
`eval/report.py` does not produce; a regeneration drops them and they have to go back by hand.

If the numbers move, the four places to update are `README.md` ("Results"), `WRITEUP.md`
("Honest limits"), `DECISIONS.md` (a new dated pass under "Eval iterations") and this file.

## 3. Half-finished, named rather than hidden

- **The tenth guided analysis cannot be run.** `compare` ("Compare two groups") is published by
  `backend/app/insights/analyses.py` with `group_a` and `group_b` as options carrying an **empty
  choice list** — the backend expects the picker to fill them from the chosen column's own distinct
  values, and the sentence builder renders them with nothing in them. The form's `ready` check
  looks only at inputs, so Run is enabled and the engine answers "Choose a value for "First
  group"." every time. Two ways out, in order of cost: **drop `compare` from `KINDS`** in
  `analyses.py`, which is one line and obeys the project's own rule about not shipping half a
  feature; or have `catalog()` fill the two choice lists from the column's distinct values, which
  is the real fix and needs the choices recomputed when the column picker changes. Until one of
  them is done, the documents say that nine of the ten in the picker run and name this one as
  unfinished — they do not claim nine exist, because the analyst can see ten cards. It is also
  published as a kind by `list_analyses` over MCP, with the same empty choice lists.

- **One "Verity" is left in code.** The rename (`DECISIONS.md` 31) reached the backend,
  `render.yaml` and `.env.example`; what remains is a docstring in `demo_data/test_demo_data.py`
  and the v2 frontend under `frontend/src/`, which the v3 merge replaces wholesale. After the merge,
  grep once more and fix the docstring. `eval/REPORT.md` still says Verity on purpose: it is a
  generated measurement artifact, re-written by the next `make eval` rather than edited by hand.

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
  `from_clause` and refuse with the sentence the picker already knows how to show. This reaches
  agents too, through the `run_analysis` MCP tool.
- **The challenge set is graded on the table only.** No case carries `expect.narration`, so a
  wrong sentence over a right table passes there; and a time-bucket answer is compared as a
  multiset without its labels, so right numbers on wrong months would pass. Both are `eval/`
  work, not app work.
- **One run per question, not three.** The daily free-tier token budget pays for one. `--runs 3`
  is what the design asks for and what a paid key would buy. See `DECISIONS.md` 30.

## 5. Open security and operations notes

- **`TRUSTED_PROXY_HOPS` has to be verified against Render's real header.** It defaults to `1`,
  meaning the nearest proxy appended the client's address to `X-Forwarded-For`, and
  `limits.client_ip` counts from the right. One hop too many and every visitor can pick their own
  identity by writing the header; one too few and every visitor shares Render's router address and
  the per-IP limits become one global limit. Now that the service is live, check the header it
  actually sends and set the variable if it is not 1. This is the only limit setting that is
  wrong-by-default-if-guessed. The per-user limits added with accounts reduce the blast radius but
  do not replace it, because a guest account costs one POST.
- **Accounts do not survive a redeploy.** `app.auth` is one SQLite file on the instance's disk
  (`DECISIONS.md` 34), so every push to `main` signs everybody out and loses their sign-up. The
  guest path is unaffected, which is why the demo instructions use it. Postgres is step one of the
  scaling path in `docs/CAPACITY.md`.
- **Tokens cannot be revoked.** They are stateless HMACs valid for 7 days; `POST /api/auth/logout`
  is the browser forgetting one. The fix is a revocation table keyed by user id.
- **The preview, catalog and insights routes are unmetered.** `GET /tables/{name}/preview`,
  `GET /catalog`, `GET /dashboard`, `GET /analyses` and `POST /analyses/run` spend no model
  tokens, which is why they are outside the question budget, but they are inside *no* limit
  either — confirmed again by the load test (`docs/CAPACITY.md`). `POST /analyses/run` is a DuckDB
  query with a 10 s timeout, so a loop over it is free CPU on a 0.1-CPU instance. A per-IP window
  on `analyses/run` and `preview`, sized in seconds rather than hours, is the small version; the
  proxy is the real one. The five no-model MCP tools are on the same footing.
- **`MAX_SESSIONS=12` is the measured ceiling**, and the thirteenth concurrent analyst evicts the
  least recently used session, whose owner meets the app's human 404. `SESSIONS_PER_IP_PER_HOUR=5`
  on Render is what stops one address emptying the store. Numbers in `docs/CAPACITY.md`.

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
- **The v2 storage-key migration is one-way and temporary.** `lib/projects.ts` moves
  `verity.projects.v1` to `darwinlens.projects.v1.<user id>` once. Delete it after it has had a
  release to run.

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
- ~~The stores-to-staff link is not offered~~ (finding 14) — **fixed**:
  `relationships._is_manager_link` lets a `manager_id` meet an `employee_id` when the employee
  side is unique, as a *suggested* link only. `test_files/README.md` still lists it as open;
  that file is owned by whoever owns `test_files/` and has not been regenerated since.
- **Span of control cannot be computed from these files** (finding 15) and now says so, which is
  the right answer: no file in that set records who reports to whom.

## 8. The next features, not today's work

MCP has shipped (`docs/MCP.md`, `DECISIONS.md` 35), so it is no longer on this list. What replaces
it, in the order `WRITEUP.md` names them:

1. **Durable storage.** Postgres for accounts, Redis plus a DuckDB file per session for the rest.
   This is the one that unlocks a second worker, and the measured order of the ceilings is in
   `docs/CAPACITY.md`.
2. **Per-customer metric dictionaries.** Today the glossary, the column synonyms and the PII
   patterns are three Python files. As config, `describe_data` hands a calling agent exactly how
   that customer defines attrition, and the conversation it forces is most of week one.
3. **SSE on `/mcp`.** Every tool answers inside its own POST today, so a long `ask` is silent until
   it returns. The browser already gets its steps streamed; an agent should too.

## Deliberately not planned

Single sign-on, roles, teams, sharing, scheduled reports, and server-side storage of customer
files. Reasons in `DECISIONS.md` 18 and 34; accounts answer "whose session is this?" and nothing
more. Dark mode was built with the Clarity token layer and dropped again in v3, which is light only
(`DECISIONS.md` 33).
