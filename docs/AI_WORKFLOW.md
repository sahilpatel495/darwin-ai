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

## 5. What happened after the first build

Sections 1 to 4 describe getting to a working prototype by late afternoon. The rest of the day
was not more features first — it was a hardening pass, and the hardening pass is where the
interesting things happened, so it belongs in the honest account too.

**The pass.** Reviewers with fixed lenses (security, privacy, a first-time user, an FDE who has
to maintain this at a customer) went over the working app rather than over modules. Separately,
a second, messier synthetic file set was generated (`test_files/`, a different fake company,
nine files, 217,000 attendance rows, four files the app must refuse) with its expected answers
computed by pandas **before** the mess was injected — the same rule the golden set follows.
Then every file was pushed through ingest with no model in the loop and the output compared
with the answer key. The point of a second set is that the first one has been looked at all day.

**Three times the happy numbers were proved wrong.** These are the findings I would put in front
of the panel, because each one passed every check that existed when it was made:

| What was found | Why nothing caught it | What changed |
|---|---|---|
| A live answer read "Engineering has the highest average salary at ₹13.34 L" when the top row was Support at ₹15.53 L — under a **High**, cross-checked badge | Every number in the sentence was real, so the grounding check passed. The eval graded the *table*, and the table was right | Rankings are computed, handed to the narrator as facts, and each clause is checked; a wrong claim gets one correction, then a rank-aware template. Ten golden questions now grade the sentence. `DECISIONS.md` 20 |
| A **6.3% undercount** on "net pay by region": the payroll file linked to the *Active* staff sheet only, so everyone who left during the year was silently missing | Link detection ran between tables, and a combined view is not a table. The answer was internally consistent and had no caveat to give | Links are detected between a combined view and the other tables, never between a view and its own members, with match rates measured on the view. `test_files/README.md` finding 2 |
| A **PII alias leak**: a combined view's `source_file` column held the uploaded file names, and a view's columns are profiled and offered to the model as filter values — so the promise "file and sheet names are never sent" was broken by the one place that writes cell text itself | `prompt_context.py` had only ever been audited for what it *reads*. Nothing audited what was written into the data it reads | The literal is the member *table* name, which the prompt prints as a heading anyway. The regression test uploads two files whose names carry a marker and asserts the marker is absent from `build_schema_context`. `DECISIONS.md` 16(b) and 22 |

The pattern in all three: the test and the bug shared an assumption. That is the argument for an
adversarial reviewer who is told not to trust the builder's report, and for a second data set
that nobody tuned against.

**Stalls, and making the work resumable.** Two things stalled the evening. Free-tier quotas ran
out, so the final evaluation could not be re-run on the final code (`DECISIONS.md` 30). And a
long UI rebuild is exactly the kind of task that dies halfway and leaves a repository that does
not compile. Three habits kept that from costing the day:

- **Worktree isolation.** The UI rebuilds ran in `.worktrees/ui` on their own branch, so `main`
  stayed deployable the whole time and merged in one commit when green. `.worktrees/` is
  git-ignored. The rule the whole day ran on: **main is always deployable, and anything not
  finished and tested is removed rather than shipped half-working.**
- **Detached processes.** Long jobs (the test suite, an eval pass, a 15 MB ingest, the load test)
  ran in the background with their output to a file, so a stall was a file to read rather than a
  session to restart.
- **Contracts first, again.** The no-AI half started as `backend/app/insights/models.py` and its
  mirror in `frontend/src/types.ts`, committed before either side was written. The backend and
  the frontend were then built against it at the same time. That is the same discipline as
  section 3, applied to a feature invented at 18:00 rather than planned at 13:00. The accounts
  work and the MCP endpoint were run the same way: the auth contract in
  `docs/DESIGN_SYSTEM.md` §9 and the tool table in `docs/MCP.md` existed before either side did.

**Two lessons about running agents, learned the expensive way.**

- **A failed report is not failed work.** In the v3 build, three builders came back as failures.
  All three had finished: their files were on disk, their type check and their tests were green,
  and what had actually broken was the last step, where an agent writes its report back to the
  lead. The reflex — re-run the failed agent — would have overwritten completed, tested work with
  a second attempt at it, and it nearly did. **A lead must read the journal and look at the disk
  before re-running anything.** The cheap version of that rule: before re-dispatching, run the
  build and the tests for the files that agent owned, and re-dispatch only if they are actually
  missing or red. An agent's own account of itself is the least reliable artifact it produces,
  which is the same reason its reviewer is told not to trust it (section 3).
- **Never let an agent block on a long process.** One agent started the dev server in the
  foreground and waited for it, which it will do until something kills it: no output, no progress,
  no failure, just a slot gone for as long as nobody notices. Anything open-ended — a server, a
  watcher, an eval pass, a load test — is started detached with its output going to a file, and
  the agent polls that file. The rule is the same one as "detached processes" above, but it needs
  saying as an instruction to the agent, not as a habit of the lead, because the agent is the one
  holding the terminal.

**What going past the brief's scope cost.** The brief says a smaller, well-thought-through app
beats a sprawling one, and the day ended with a much bigger app than the design specified: extra
screens, a projects home, a saved board, accounts, an MCP endpoint, and **two** visual directions
that each replaced a finished one (`DECISIONS.md` 26 and 33). The bill was real — two evenings on
a surface that already worked, one half-finished tenth analysis that the documents now name as
unfinished (`docs/PENDING.md` §3), and an evaluation that was never re-run because the time went
elsewhere (`DECISIONS.md` 36). What was bought is also real: the no-AI half is the part that still
works when the free tiers are empty and the clearest demonstration of the thesis, and the MCP
endpoint turns the whole thing from a web app into an engine a customer's agents can call. The
judgement is argued, not hidden, in `WRITEUP.md`.

## 6. What I would tell another engineer

- Agents are fast at filling in a well-specified module and poor at agreeing on interfaces. Spend the human time on contracts and test cases.
- A reviewer with an adversarial brief finds more than a builder asked to "be careful".
- Trust the disk over the report. An agent that says it failed may have finished; check the files and the tests before you re-run it.
- Nothing an agent runs may block. Detach it, write its output to a file, and poll the file.
- Verify claims about the outside world (rate limits, deprecations, pricing) the same day. Three of my starting assumptions were out of date.
- Keep a number that cannot be argued with. Here it is the golden eval, computed independently of the app.
