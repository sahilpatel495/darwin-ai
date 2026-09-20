# Verity evaluation report

Generated 2026-09-20T17:55:44+05:30 with `openai/gpt-oss-120b`: 40 questions, 1 run(s) each. Expected answers are computed with pandas from the clean sample data, independently of the app.

## Headline

- **Accuracy: 100.0%** (40 of 40 questions correct). By split: **dev 30 of 30**, **holdout 10 of 10**.
- **Holdout accuracy: 100.0%** (10 of 10). Holdout failures are never shown to the prompt-tuning loop, so this is the number that shows the prompts were not fitted to the test.
- **Trust score: +1.00** on a scale of -1 to +1 (+1 correct, 0 declined to answer, -1 gave a wrong answer).
- Speed: half of the questions finished within 2.6 s, 95% within 4.8 s. Questions replayed from the model cache are not timed in this pass; each keeps the last timing it was measured with, which for the 30 dev questions is an earlier live pass. The challenge section below is the one set whose every timing was measured live.
- Repairs: 2.5% of questions needed the SQL to be corrected before it ran.
- Cross-check: a second model family reached the same result on 100.0% of the answers it checked in the latest pass.
- **The sentence is graded too, not only the table:** 10 of the 40 questions must name the highest (and for one, the lowest) row of the expected result in the answer text, and no clause may call a different row the highest. 0 failures of that kind in this pass. It is a separate failure class because the golden set scored 40/40 while the live app was still capable of "Engineering has the highest average salary" over a table whose top row was Support (`DECISIONS.md` 20).

## Accuracy by category

| Category | Questions | Correct | Accuracy |
|---|---|---|---|
| totals | 3 | 3 | 100.0% |
| averages | 3 | 3 | 100.0% |
| filters | 3 | 3 | 100.0% |
| comparisons | 3 | 3 | 100.0% |
| trends | 2 | 2 | 100.0% |
| joins | 3 | 3 | 100.0% |
| unions | 3 | 3 | 100.0% |
| hr_metrics | 4 | 4 | 100.0% |
| fiscal_year | 2 | 2 | 100.0% |
| fan_out_trap | 2 | 2 | 100.0% |
| null_trap | 2 | 2 | 100.0% |
| ambiguous | 2 | 2 | 100.0% |
| unanswerable | 3 | 3 | 100.0% |
| injection | 2 | 2 | 100.0% |
| non_hr | 3 | 3 | 100.0% |

## Is the confidence badge honest?

A badge is only useful if High is right more often than Medium, and Medium more often than Low.

| Badge | Questions | Accuracy |
|---|---|---|
| High | 36 | 100.0% |
| Medium | 1 | 100.0% |

3 question(s) carry no badge because the app refused, asked, or failed.

## Model comparison

| Model | Accuracy | Typical time |
|---|---|---|
| `openai/gpt-oss-120b` | 100.0% | 2.6 s |

### Which models answered

Three roles, three chains (`backend/app/config.py`). In this pass no chain failed over, so one model
filled each role for every question in both sets:

| Role | Model | Where |
|---|---|---|
| Writes the SQL | `openai/gpt-oss-120b` | Groq |
| Phrases the answer | `openai/gpt-oss-20b` | Groq |
| Cross-checks with its own SQL | `qwen/qwen3.8-27b` | Groq |

## Failures

None. Every question passed. No question ended as a provider error, so nothing was re-run.

## Reproduce

`PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --split all --runs 3`

This page was produced by one run per question, not three: the free tier's daily token budget pays
for one. Most golden SQL and most golden cross-checks replayed from `eval/.llm_cache`, because
neither prompt has changed, so that SQL is the same text an earlier pass graded. Every narration was
live: the narrator now checks its own claims, so its prompt moved and nothing it writes was in the
cache. The challenge set below was run live end to end, from an empty cache.

## Challenge set (never tuned)

16 harder questions, written after the prompts were finished and never used to change one. Run separately from the golden set. Generated 2026-09-20T18:05:43+05:30 with `openai/gpt-oss-120b`, 1 run(s) each.

- **Accuracy: 93.8%** (15 of 16 correct).
- **Trust score: +0.88** on the same scale as above (+1 correct, 0 declined to answer, -1 gave a wrong answer).
- Speed, all measured live (nothing here was in the cache): half within 3.8 s, 95% within 56.6 s. The long tail is the free tier's rate limiter, not the database: three questions waited on a token-per-minute pause.
- Repairs: 6.2% (1 of 16). Cross-check: 100.0% agreement over the answers it checked. Nothing disagreed anywhere in this pass, so the cross-check did not flag the one wrong answer.
- Calibration: High 10 of 10 correct, Medium 3 of 4, 2 refusals carry no badge. The single wrong answer was badged Medium, which is the ordering the badge promises.

### Every challenge failure

| Id | Category | Kind of failure | Question | What happened |
|---|---|---|---|---|
| ch-06 | change_over_time | wrong result | By how much did total net pay rise or fall each month against the month before, from February to December 2025? | The result does not match the expected value. Expected [(-138900.0,), (250500.0,), (629500.0,), (-19300.0,), (239700.0,), (461100.0,), (998200.0,), (-104100.0,), (288000.0,), (705100.0,), (-335100.0,)]; got [['2025-02-01', 38494200.0, None], ['2025-03-01', 38744700.0, 250500.0], ['2025-04-01', 39374200.0, 629500.0]] (11 row(s)). |

**Classified.** One failure, and its class is **date logic**, not arithmetic:

| Id | Class | What went wrong, in one line |
|---|---|---|
| ch-06 | date logic | The month filter was applied *before* the comparison, so January never entered the window and February's change came back empty. The other ten monthly changes are exact. |

The SQL filtered `pay_month BETWEEN '2025-02-01' AND '2025-12-01'` inside the CTE and then took
`LAG(total_net)` over that filtered set. The question asks for changes *from* February, which needs
January's total to subtract. Ten of the eleven numbers are right; the first one is missing.

No other class fired: no wrong column, no fan-out, no over-refusal (both refusals were the two
questions that ask for a forecast and a significance test, which this app refuses by design), no
missed refusal, and no provider error, so nothing had to be re-run.

**What the one failure says about the ceiling.** The app is reliable when a question maps to one
aggregate over one filtered range, which is most HR questions. It is not yet reliable when the
window a calculation needs is wider than the window the question names — a period boundary the
model must reason *outside* of. Nothing deterministic catches that today: the guard accepts the SQL
(it is valid), the cross-check raised nothing, and the missing number came back empty rather than
wrong, so the grounding check had nothing to object to — the sentence simply starts at March. Only
the badge behaved: it put this answer in Medium, and Medium is the only bucket holding a wrong
answer (Medium 3 of 4, High 10 of 10).

Two things this section cannot see, stated so the score is not read as more than it is:
- Challenge questions are graded on the table only. None carries a `narration:` key, so a wrong
  sentence over a right table would pass here; the golden set is where the sentence is graded.
- `ch-06` is graded as a multiset without its month labels (the time-bucket convention inherited
  from `eval/truth.py`, which `trd-01` shares), so eleven right numbers on the wrong months would
  also have passed. The grader is looser than the app here, not stricter.

These questions were written to find where it breaks.
