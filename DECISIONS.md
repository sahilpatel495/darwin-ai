# Decisions

Short ADRs: context → decision → alternatives → consequences. Newest at the bottom.

**1. SQL, not code execution.** *Context:* the model must turn questions into computation over uploaded files. *Decision:* it writes one DuckDB `SELECT`; nothing it writes is ever `exec`'d. *Alternatives:* PandasAI / LangChain pandas agents that run model-written Python. Rejected: repeated RCE CVEs (CVE-2024-12366 at CVSS 9.8, CVE-2023-39659, CVE-2023-39661, CVE-2024-5565) and sandboxes bypassed twice. *Consequences:* no statistical tests or forecasting; those questions get an honest refusal.

**2. The model never sees rows.** *Context:* HR data is full of PII and the model is a third-party API. *Decision:* prompts are built only from profiles (names, types, statistics, short category values) by one function, `prompt_context.py`; result rows are PII-tokenised before narration. *Alternatives:* send sample rows (better SQL, unacceptable for HR); RAG over rows (same problem, more moving parts). *Consequences:* one choke point makes the guarantee testable with planted canary values.

**3. True distinct values for low-cardinality, non-PII columns.** *Context:* without real filter literals the model guesses `'Bangalore'` for `'Bengaluru'`. Research ranks value hints as the highest-gain technique. *Decision:* send distinct values when a column has ≤ 30 of them, is not PII, and each value is ≤ 40 characters (longer text is dropped as possible injected instructions). *Consequences:* a short hostile category label could still reach the prompt; the guard bounds what it can cause.

**4. Allow-list SQL guard plus locked-down DuckDB.** *Decision:* sqlglot parse; one `SELECT`; no table functions, qualified names or write nodes; tables and columns must exist in the catalog. DuckDB runs with external access off and configuration locked. *Alternatives:* deny-list keywords (bypassable); DuckDB settings alone (still allows CREATE/INSERT). *Consequences:* top-level `PIVOT` is rejected; acceptable.

**5. Read everything as text, then infer types ourselves.** *Context:* pandas inference turns `000457` into 457 and `₹1,20,000` into a string. *Decision:* own the inference with a 95% parse threshold and report every coercion. *Consequences:* more code than `read_csv`, but it is the FDE-relevant part and it yields the ingestion receipt.

**6. Identifier columns stay text.** Joins are always text-to-text and leading zeros survive.

**7. Exact duplicates are removed only when the table has an identifier column.** Rows identical including their ID are export errors; without an ID they may be legitimate. Always reported either way.

**8. Deterministic ambiguity detection before model-judged ambiguity.** A glossary term that maps to several present columns ("salary": CTC, gross, net) produces one-click options without an LLM call. Elsewhere the default is to state the assumption, not interrogate the user.

**9. Rules choose the chart; the model copies pre-formatted numbers.** Chart type follows result shape. Narration receives display strings (`₹12.4 L`) and every number in the answer must match one; otherwise a template is used. *Consequences:* duller prose, zero invented numbers.

**10. Cross-check as a confidence signal, not a vote.** A second model family writes its own SQL in parallel; agreement earns a badge, disagreement a banner. Research shows little accuracy gain from voting but the best available confidence signal.

**11. No schema pruning.** Research shows it hurts when the schema fits in context, which it does for ad-hoc uploads.

**12. Strictly $0.** *Context:* no budget and no card; Groq free is 8K tokens/min and 200K/day per model. *Decision:* a provider failover chain (limits are per model, so alternating models spreads the budget), lean prompts, a disk cache for eval runs, Render free with keep-warm pings. *Alternatives:* ~$15 for paid tiers and an always-on host. *Consequences:* slower eval loop and a possible cold start; mitigated by pre-warmed starter answers and a demo video.

**13. Eval with a holdout split.** 30 dev / 10 holdout; the tuning loop never sees holdout failures. Ground truth comes from pandas over the generator's clean frames, before the mess is injected, so ingestion and SQL are tested together.

**14. SSE over the POST response; session id in a header-free URL path, stored in sessionStorage.** Embedded hosts block third-party cookies; one request per question keeps the client simple.

**15. The golden eval picks the model, not reputation.** Candidates are compared on the same 40 questions; the table goes in the README.

**16. Review findings that changed the design (from the independent reviewers).** (a) PII is detected per column, so one email inside a "Remarks" column would have been offered to the model as a filter value: the prompt builder now drops any value that looks like personal data, whatever profiling decided. (b) File and sheet names are attacker-controlled text and are no longer sent. (c) Identifier values are never listed, even for small tables. (d) Category values must be at most 40 characters and 4 words; a sentence is not a label. (e) The rate limiter reads the last `X-Forwarded-For` entry (appended by the proxy), not the first (chosen by the client). (f) A clarification sent by the browser is kept only if it names a real column. (g) "New session" deletes the server-side data immediately. (h) Re-uploading a file with the same name replaces the earlier copy.

**17. Join caveats are directional.** "7% of employees have no payroll rows" and "7% of payroll rows have no employee" are different problems, so the caveat names the side. Confidence uses the better-contained side, because in a healthy parent/child link every child key exists in the parent.
