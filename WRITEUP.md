# DarwinLens: one-page write-up

Sahil Patel · Forward Deployed Engineer take-home · demo: <!-- DEPLOY_URL -->

**How I read the brief.** "Delta solutioning on top of what AI does": any chat model already
attempts questions over a spreadsheet, badly. I read the delta as the engineering between a
model's first plausible answer and one a customer can act on. Real HR exports have title rows,
"Grand Total" footers, `₹1,20,000` typed as text, codes that lose their leading zeros, and PII;
"attrition" and "salary" have contested meanings. A raw model fails on all of it quietly, and
quiet is the expensive part.

**The thesis.** The model never computes a number and never sees a row. It writes SQL from column
names, statistics and short category labels. DuckDB computes. Deterministic code checks the SQL
before it runs and the wording after. The screen shows the work.

## Five decisions and what each cost

1. **SQL, not model-written Python.** Exec-based agents have a record of RCE CVEs; SQL can be
   parsed and allow-listed. *Cost:* no statistics or forecasting — those refuse.
2. **Schema-only prompts through one function,** so "no PII in prompts" is a test with planted
   canary values. *Cost:* weaker SQL than with sample rows; sending real values for small non-PII
   columns buys some back (the model writes `Bengaluru`, not `Bangalore`).
3. **Rules choose the chart; the model copies pre-formatted numbers, and its claims are checked** —
   a ranking word may only sit beside the row that earns it. *Cost:* duller prose.
4. **Cross-check as a confidence signal, not a vote.** *Cost:* a second call per question, and
   agreement is evidence, not proof.
5. **Strictly $0** — failover with per-model cooldowns, token pacing, a bounded wait. *Cost:* a
   slow tuning loop and, in the end, an evaluation I could not afford to re-run.

## The scope grew, and the rule that kept it honest

One screen became six: Home with local-first projects, Ask, an automatic Overview, guided
Analyses, a printable Saved board, Trust. The rule was that `main` stayed deployable all day, risky
work ran in a git worktree, and anything not finished and tested was **removed, not shipped
half-working**. That rule is why this page can name the one thing that slipped past it: the tenth
guided analysis is published but cannot be run, so the docs name it rather than count it.

This sits in tension with the brief's "a smaller app beats a sprawling one", and I won't pretend
otherwise — an evening went on replacing a finished visual direction, and the eval re-run is what
paid for it. What it bought is the strongest evidence I have for the thesis: Overview and Analyses
produce real numbers — 14 tiles in about 66 ms — with **no model in the loop**, through the same
guard, executor and formatter as a model-written query. The half that needs no AI is the best
argument that the AI is not doing the arithmetic.

**What I cut.** Login, persistence, other databases, `.xls`, wide attendance musters, small-group
salary suppression, and the grouping row of a two-row header (the key survives; the labels don't).
Time went to ingestion, privacy, verification and measurement.

## Results, and what they do not cover

**Golden set 40/40** (dev 30/30, holdout 10/10), trust +1.00, cross-check agreement 100%; ten of
the forty are graded on the *sentence* as well as the table, and none failed. **Challenge set
15/16** — sixteen harder questions written after the prompts were frozen and never used to tune
one. The single failure is date logic: a window narrower than the calculation needed. That set is
also where calibration is provable, because nothing in the golden set is wrong: High 10/10,
Medium 3/4, and the wrong answer is the Medium.

**Measured at 17:55 and 18:05 IST on 20 September with `openai/gpt-oss-120b` — before two later
changes to what the model is sent (commits `0b7c556`, `df2bef1`), so not on the final commit.** I
started the re-run twice and it couldn't finish: Groq's daily allowance was spent and Google's
Gemma endpoint was taking minutes per call. It runs this morning. The lesson generalises: a $0
constraint buys engineering, not evaluation — failover kept the *app* up and bought none of the
tokens an eval needs on demand. [`eval/REPORT.md`](eval/REPORT.md).

## How I used AI to build it

Claude Code led parallel subagents. I set the thesis, scope, constraints and cuts, and approved the
spec before any code existed. **Contracts first** — every shared type, plus the one function
allowed to describe data to a model — then builders owned disjoint files against them, each
followed by an **independent reviewer told not to trust the builder's report**. Correctness came
from loops, not prompts: an eval loop that never saw holdout failures, and a hardening loop with
fixed lenses.

Three times a reviewer or a second, never-tuned file set proved the happy numbers wrong — each
having passed every check that existed at the time:

- an answer said "Engineering has the highest average salary" when the top row was Support, **under
  a High, cross-checked badge**: every number was genuine, and the eval graded the table;
- a **6.3% undercount** on pay by region, because links were detected between tables and a combined
  view is not a table, so everyone who had left was silently missing;
- a **PII alias leak**: a combined view's `source_file` column held uploaded file names, which are
  then offered to the model as filter values. The prompt builder had only been audited for what it
  *reads*.

Each time, the test and the bug shared an assumption. [`docs/AI_WORKFLOW.md`](docs/AI_WORKFLOW.md).

## What I would build next, as an FDE at a customer

**An MCP tool over this engine** — `answer_question` already takes its session and model client as
arguments, so MCP is a second transport, not a second implementation. For a company shipping an HCM
MCP server, its agents would answer with *that customer's* signed-off definition of attrition and a
SQL trail anyone can check. Then **per-customer metric dictionaries as config** (today the
glossary, column synonyms and PII patterns are three Python files — and the conversation they force
is most of week one), and **a payroll variance explainer** before payroll lock: this month against
last, each difference traced to a cause.
