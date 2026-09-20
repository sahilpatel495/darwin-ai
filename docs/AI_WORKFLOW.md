# How this was built with AI

The brief says the test is how I "use AI tools to go from idea to a working prototype". This is the honest account: what I delegated, what I kept, and the guardrails that made a team of agents produce one coherent codebase instead of ten.

Tooling: Claude Code as lead engineer and orchestrator, with parallel subagents. The **runtime** model inside the app is open-weight only (see README); Claude never runs in the product.

## 1. Research before design (5 agents in parallel, ~10 minutes)

Each agent got one question and had to cite sources and mark anything unverified:

| Agent | Question | What changed because of it |
|---|---|---|
| Providers | Which open-weight models are hosted free today, with what limits? | Groq retired Llama 3.3 70B in Aug 2026; its free tier is 8K tokens/min. The plan moved from "one provider" to a failover chain, and the eval decides the model. |
| Hosting | Where can a Docker app run free without a cold start? | Hugging Face Docker Spaces now need a paid plan. Host became Render free with keep-warm pings. |
| Trust engineering | Which text-to-SQL techniques buy the most correctness per hour? | Send real distinct values for small categorical columns (largest measured gain); skip schema pruning (it hurts small schemas); use a second model as a confidence signal, not a vote. The DuckDB lock-down order and the guard skeleton were verified by running them. |
| Domain | What do real Indian HR exports and HR metrics look like? | Title rows, "Grand Total" footers, ₹ lakh/crore strings, leading-zero employee codes; precise attrition and fiscal-year definitions; "salary" is ambiguous between CTC, gross and net. |
| UX | What do the best data-chat products do, and what do users complain about? | "How this was computed" panels, clarify-instead-of-guess, confident wrong numbers and silent bad joins as the pain to solve. |

## 2. Decisions stayed with me

I chose the thesis (the model never computes a number and never sees a row), the scope tiers, the $0 constraint and the cuts. They are in `docs/DESIGN.md` and `DECISIONS.md`. The AI proposed; I approved the spec before any code existed.

## 3. Contracts first, then parallel build

The lead wrote, before any agent started:
- `backend/app/contracts.py`: every shared type, mirrored in `frontend/src/types.ts`.
- Typed stubs for every module, with docstrings stating the rules.
- `prompt_context.py`, the single function allowed to describe data to a model, with tests that plant canary PII and an injected instruction.
- A hand-built fixture session, and UI fixtures generated from the Pydantic models so mock data cannot drift.
- `docs/PLAN.md`: ten briefs with exact interfaces and concrete input → expected-output cases.

Then one workflow ran **ten builders in parallel**, each owning a disjoint set of files, each followed immediately by an **independent reviewer** told not to trust the builder's report: run the tests, read every file, attack the module with inputs the builder did not try (the guard's reviewer played a customer security engineer hunting for bypasses), fix what breaks, add a regression test.

Rules that kept ten agents from colliding: own only your files; never edit a shared contract, report the problem instead; no new dependencies; no git (the lead commits); tests never call a real model.

The lead wrote the two files that touch everything, `query/pipeline.py` and `main.py`, plus the integration tests that state the product's promises.

## 4. Loops instead of prompts

- **Eval loop:** run the golden set → classify failures → smallest fix → re-run, until the dev split passes the bar. The loop sees holdout *scores* but never holdout *failures*, so it cannot overfit the prompt to the test.
- **Hardening loop:** reviewers with different lenses (security, privacy, first-time user, FDE maintainability) find issues; each finding is verified before anything is changed.

## 5. What I would tell another engineer

- Agents are fast at filling in a well-specified module and poor at agreeing on interfaces. Spend the human time on contracts and test cases.
- A reviewer with an adversarial brief finds more than a builder asked to "be careful".
- Verify claims about the outside world (rate limits, deprecations, pricing) the same day. Three of my starting assumptions were out of date.
- Keep a number that cannot be argued with. Here it is the golden eval, computed independently of the app.
