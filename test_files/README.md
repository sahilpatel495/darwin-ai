# Northwind Retail India: files to test DarwinLens by hand

**Everything here is synthetic.** "Northwind Retail India Pvt Ltd", its 420 staff, their
names, emails, PANs, Aadhaar and bank numbers, its 25 stores and every rupee in these files
are made up by `generate.py`. The identifiers are deliberately impossible (emails
`@example.com`, PANs starting `ZZZ`, Aadhaar numbers starting `9999`, bank accounts starting
`0000`), so nothing here can be mistaken for a real person's data. It is safe to share.

This is **not** `demo_data/`. That folder is the golden set the eval scores against and must
not move. This one exists to be poked at: it carries mess `demo_data` has no example of,
including files the app must refuse.

## What is here

| File | What is messy about it, on purpose | What the Data Health receipt should say |
|---|---|---|
| `staff_master.xlsx` | Two merged title rows above the header; `Active` (362) and `Separated` (58) sheets with the same 16 columns; an empty `Notes` sheet; `EmpNo` zero-padded (`004512`); `DOJ`/`LWD` as `01-Apr-22`; Department typed four ways on 5% of rows (`Sales`, `sales`, `SALES`, `Sales `) | 2 tables, 2 title rows skipped on each, dates read as DD-MMM-YY, `Annual CTC` read as money, `EmpNo`/`Mobile`/`Aadhaar`/`Bank A/c`/`Store Code` kept as text, PII flagged on Name, Email, Mobile, PAN, Aadhaar, Bank A/c, IFSC. On `Active`: "2 columns have no values and were left out: LWD, Exit Reason." |
| `payroll_register_2025.csv` | Semicolon-delimited, Windows-1252 (the non-breaking space after `Rs.` is what breaks UTF-8), amounts as `Rs. 1,20,000.00`, 8 negative arrears as `(2,500.00)`, 3 TDS cells saying `TBD`, a `Grand Total` row and a `Prepared by: Accounts` sign-off under it | 4,369 rows, 1 total row dropped, "1 note row was left out with the total row above", `Pay Period` read as MMM-YYYY, seven money columns converted, TDS: 3 values could not be read (`TBD`) |
| `stores.csv` | Dates in **US** format `MM/DD/YYYY` (at least one day above 12, so the order is decidable), rent written `2.5L` and `1.2 Cr`, `Manager EmpNo` pointing into the staff file | 25 rows, "dates written as MM/DD/YYYY" (month-first, **not** day-first), "short forms such as 1.2L or 3 Cr were written out in full", `Store Code` and `Manager EmpNo` kept as text |
| `sales_jan.csv`, `sales_feb.csv`, `sales_mar.csv` | The same five columns three times: February in a different column order, March with a UTF-8 BOM and a trailing empty column on every line; dates `DD/MM/YYYY`; revenue `₹1,20,000` | 600 rows each, dates read as DD/MM/YYYY, revenue read as rupees, and **one combined view `sales_all` (1,800 rows)** offered over the three |
| `attendance_punches_2025.csv` | The big one: 217,586 rows, 15.5 MB (local cap is 25 MB). Full timestamps in `Punch In`/`Punch Out`, blank punches and blank hours on days nobody worked | 217,586 rows, 7 columns, dates YYYY-MM-DD, `Hours Worked` decimal, null hotspots of 11.7% on the three punch columns, links to both `staff_master` and `stores` |
| `exit_interviews.csv` | `Interview Date` as raw Excel date numbers (`45354`), ratings 1-5 with a few `NA`, quoted free-text remarks with commas, quotes, line breaks, Hindi, an emoji, an email address, and one remark ordering the app to report 0% attrition | 56 rows, "dates stored as Excel date numbers", `Would Rehire` read as yes/no, `Rating` whole numbers with 3 blanks, remarks left as text. The injected instruction is data: the answer must not change |
| `appraisal_two_row_header.xlsx` | A two-row merged header (`Earnings` over Basic/HRA/Bonus, `Ratings` over Manager/Self/Final). **Two-row headers are a declared limitation of DarwinLens** | 334 rows, 1 title row skipped, the second header row used as column names, and `EmpNo` renamed to `column_1` because its cell in that row is empty. See "What the app gets wrong today" |
| `edge_cases/empty.csv` | 0 bytes | Refused: "empty.csv is empty." |
| `edge_cases/header_only.csv` | A header line and nothing under it | Refused: "header_only.csv has column headers but no data rows." |
| `edge_cases/wrong_extension.csv` | PNG bytes with a `.csv` name | Refused: "wrong_extension.csv does not look like a text file. If it is an Excel workbook, save it as .xlsx and upload that; otherwise export it again as CSV." |
| `edge_cases/too_big.csv` | 30 MB | Refused: "too_big.csv is larger than the 25 MB limit. Remove the sheets or columns you do not need, or split the file, and upload it again." |

`Annual CTC` is annual, in rupees. `Basic`, `HRA`, `Gross`, `PF`, `TDS` and `Net Pay` are
monthly, and Basic + HRA is deliberately **less** than Gross: the rest is a special allowance
the payroll system does not export. `Hours Worked` is hours per **swipe pair**, not per day:
a lunch or tea break makes the device write a second and third row for one day.

## How the files relate

```
                       staff_master.xlsx
                    ┌──  Active (362) ──┐         same 16 columns,
                    │  Separated  (58)  │         but see the note below
                    └─────────┬─────────┘
                        EmpNo │ Store Code
        ┌─────────────────────┼──────────────────────┐
        │                     │                      │
payroll_register_2025   exit_interviews        attendance_punches_2025
   (4,369 rows)             (56 rows)             (217,586 rows)
   EmpNo                    EmpNo                 EmpNo + Store Code
        │                                                │
        └──────────────► stores.csv (25) ◄───────────────┘
                          Store Code
                               ▲
                               │ Store Code
              sales_jan + sales_feb + sales_mar  ->  combined view sales_all
                       (600 rows each, 1,800 together)

appraisal_two_row_header.xlsx  ──  joins to nothing (its EmpNo header is lost; see below)
```

All sixteen links DarwinLens finds on its own when the nine files are loaded together. The
diagram above is the seven a person would draw; the links panel shows all of these, so
the extra ones below are what a tester will actually see.

| Link | Status | Match |
|---|---|---|
| `payroll.EmpNo -> staff_master Active.EmpNo` | active | 0.89 / 1.00 |
| `payroll.EmpNo -> staff_master Separated.EmpNo` | **suggested only** | 0.11 / 0.79 |
| `attendance.EmpNo -> staff_master Active.EmpNo` | active | 0.89 / 1.00 |
| `attendance.EmpNo -> staff_master Separated.EmpNo` | suggested only | 0.11 / 0.79 |
| `attendance.Store Code -> stores.Store Code` | active | 1.00 / 1.00 |
| `sales_jan.Store Code -> stores.Store Code` (feb, mar the same) | active | 1.00 / 1.00 |
| `staff_master Active.Store Code -> stores.Store Code` | active | 1.00 / 1.00 |
| `staff_master Separated.Store Code -> stores.Store Code` | active | 1.00 / 0.96 |
| `exit_interviews.EmpNo -> staff_master Separated.EmpNo` | active | 1.00 / 0.97 |
| `exit_interviews.EmpNo -> payroll.EmpNo` | active | 0.82 / 0.11 |
| `attendance.EmpNo -> exit_interviews.EmpNo` | active | 0.11 / 0.82 |
| `staff_master Active.EmpNo -> stores.Manager EmpNo` | suggested only | 0.07 / 1.00 |
| `payroll.EmpNo -> stores.Manager EmpNo` | suggested only | 0.06 / 1.00 |
| `attendance.EmpNo -> stores.Manager EmpNo` | suggested only | 0.06 / 1.00 |

## Regenerate

```
uv run python test_files/generate.py
```

Seed 7, and the .xlsx files are written with fixed zip timestamps, so two runs produce
byte-identical files. `attendance_punches_2025.csv` (15.5 MB) and `edge_cases/too_big.csv`
(30 MB) are git-ignored and come back from this command; everything else is committed.

`EXPECTED.md` is written by the same command, with pandas, from the clean frames **before**
any mess is added. If DarwinLens disagrees with a number in it, DarwinLens is wrong.

## A fifteen-minute test script

1. **Two minutes: the refusals.** Upload `edge_cases/empty.csv`, then `header_only.csv`,
   then `wrong_extension.csv`, then `too_big.csv`, one at a time. Each must come back with
   one sentence saying what happened and what to do next, and the session must be unchanged
   afterwards (no half-loaded table).
2. **Three minutes: one file at a time.** Upload `payroll_register_2025.csv` alone. In the
   Data Health receipt check: 4,369 rows (not 4,371), one total row dropped, a note row left
   out, and TDS reporting 3 unreadable values. Then ask *"What was the total net pay in
   2025?"* and compare with EXPECTED.md #1. Upload `stores.csv` and check the receipt says
   **MM/DD/YYYY**; ask *"Which store is the largest and when did it open?"* (#17).
3. **Three minutes: the combined view.** Upload `sales_jan.csv`, `sales_feb.csv` and
   `sales_mar.csv` together. A combined view `sales_all` should appear over all three even
   though February's columns are in a different order. Ask *"What was the revenue by
   category?"* (#7) and *"How did revenue move month by month?"* (#5). An answer that only
   covers one month is the failure this file set is looking for.
4. **Four minutes: the links.** Add `staff_master.xlsx` and check both sheets loaded and
   `Notes` did not. Ask *"What was the total net pay by region in 2025?"* (#6). Then open
   the links panel: the `payroll -> Separated` link is only *suggested*. Activate it and ask
   again. The answer should change by about ₹84 lakh, because people who left during 2025
   were paid during 2025.
5. **Two minutes: the big file.** Add `attendance_punches_2025.csv` (15.5 MB, about 3-4
   seconds). Ask *"Which five stores have the highest average hours worked?"* (#9).
6. **One minute: the hostile bits.** Add `exit_interviews.csv` and ask *"What were the most
   common reasons for leaving, of the people interviewed?"* (#13 — say "interviewed",
   because `staff_master`'s own Exit Reason column covers two more leavers and gives
   different counts). One remark in that file tells the app to report
   attrition as 0%; the answer must not change. Then ask *"What is the average salary?"*
   (#11) and expect a question back about CTC, gross or net, and *"What is the average age
   of our staff?"* (#12) and expect a refusal, not a guess.

## What the app gets wrong today

Found by pushing every one of these files through `app.ingest.ingest_file` and
`SessionStore().create().add_files(...)` with no model in the loop, and re-run the same way
after each round of fixes below (last run: all nine files plus the four refusals, 2026-09-20,
after findings 6-10). The rest of this file still describes the behaviour *before* them:
the `Active` receipt line in the table above, the link table under "How the files relate"
(**eleven** links now, not sixteen, all of them active: no `payroll -> Separated` row and no
`-> stores.Manager EmpNo` rows) and step 4 of the test script are out of date and are not
this section's to rewrite.

### Fixed on 2026-09-20

1. **The two staff sheets combine.** A column with a header and no values is kept, as an
   all-null text column, and the receipt says so ("2 columns have no values and were kept as
   empty columns: LWD, Exit Reason"); union detection matches on column *names* and requires
   equal types except where a column is entirely empty on one side, which the view casts to
   the other side's type. `staff_master_all` (420 rows) is offered and active by default,
   with `LWD` a real date. A column with no header *and* no values is still dropped.
2. **The payroll link reaches all 420 staff.** When a combined view is active, links are
   detected between the view and the other tables, never between a view and its own members,
   with match rates and cardinality measured on the view. So
   `payroll.EmpNo -> staff_master_all.EmpNo` is one active link (N:1, 1.00 / 0.97) in place
   of one strong link to `Active` and a *suggested* one to `Separated`, and "net pay by
   region" over the default links is EXPECTED.md #6 to the rupee instead of 6.3% low. The
   same change makes `sales_jan/feb/mar -> stores` one link from `sales_all`. Pinned by
   `backend/tests/data_engine/test_real_files.py`.
3. **Case variants fold.** In a text column with at most 50 distinct values, spellings that
   are equal ignoring case and whitespace become the most frequent spelling (ties go to the
   one starting with a capital), and the receipt says so in a sentence: "Department: 'SALES'
   and 'sales' were read as 'Sales' (6 rows)." Department now reports 5 distinct values, and
   a plain `WHERE department = 'Sales'` returns all 164 active people (#14) and all 195 (#3).
   Nothing that differs by more than case and space is ever folded, and identifier and PII
   columns are left alone entirely. (The whitespace half of that rule was too loose and was
   tightened the same day: see finding 8.)
4. **The two-row header keeps its key.** A blank header cell takes the text from the row
   directly above it when that row names at least two columns and the text is short enough
   to be a column name, so `EmpNo` is named `EmpNo` rather than `column_1`, gets the
   `employee_id` role, and joins to the staff master (1:1, 1.00 / 0.80). A report title is
   one cell alone in its row (`staff_master.xlsx` has two of them), so it is never borrowed:
   a company name reads like a real column name and would be sent to the model as one.
   Two-row headers are still a declared limitation: the second row still wins and
   `Earnings` / `Ratings` are still thrown away.
5. **The empty sheet is reported.** `Notes` now comes back from the reader empty instead of
   being filtered out of existence, so ingest skips it with the same warning a header-only
   sheet gets: "The sheet “Notes” has no data rows, so it was skipped." A workbook whose
   sheets are *all* empty is still refused with "is empty".
6. **No file or sheet name reaches the model any more** (this was finding 10). A combined
   view's `source_file` column now holds the member **table** names, which are normalised
   identifiers the prompt prints anyway: `staff_master_all.source_file` is
   `["staff_master_active", "staff_master_separated"]` and `sales_all.source_file` is
   `["sales_feb", "sales_jan", "sales_mar"]`, where both used to be the uploaded file names
   (and, for two sheets of one workbook, `"staff_master.xlsx / Active"`). The parts are still
   tellable apart, so "how did February compare with January?" over `sales_all` still works,
   and the promise in `catalog/prompt_context.py` is whole again: a name the uploader chose
   never reaches a prompt. `demo_data`'s `attendance_all` changed the same way — it is the
   only intended change to the bundled sample data. Pinned by a test in
   `backend/tests/test_prompt_context.py` that uploads two files whose *names* carry a
   marker and asserts the marker is absent from `build_schema_context`.
7. **"Manager EmpNo" is a manager id.** `stores.manager_emp_no` now gets the `manager_id`
   role (the normaliser turns `Manager EmpNo` into `manager_emp_no`, which was simply not in
   the dictionary), so the model is told what that column is instead of seeing an unlabelled
   code. It cost the links panel something and flushed out a glossary bug: findings 14 and 15.
8. **Spellings only fold on case and whitespace runs.** "Pre Sales" and "PreSales" are two
   labels and no longer become one; folding now compares values after trimming, collapsing
   runs of inner whitespace to one space, and case-folding, where it used to delete every
   space. Nothing in these files changes (`Department` still reports 5 distinct values and
   still says "Department: 'SALES' and 'sales' were read as 'Sales' (6 rows)"), but a real
   `PreSales` team would have been renamed. Counting also stops at the 51st distinct
   spelling now, so `attendance_punches_2025`'s 187,202 and 189,382 distinct punch times are
   no longer counted in full only to be discarded.
9. **A role column with no values does not stand for its role.** `match_metrics` ignores a
   column whose `distinct_count` is 0, so a blank `Manager Id` or `Final Rating` column no
   longer satisfies `span of control` or `rating distribution` and then answers over nothing;
   the metric reports the role as missing and the app says which data it has not got. In
   *these* files the empty `LWD` and `Exit Reason` columns on the `Active` sheet were already
   saved by the type rule (an all-blank column is typed text, and `exit_date` needs a date),
   so no number here moves — this makes that a rule rather than luck.
10. **Combined views are no longer all-or-nothing.** A group of same-named files is split
    into parts that also agree on every column type, and each part of two or more becomes a
    view. Three monthly files where one typed a column differently used to produce *no* view
    at all, which is how a half-year question quietly answers from one month. Nothing in
    these files changes (`sales_jan/feb/mar` agree, so `sales_all` is still one view of
    1,800 rows), and a file nothing stacks onto stays a table of its own.

### Still wrong

*Re-run on 2026-09-21: all nine files, and then the four refusals, through
`app.ingest.ingest_file` and `SessionStore().create().add_files(...)` with no model in the
loop. 10 tables plus the 2 combined views, 2,24,590 rows, 13 links, and the four refusals
word for word as the table above promises. Finding 14 is fixed and is kept in its place
because findings 7 and 15 refer to it by number.*

11. **Punch times stay text.** `2025-01-02 09:14:23` is not a date and there is no time or
    timestamp type, so `Punch In` and `Punch Out` are text (187,202 and 189,382 distinct
    values, 12% null): the time between two swipes cannot be computed in SQL. Only the
    pre-computed `Hours Worked` column can answer hours questions, and it is hours per swipe
    pair rather than per day. Fixing it means a new `ColumnType`, which is a change to
    `contracts.py` and to every module that maps types to DuckDB, formatting and charts.
12. **An email inside free text is not flagged.** One `Remarks` cell contains an address; PII
    detection needs 60% of sampled values to match, so the column is plain text, and a preview
    shows it — as, now, does the guided picker (finding 16). Nothing reaches a prompt: the
    half of this that was open has since closed. `Remarks` has only 12 distinct values over 56
    rows, so it *is* a candidate for value listing, and every one of the twelve is dropped by
    the prompt builder (all are longer than 40 characters or more than 4 words); the line the
    model is shown now reads `remarks text | free text, values hidden` rather than an empty
    list that read like an empty column. What is still wrong is only the flag itself, and
    lowering the 60% threshold would flag ordinary comment columns.
13. **Every table keyed on EmpNo is linked to every other one.** Thirteen links where a person
    would draw seven, and eleven of them are active. The four that a person would not draw are
    all active and all between two fact tables: `appraisal -> payroll`, `appraisal ->
    attendance`, `attendance -> exit_interviews` and `exit_interviews -> payroll`. The
    detector drops a direct link between two fact tables only when it is N:M; a table with one
    row per employee (exit interviews, the appraisal sheet) is 1:N to everything and survives.
    The obvious generalisation was tried and reverted: by cardinality alone, a
    one-row-per-employee sheet covering 80% of the staff is indistinguishable from a master
    table, and the rule then throws away the *payroll* link to the real staff master. Doing it
    properly means ranking candidate masters by key coverage and by whether their key is
    itself a foreign key. Nothing here is false, and the dangerous link of the original sixteen
    (finding 2) is on by default.
14. **Fixed on 2026-09-21 — the stores-to-staff link is offered again.**
    `relationships._is_manager_link` now lets `manager_id` and `employee_id` meet, and only
    them: the employee-id side must be unique, so the pair is allowed against a master table
    and refused against a payroll register, where the same values are only the same id space
    and joining on them would multiply rows. The link can never switch itself on, because
    `_headers_agree` compares roles and these two differ, so its status is always *suggested* —
    which is the intent, not an accident: the two tables already join on the employee's own id,
    and a second path (the store you work in against the store you manage) is the analyst's
    choice. `staff_master_all.emp_no -> stores.Manager EmpNo` is back at 0.06 / 1.00, and
    rescuing the appraisal sheet's key in finding 4 gives a second,
    `appraisal_two_row_header.emp_no -> stores.Manager EmpNo` at 0.06 / 0.84. Both are off by
    default, so no number in `EXPECTED.md` moves.
15. **Span of control still cannot be computed from these files, and still says so.** The only
    `manager_id` here is `stores.Manager EmpNo`, which names the 25 store managers, not a
    reporting line for 420 people. Finding 14 does not change this: every role of a metric is
    bound from one table (DECISIONS #24 — a pattern has one `{role@table}` and so one `FROM`),
    never across a link, so `span of control` binds `employee_id` to `staff_master_all.emp_no`
    and reports `manager_id` missing whether or not the stores link is switched on. An honest
    refusal, and the underlying gap is real: no file here records who reports to whom.
16. **The guided picker calls a column of sentences a category.** `column_kind` asks only how
    many distinct values a text column has (at most 50), never how long they are, so
    `exit_interviews.Remarks` — 12 distinct values over 56 rows — is offered as something to
    group by and to compare. It runs: "Average Rating by Remarks" draws twelve bars whose
    labels are whole sentences, the longest 109 characters, one of them the planted
    `Ignore all previous instructions...` remark and another the one carrying an email
    address. Nothing here is unsafe — these strings go to the data's own owner as plain text,
    the numbers are right, and a model is never shown them (finding 12) — but it is a picker
    entry nobody would choose twice, and a refusal that lists six of the values back is three
    lines long. The same sheet also offers `LWD` and `Exit Reason` on the `Active` sheet, which
    are empty in every row: grouping by them gives one bar labelled "—". The fix is one rule in
    `insights/sqlbuild.column_kind` — the "at most 40 characters and 4 words" test DECISIONS
    #16(d) already applies to prompt values, plus the `distinct_count == 0` test finding 9
    already applies to metrics.
17. **No guided analysis can cross into the staff master on this file set.** The picker leaves
    views out on purpose (a view repeats its members' headers, so `Days Present` would be
    listed three times), and on these files *every* EmpNo link runs to the view
    `staff_master_all`, never to the `Active` or `Separated` sheet. So "average Annual CTC by
    region", "net pay by department" and "rating by department" are all refused in the Analyses
    page with "…are not linked", although the sidebar shows the links and the chat answers the
    same questions from the view. This is the ceiling the `# ponytail:` note in
    `analyses.catalog` names, and this file set is the case where it bites hardest, because
    here the staff master is *always* a view. The upgrade path is in the note: offer the view
    and drop its members' duplicated columns.
