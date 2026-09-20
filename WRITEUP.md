# DarwinLens: one-page write-up

Sahil Patel · Forward Deployed Engineer take-home · live demo: https://darwinlens.onrender.com

**The thesis.** The model never computes a number and never sees a row. It writes SQL from column
names, types, statistics and short category labels. DuckDB computes. Deterministic code checks the
SQL before it runs and the wording after. The screen shows the work, down to the exact prompt.

**What I scoped in, and what I cut.** In: messy real exports, privacy, verification and
measurement. Out: server-side storage of HR files, other databases, forecasting and statistical
tests, old `.xls`, wide attendance musters, and the grouping row of a two-row header. Accounts
exist only to answer "whose session is this?"; projects and history still live in the browser.

**The delta on top of what a chat model already does.** A raw model over a spreadsheet fails
quietly, and quiet is the expensive part. So: an ingestion receipt per file, real header row
found, "Grand Total" footer dropped, `₹1,20,000` read as money, `000457` kept as text, every
change written down. Rows never reach the model, enforced by one function and a canary test.
Clarify chips computed by rule, not by a model call, when "salary" could be CTC, gross or net. An
allow-list SQL guard over a locked-down DuckDB. A second model family writing its own SQL as a
confidence signal. Claim checking, because a true number under a false sentence is still a wrong
answer. A confidence badge that lists its reasons. And a whole half of the product, Overview and
Analyses, computes real numbers with no model in the loop, through the same guard and executor. It
is the best argument for the thesis, and it survives an empty free tier. That engine is now an MCP
server too: six tools, same limits, same masking, so a customer's agents answer with that
customer's vetted definition of attrition.

**How I used AI to build it.** Claude Code as lead, with parallel subagents. I set the thesis, the
scope, the constraints and the cuts, and approved the spec before any code existed. Contracts
first: every shared type, plus the one function allowed to describe data to a model. Builders then
owned disjoint files against those contracts, each followed by an independent reviewer told not to
trust the builder's report. Two reviewer findings paid for the arrangement. One was a live answer
reading "Engineering has the highest average salary" when the top row was Support, under a
High, cross-checked badge, every number genuine. The other was a combined view's `source_file`
column carrying uploaded file names into prompts, breaking a privacy promise the prompt builder had
only been audited to keep in the other direction. Both are regression tests now.

**Honest limits.** Golden set 40 of 40, holdout 10 of 10, never-tuned challenge set 15 of 16, the
one failure date logic. Measured at about 18:00 on 20 September, before two later prompt changes;
the re-run could not finish on free quota, so the numbers carry their timestamp. Accounts live in
a SQLite file on the instance's disk, so a redeploy on the free host wipes them; no email
verification, no password reset. One worker with in-memory sessions, and a measured ceiling of
twelve concurrent analysts.

**What is next.** Durable storage first: Postgres for accounts, Redis and a DuckDB file per
session, which also unlocks a second worker. Then per-customer metric dictionaries driven by the
glossary, because "what do you mean by attrition?" is most of week one. Then SSE on the MCP
endpoint, so an answer streams its steps to an agent as it does to the browser.
