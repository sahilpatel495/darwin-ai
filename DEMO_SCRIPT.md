# Demo script (3 minutes)

One idea to land: **the model never computes a number and never sees a row; everything it says can be checked on screen.** Record at 1280×800, browser zoom 110%. Warm the app first (`make warm URL=...`) so nothing waits on a cold start.

| Time | Do | Say |
|---|---|---|
| 0:00 | Landing page. | "A raw LLM over a spreadsheet gives confident wrong numbers and sends your data to a third party. For HR data that is a non-starter. Verity is what I built around the model so an analyst can trust the answer." |
| 0:15 | Click **Try with sample HR data** (six files load). Open the **Salary_Register_2025.xlsx** card. | "This is a realistic payroll export: three title rows, a Grand Total footer, amounts typed as rupee strings, duplicate rows. The receipt shows what was skipped, parsed and dropped. Employee codes keep their leading zeros. Name, email, phone and PAN are flagged as PII and hidden from the model." |
| 0:40 | Point at **Relationships**. | "It found that `emp_id` in one file is `Emp Code` in another, with the match rate and cardinality, and it stacked the two attendance quarters into one view. I can reject any of these." |
| 0:55 | Ask: **"What is the total gross pay by department?"** Watch the steps stream. | "The model writes SQL. A parser guard checks it is a single read-only query over known tables. DuckDB computes. A second model from a different family writes its own SQL, and the results agree, so it is marked cross-checked." |
| 1:20 | Open **How I got this** → SQL → **What the model saw**. | "This is the exact prompt. Structure and statistics only. No rows, no names. A test plants fake PII and fails the build if it ever shows up here." |
| 1:40 | Ask: **"What is the average salary by department?"** | "'Salary' could be CTC, gross or net. It does not guess. This check is rule-based, so it costs no model call." Click **CTC**. |
| 1:55 | Ask: **"What was attrition in FY25?"** | "It uses a vetted definition: exits over average headcount, Indian fiscal year. The badge says so, and the glossary on the left is editable per customer. That is the forward-deployed part." |
| 2:15 | Ask: **"What is our customer churn rate?"** | "There is no customer data, so it refuses and says what it would need." |
| 2:25 | Click a follow-up chip: **"Split that by location"**. | "Follow-ups keep context, but only the previous question and SQL are remembered, never rows." |
| 2:35 | Open **Trust Report**. | "Forty golden questions. Ground truth is computed with pandas from the clean data before I inject the mess, so it tests ingestion and SQL together. Ten questions are a holdout the tuning loop never saw. And this table shows the confidence badge is calibrated: High answers are right more often than Low ones." |
| 2:55 | Back to the app. | "Small surface, deep trust. What I would build next as an FDE: expose this engine as an MCP tool so Darwinbox agents answer with each customer's own metric definitions." |

## If something goes wrong on camera
- Model rate-limited: the app says so in a sentence. Ask a starter question instead (pre-warmed, answered from cache).
- Cold start on the free host: open the link a minute before recording.

## Questions to expect
- *Why SQL and not pandas code?* RCE CVEs in every exec-based agent; SQL can be parsed and allow-listed.
- *What if the second model is also wrong?* Agreement is evidence, not proof. That is why it feeds confidence rather than overriding the answer, and why calibration is measured.
- *Does this scale?* One process with in-memory sessions today. Path: session state to Redis/object storage, DuckDB file per session, the limiter to the proxy, LLM calls behind a queue. None of it changes the pipeline.
- *Why gpt-oss?* Apache-2.0 open weights served by Groq. The eval picked it over the alternatives; the table is in the README.
