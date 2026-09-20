# Verity: one-page write-up

Sahil Patel · Forward Deployed Engineer take-home · demo: <!-- DEPLOY_URL -->

## The problem as I read it

The brief asks for plain-English questions over uploaded spreadsheets, with "delta solutioning on top of what AI does". Any chat model will already attempt that. I read the delta as what an engineer must add before a customer can trust the answer on their own data. Real HR exports have title rows, "Grand Total" footers, `₹1,20,000` typed as text, and PII. "Attrition" and "salary" have contested meanings. A raw model fails on these quietly and confidently.

## Approach

One rule: the model never computes a number and never sees a row. It writes SQL from column names, statistics and short category labels. DuckDB computes. Deterministic code checks the SQL before it runs and the wording after. A smaller model phrases the computed result, with PII swapped for tokens. The screen shows the SQL, the caveats, the confidence reasons and the exact prompts.

## Five decisions and what each cost

1. **SQL, not model-written Python.** Agents that run model-written code have a record of remote-code-execution CVEs. SQL can be parsed and allow-listed. Cost: no statistics or forecasting; those get a refusal.
2. **Schema-only prompts, built by one function.** One choke point makes "no PII in prompts" a test with planted canary values. Cost: weaker SQL than with sample rows. Real values for small non-PII columns buy some back: the model writes `Bengaluru`, not `Bangalore`.
3. **Rules choose the chart; the model copies pre-formatted numbers.** A number in the sentence that is not in the result triggers a plain template. Cost: duller prose.
4. **Cross-check as a confidence signal, not a vote.** A second model family writes its own SQL. Disagreement shows a banner. Cost: a second call per question.
5. **Strictly $0.** Free tiers rate-limit, so reliability comes from a provider failover chain and lean prompts. Cost: a slow tuning loop and a cold start on the free host.

## What I cut

Login, persistence, other databases, `.xls`, two-row merged headers, muster-style attendance sheets, small-group salary suppression. The time went to ingestion, privacy and measurement. No visible feature is half-working.

## Results

Forty golden questions; truth computed with pandas from the clean data, before the mess is injected; ten held out from tuning.

<!-- EVAL -->

## How I used AI

Claude Code led a team of parallel subagents. I set the thesis, scope, constraints and cuts, and approved the spec before any code. Builders owned disjoint files against fixed contracts; each was followed by a reviewer told to break the module. Details: [`docs/AI_WORKFLOW.md`](docs/AI_WORKFLOW.md).

## What I would build next, as an FDE at a customer

- **An MCP tool over this engine,** so the company's agents answer with each customer's metric definitions instead of a fresh guess.
- **Per-customer metric dictionaries as config.** Today the glossary, column synonyms and PII patterns are three Python files.
- **A payroll variance explainer** before payroll lock: this month against last, each difference traced to a cause.
- **A migration reconciler** for legacy HRMS exports: old and new side by side, mismatches listed by key.
