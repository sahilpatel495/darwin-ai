# Demo script (3 minutes)

One idea to land: **the model never computes a number and never sees a row, and everything it says
can be checked on screen.** Two things prove it: the answer card you can open down to the prompt,
and a whole half of the app that produces numbers with no model at all.

**Before recording.** Record at 1280×800, browser zoom 110%. The app is light only, so there is no
theme to set. Warm it first: `make warm URL=https://darwinlens.onrender.com`. The free instance
sleeps after 15 idle minutes and takes about a minute to wake, so open
<https://darwinlens.onrender.com> a couple of minutes early and leave the tab up. Keep a second tab
on the Overview page as an escape hatch. You do not need to sign in: **Try the live demo** makes a
guest account and loads the sample company in one press.

| Time | Do | Say |
|---|---|---|
| 0:00 | The landing page. Headline **"Ask your spreadsheets. Verify every answer."** Point at the dark strip along the top and at the footer line. | "A raw LLM over a spreadsheet gives confident wrong numbers and ships your data to a third party. For HR that is a non-starter. DarwinLens is what I built around the model. It runs on open-weight models, and your rows never reach the AI. It is my own prototype for this assignment, not a Darwinbox product." |
| 0:12 | Click **Try the live demo**. The workspace opens. | "No sign-up, no upload: a guest account and a made-up company of 500 employees, in one press. Six messy spreadsheets — merged title rows, a Grand Total footer, rupee strings, duplicate payslips — and you can download them and check my homework." |
| 0:25 | The **Ask** tab, empty. Point at the top bar: the pill tabs **Ask · Overview · Analyses · Saved**, then the **Data** button with its file count. | "Four tabs, and two of them never call a model at all. Everything the app read out of your files is behind Data." |
| 0:33 | Click the suggestion card for total gross pay by department. | "It suggests questions these files can actually answer, so nobody has to guess the magic words." |
| 0:42 | The **Working on it** card runs. Read the steps as they tick. | "Watch the steps: it understands the question, writes the query, *checks the query is safe* against a parser allow-list, runs it on your data, and double-checks with a second AI model from a different family writing its own query." |
| 0:55 | The answer card arrives. Point at the confidence badge, the ticks, the chips. | "The headline, the confidence badge with a *Why?* you can open, and the checks: computed by a database from your files, a second model got the same result, no rows or personal data were sent to the AI. The chips are computed from the rows, not written by the model." |
| 1:08 | Use **Show the result as**: bar → donut → table. | "Charts are chosen by rules, never by the model, and I can switch." |
| 1:16 | Open **How I got this**. Point at the flow strip, then scroll to **What the model saw**. | "The route the answer took, how it read the question, the plan, the data used, the SQL, the cross-check. Then the one that matters. *What the model saw:* column names, types, statistics and short category lists. No rows. A test plants fake PII and fails the build if it ever appears here." |
| 1:38 | Ask **"What is the average salary by department?"** The clarify options appear. Press the CTC one. | "'Salary' could be CTC, gross or net. It does not guess, and this check is rule-based, so it costs no model call. Once I answer, it never asks me again." |
| 1:52 | Ask **"What will our attrition rate be next quarter?"** — a refusal, with **What would make this answerable**. | "It refuses and says what it would need. No forecasting, no statistical tests, because running model-written code is how comparable tools got remote-code-execution CVEs. No answer beats a wrong one." |
| 2:05 | Tab to **Overview**. Point at the green **No AI involved** badge, then open a tile's **Table and SQL**. | "Fourteen tiles, computed the moment the files landed, in about sixty-six milliseconds, and the same fourteen every time. No AI involved. Every tile shows its rows and its query — same guard, same database, same formatter as an answer, so a tile and the chat cannot disagree. This is the half that still works when every free model is rate limited." |
| 2:22 | Tab to **Analyses**. Pick a kind, change the pill selects in the sentence, press **Run**. | "And if you would rather not type a question, build the sentence: *show me the average of Annual CTC by Department*. **No AI needed** — you choose the columns, the database does the rest. You see the sentence before you run it, and the SQL after." |
| 2:36 | Open **Data** → **Tables** tab → expand `Salary_Register_2025.xlsx`. | "This is the receipt. Title rows skipped, a Grand Total row dropped — that row double-counts if you sum it. Rupee strings read as money. Employee codes kept as text, so `004512` stays `004512`. Name, email, phone and PAN flagged as personal data and hidden from the model." |
| 2:48 | Save an answer, tab to **Saved**, hover **Print or save as PDF**. | "Answers and tiles collect into a report that prints — the thing an analyst actually hands their CHRO." |
| 2:55 | Avatar menu → **Trust report**. | "And the numbers: forty golden questions with truth computed in pandas before I inject the mess, ten held out from tuning, plus sixteen harder ones written after the prompts were frozen. Every failure listed. The same engine is also an MCP server, so a company's own agents get these answers with that customer's own definition of attrition." |

## Two honesty lines to say out loud

Say both. They land better than the scores do.

- **On the numbers:** "These were measured at six in the evening on the 20th, before two later
  prompt changes. The re-run ran out of free quota and did not finish. I would rather show you a
  number with its timestamp than one that looks cleaner."
- **On the ceiling:** "One challenge question failed, and it is the honest kind: a month-on-month
  change filtered the months *before* differencing, so the first change came back empty. Valid
  SQL, the cross-check agreed, an empty cell is not a wrong number. Only the confidence badge
  noticed — and it did not call it High."

## If something goes wrong on camera

- **A model is rate limited.** The app says so in one sentence with a wait time. Do not wait on
  camera — go to **Overview** or **Analyses**. Neither calls a model, so both work with the quota
  completely gone, and that is a better demo of the thesis than the answer you lost.
- **A question hangs.** The six starter questions are cached after the first ask (and pre-warmed by
  `make warm`), so re-asking one is instant. The clarify options and the refusal cost no model call
  either.
- **Cold start.** The free instance sleeps after 15 idle minutes and takes about a minute to wake.
  Open the link before you start recording.
- **Your account is gone.** Accounts live in a SQLite file on the instance's disk and a redeploy
  wipes it. Do not plan to sign in on camera: **Try the live demo** always works, because it makes
  a fresh guest.
- **The Trust report says no report has been run.** `eval/report.json` was not in the image. Show
  [`eval/REPORT.md`](eval/REPORT.md) in the repo instead.
- **Running out of time.** Cut in this order: the chart switch (1:08), the guided analysis (2:22),
  the Saved board (2:48). Never cut "What the model saw" or the refusal.

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
- *Can our agents call it?* Yes. `POST /mcp` puts the same engine behind the Model Context
  Protocol: six tools, five of which call no model at all, the same bearer token, the same limits
  and the same personal-data masking. A security review of it found four defects, all fixed with
  regression tests — including a stringified `"false"` that would have turned masking off, because
  `bool("false")` is true. `docs/MCP.md` has a curl walkthrough.
- *Does this scale?* One process with in-memory sessions today, deliberately. Measured in
  `docs/CAPACITY.md`: the twelve-session store is what saturates first, at the thirteenth
  concurrent analyst, not CPU and not memory — the Overview held at about 55 ms at 5, 15 and 30
  analysts and peak memory was 247 MB against 512. Path: accounts to Postgres, sessions to Redis
  with a DuckDB file each, the limiter to the proxy, model calls behind a queue.
- *Why gpt-oss?* Apache-2.0 open weights served by Groq — not the GPT API, and no request goes to
  OpenAI. Every runtime model is open-weight, and the eval picked this one.
- *What is not finished?* `docs/PENDING.md`, and I will show it: the eval re-run on the final
  prompts, accounts that a redeploy wipes, the tenth guided analysis that reaches the picker but
  cannot be run, a guided cross-file sum that should refuse rather than caveat, the unmetered
  no-model routes, and `TRUSTED_PROXY_HOPS` to confirm against the header Render actually sends.
