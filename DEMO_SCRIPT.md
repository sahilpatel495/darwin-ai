# Demo script (3 minutes)

One idea to land: **the model never computes a number and never sees a row, and everything it says
can be checked on screen.** Two things prove it: the answer card you can open down to the prompt,
and a whole half of the app that produces numbers with no model at all.

**Before recording.** Record at 1280×800, browser zoom 110%, light theme. Warm the app
(`make warm URL=...`) so the six starter questions are already in the answer cache and nothing
waits on a cold start. Open the link a minute early. Have a second tab on the Overview page as an
escape hatch. Skip the first-run tour off camera, or take it — it is six steps and reads well, but
it does not fit in three minutes.

| Time | Do | Say |
|---|---|---|
| 0:00 | Home, with the nav rail on the left. Hover the rail: Home, Ask, Overview, Analyses, Saved, Trust. | "A raw LLM over a spreadsheet gives confident wrong numbers and ships your data to a third party. For HR that is a non-starter. DarwinLens is what I built around the model. It is not a chat box — six screens, and two of them never call a model at all." |
| 0:12 | On the sample card click **See what's inside**, scroll the file list for two seconds, then **Load this data**. | "Before you trust it with your own files, look at its files. Six spreadsheets from a company that does not exist, messy on purpose — merged title rows, a Grand Total footer, rupee strings, duplicate payslips. You can download them and check my homework." |
| 0:25 | The workspace opens on the briefing: **"Here's what I found in your files"**. Point at the subtitle. | "Straight away, before any question: four things it found. Read the subtitle — *counted while your files were read, no AI was involved in any of it.*" |
| 0:35 | Open the sidebar **Files** tab, expand `Salary_Register_2025.xlsx`. | "This is the receipt. Three title rows skipped, one Grand Total row dropped — that row double-counts if you sum it. Rupee strings read as money. Employee codes kept as text, so `004512` stays `004512`. Name, email, phone and PAN flagged as personal data and hidden from the model." |
| 0:50 | Nav rail → **Overview**. Point at the line under the title. | "Fourteen tiles, computed the moment the files landed. *Computed from your files. No AI involved.* Headcount, attrition with the definition it used, pay by month, the CTC spread — about seventy milliseconds, and the same fourteen every time. This is the half that still works when every free model is rate limited." |
| 1:05 | On one tile open the menu → **View table and SQL**. | "Every tile shows its rows and the query that produced them. Same guard, same database, same formatter as an answer, so a number here and the same number in the chat cannot disagree." |
| 1:15 | Nav rail → **Analyses**. Pick **Break down**, choose a measure and a group, watch the preview sentence, **Run this analysis**. | "And if you would rather not type a question: pick the columns. *No AI needed — you choose the columns, the database does the rest.* You see the sentence before you run it, and the SQL after." |
| 1:30 | Nav rail → **Ask**. Click the starter question **"What was the total gross pay by department in 2025?"**. Let the thinking card run. | "Now the model. Watch the steps: it writes the query, a parser guard checks it is one read-only SELECT over known tables, DuckDB runs it, and a second model from a different family writes its own query in parallel." |
| 1:45 | The answer card arrives. Point at the badge, the green ticks, the insight chips. | "The headline, the confidence badge with its reasons, and the checks: computed by a database, cross-checked by a second model, no rows or personal data sent. The chips under it — 'the top three make up 72%' — are computed from the rows, not written by the model." |
| 1:55 | Use the **Show the result as** control: bar → donut → table. | "Charts are chosen by rules, never by the model, and I can switch." |
| 2:05 | Open **How I got this**. Point at the flow strip, then scroll to **What the model saw**. | "The flow: question, query written, safety check, my data, second model, answer. Then the plan, the SQL, the attempts — and this is the one that matters. *What the model saw.* Column names, types, statistics and short category lists. No rows. A test plants fake PII and fails the build if it ever appears here." |
| 2:25 | Ask **"What is the average salary by department?"** — the clarify chips appear. Click the CTC option. | "'Salary' could be CTC, gross or net. It does not guess, and this check is rule-based, so it costs no model call. Once I answer, it never asks me again." |
| 2:40 | Ask **"What will our attrition rate be next quarter?"** (refusal — this is golden question `una-03`, so it is graded to refuse). | "It refuses and says what it would need. No forecasting, no statistical tests — because running model-written code is how comparable tools got remote-code-execution CVEs. No answer beats a wrong one." |
| 2:50 | Save an answer, then nav rail → **Saved**, and hover **Print or save as PDF**. | "Answers and tiles collect into a board that prints as a report — the thing an analyst actually has to hand their CHRO." |
| 2:58 | Nav rail → **Trust**. | "And the numbers: forty golden questions with truth computed in pandas before I inject the mess, ten of them held out from tuning, plus sixteen harder ones written after the prompts were frozen. Every failure listed. What I would build next is an MCP tool over this same engine, so a company's agents answer with each customer's own definition of attrition." |

## Two honesty lines to say out loud

Say both. They land better than the scores do.

- **On the numbers:** "These were measured at six in the evening, before two later prompt changes.
  The re-run ran out of free quota and is scheduled for the morning. I would rather show you a
  number with its timestamp than one that looks cleaner."
- **On the ceiling:** "One challenge question failed, and it is the honest kind: a month-on-month
  change filtered the months *before* differencing, so the first change came back empty. Valid
  SQL, the cross-check agreed, an empty cell is not a wrong number. Only the confidence badge
  noticed — and it did not call it High."

## If something goes wrong on camera

- **A model is rate limited.** The app says so in one sentence with a wait time. Do not wait on
  camera — move to **Overview** or **Analyses**. Neither calls a model, so both work with the
  quota completely gone, and that is a better demo of the thesis than the answer you lost.
- **A question hangs.** The six starter questions are cached after the first ask (and pre-warmed
  by `make warm`), so re-asking one is instant. The clarify chips and the refusal cost no model
  call either.
- **Cold start on the free host.** The instance sleeps after 15 idle minutes and takes about a
  minute to wake. Open the link before you start recording.
- **The Trust Report says no report has been run.** `eval/report.json` was not in the image.
  Show [`eval/REPORT.md`](eval/REPORT.md) in the repo instead.
- **Running out of time.** Cut in this order: the guided analysis (1:15), the chart switch (1:55),
  the Saved board (2:50). Never cut "What the model saw" or the refusal.

## Questions to expect

- *Why SQL and not pandas code?* RCE CVEs in every exec-based agent. SQL can be parsed and
  allow-listed, and the allow-list is tested against a hostile-query corpus.
- *What if the second model is also wrong?* Agreement is evidence, not proof. That is why it feeds
  confidence rather than overriding the answer, and why calibration is measured.
- *Your golden set scores 100% — isn't that overfitting?* Partly, yes, and I say so: the prompts
  were tuned against its dev failures. That is what the ten-question holdout and the never-tuned
  challenge set are for, and the challenge set is where the badge is shown to rank correctly.
- *What caught a wrong answer that your tests did not?* Three things, all after the tests were
  green: a sentence that named the wrong department as highest with every number genuine; a 6.3%
  undercount because links were detected to tables and not to a combined view; and file names
  reaching a prompt through that view's `source_file` column. Each is in `DECISIONS.md`.
- *Does this scale?* One process with in-memory sessions today, deliberately. Path: session state
  to Redis or object storage, a DuckDB file per session, the limiter to the proxy, model calls
  behind a queue. None of it changes the pipeline.
- *Why gpt-oss?* Apache-2.0 open weights served by Groq — not the GPT API, and no request goes to
  OpenAI. Every runtime model is open-weight, and the eval picked this one.
- *What is not finished?* `docs/PENDING.md`, and I will show it: the eval re-run, the tenth guided
  analysis that reaches the picker but cannot be run, a guided cross-file sum that should refuse
  rather than caveat, and `TRUSTED_PROXY_HOPS` to verify on the host.
