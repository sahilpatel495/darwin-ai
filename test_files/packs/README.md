# Test packs

Eight small worlds for hand-testing DarwinLens, each a zip of 5-6 related files with
columns that neither `demo_data/` nor `test_files/` has. Drop a pack on the upload box and
you are meeting the product cold, the way a stranger would.

All of it is invented: `@example.com` addresses, `+1-555-01xx` phone numbers, made-up
company and people names. Nothing here belongs to a real person or a real company.

- **Generator:** `test_files/packs/generate_packs.py` (seeded, deterministic, stdlib +
  pandas + openpyxl). `uv run python test_files/packs/generate_packs.py` rewrites every
  pack and re-zips it; two runs produce byte-identical files.
- **Truth:** `test_files/packs/EXPECTED.md` - 8 to 10 questions per pack with the exact
  answer, computed with pandas from the clean frames **before** any mess was added. If the
  app disagrees with a number there, the app is wrong.
- **Check:** `PYTHONPATH=backend:. uv run python test_files/packs/generate_packs.py --check`
  ingests every pack through the real engine (`Session.add_files`) and prints the receipt.
  No model is ever called.

## How to use one

1. Unzip. Each zip expands to a folder of its own.
2. Drop **all** the files in that folder on the upload box at once.
3. Read the Data Health receipt on each file card before asking anything: title rows
   skipped, totals dropped, duplicates, date format, columns kept as text, personal columns.
4. Open `EXPECTED.md` at the matching pack and type the questions. The trap line under each
   answer says what the question is really testing.
5. Then try the guided Analyses (no AI) listed per pack below.

Mixing packs is a test in itself: upload `learning` and `retail_sales` together and nothing
should link across them - no store should join to a course. Upload `recruitment` and
`performance_and_engagement` together and only `department` should connect the two worlds.

## The packs

| Pack | Files | Zip | What it is |
|---|---|---|---|
| `recruitment.zip` | 6 | 35 KB | Hiring funnel: requisitions, candidates, interviews, offers, recruiters, channel spend |
| `leave_and_shifts.zip` | 6 | 43 KB | Time off and rostering: employees, leave requests, balances, roster, holidays, sites |
| `learning.zip` | 6 | 21 KB | L&D: courses, enrolments, certifications, budget, trainers, employees |
| `benefits_and_claims.zip` | 5 | 36 KB | Reimbursements, insurance enrolment, allowance master, approvals, employees |
| `retail_sales.zip` | 6 | 781 KB | **Not HR.** 24 stores, 120 SKUs, 121,632 sale lines over two quarters, returns, staffing |
| `performance_and_engagement.zip` | 6 | 19 KB | OKRs, review ratings, engagement survey, exits, managers, employees |
| `company_fintech_full.zip` | 6 | 236 KB | **A whole company.** Kifaya Finserv: 900 staff, 12 months of payroll, attendance, reviews, revenue targets |
| `company_manufacturing_full.zip` | 5 | 362 KB | **A whole company.** Girnar Auto Components: 2,500 workers over 4 plants, wage register, shift attendance, safety, production |

Total: 1.5 MB of zips. Largest single file: `daily_sales_q1.csv` at 2.3 MB - every file is
comfortably under the 10 MB hosted upload limit.

The two `company_*_full` packs are the same **kinds** of files as `demo_data/` (employee
master, payroll by month, attendance, performance reviews, exits, sales or targets) for a
different invented company, with a different vocabulary (`staff_no`, `cost_centre`, `band`,
`fixed_pay`; `ticket_no`, `shop_floor`, `daily_wage`). If anything in the app is quietly
hard-coded to the sample company's column names, these two will show it.

## Three combos worth trying

1. **`recruitment` + `performance_and_engagement`** - two worlds joined only by
   `department`. Ask "which department hires the most and rates the hardest?" and watch
   whether the app links at the right grain or invents an employee-level join.
2. **`retail_sales` alone** - the general-purpose test. No HR vocabulary anywhere, 121,632
   rows, two quarter files that must combine. If the answers are good here, nothing is
   hard-coded to HR.
3. **`benefits_and_claims` + `leave_and_shifts`** - both keyed on the same employee codes
   under three different column names (`emp_code`, `employee_id`, `employee`). A good look
   at link detection when the names disagree.

Or the unhappy path: **`learning` + `company_manufacturing_full`** - two unrelated worlds.
Nothing should link, and the app should say so rather than joining a course code to a
ticket number.

## Exactly where the mess is

### recruitment
- `requisitions.csv` - **two title rows** above the header, a **Total footer**, `Requisition ID`
  as a leading-zero text id (`004500`), `Rs. 12,50,000` amounts, an **all-empty column**
  (`Recruiter Notes`), `N/A` and `-` gaps, DD-MM-YYYY dates, department typed four ways.
- `candidates.xlsx` - **two sheets** (`Applied 2025 H1`, `Applied 2025 H2`) with identical
  columns that must combine, **3 duplicated rows** in H2, one **orphan** row pointing at
  requisition `009999`, source values typed four ways.
- `interviews.csv` - **UTF-8 BOM**, `3 Mar 2025` dates, `N/A` scores.
- `offers.csv` - `₹` amounts, `accepted` as Yes / No / `-`, `joining_date` as `N/A` when declined.
- `recruiters.csv` - **MM/DD/YYYY** dates (the US-style file in this pack).
- `job_boards_spend.csv` - **semicolon-separated, Windows-1252**, title row, Total footer,
  `Rs.` amounts with a non-breaking space.
- **Key under two names:** `Requisition ID` in requisitions vs `req_id` in candidates.

### leave_and_shifts
- `employees_lite.csv` - **all-empty column** (`middle_name`), leading-zero `emp_code`,
  department typed four ways.
- `leave_requests.csv` - **MM/DD/YYYY** dates, **Grand Total footer**, leave type typed four
  ways, blank approvers, an **orphan** row for employee `009999`.
- `leave_balances.xlsx` - **two sheets** (`Balances FY25`, `Balances FY24`) with identical
  columns and a **title row** on each. Combining both doubles every employee.
- `shift_roster.csv` - **40 duplicated rows**, DD-MM-YYYY dates, 3,640 real rows.
- `holidays.csv` - **UTF-8 BOM**, `14 Jan 2025` dates.
- `sites.csv` - **semicolon-separated, Windows-1252**.
- **Key under two names:** `emp_code` vs `employee_id` vs `employee`.

### learning
- `courses.csv` - **UTF-8 BOM**, `₹` seat costs, category typed four ways.
- `enrollments.csv` - **all-empty column** (`feedback_comment`), `82%` percent strings,
  `N/A` scores on everything not completed, DD-MM-YYYY dates, an **orphan** row pointing at
  course `CRS-999`.
- `certifications.xlsx` - **title row**, two date columns (issued and expires).
- `training_budget.csv` - **Grand Total footer**, `₹` amounts, a utilisation column already
  written as a percent string, department typed four ways.
- `trainers.csv` - **semicolon-separated, Windows-1252**, title row, `Rs.` day rates.
- `employees_lite.csv` - plain comma CSV, the clean one.

### benefits_and_claims
- `reimbursement_claims.csv` - **semicolon-separated, Windows-1252**, title row, **Total
  footer**, `Rs. 4,500` with a non-breaking space, claim type typed four ways, leading-zero
  `receipt_no`.
- `insurance_enrolment.xlsx` - **title row**, dependants and premium.
- `allowances_master.csv` - **UTF-8 BOM**, `₹1,23,456.50` amounts.
- `claim_approvals.csv` - **MM/DD/YYYY** dates (claims are DD-MM-YYYY), `₹` amounts, blank
  remarks, one **orphan** approval for claim `CLM99999`.
- **Key under two names:** `emp_code` in claims vs `employee_id` in employees_lite.
- Note: cp1252 has no rupee sign, which is why the semicolon file writes `Rs.` and the
  UTF-8 files write `₹`. That is the real constraint, not a shortcut.

### retail_sales
- `daily_sales_q1.csv` + `daily_sales_q2.csv` - identical columns, **must combine** (121,632
  rows), DD-MM-YYYY dates, `discount` as `10%` strings, and a **Grand Total footer at the
  bottom of Q2**.
- `products.xlsx` - **all-empty column** (`discontinued_on`), category typed four ways.
- `stores.csv` - leading-zero `store_id` (`0010`), region typed four ways.
- `returns.csv` - **UTF-8 BOM**, **MM/DD/YYYY** dates, `₹` refunds, reason typed four ways,
  one **orphan** row with both an unknown SKU and an unknown store.
- `staff_by_store.csv` - **semicolon-separated, Windows-1252**, title row, Total footer, and
  four rows per store, which is the fan-out trap.

### performance_and_engagement
- `review_ratings.xlsx` - a **title row AND a two-row header** with merged group cells
  (`Employee` / `Ratings` / `Compensation` above the real column names), `12.4%` hike strings.
- `engagement_survey.csv` - **UTF-8 BOM**, **wide format**: one column per question, whole
  sentences as headers, scores 1-5, **blanks** scattered through.
- `okrs.csv` - `progress_percent` as a percent string, department typed four ways.
- `exit_interviews.csv` - **free text** with commas, quotes and newlines inside cells,
  `3 Mar 2025` dates, one **orphan** `emp_code`.
- `managers.csv` - **semicolon-separated, Windows-1252**, title row.
- `employees_lite.csv` - the bridge: carries `manager_id`, so ratings reach managers in three hops.

### company_fintech_full (Kifaya Finserv, 900 staff)
- `staff_master.xlsx` - **two sheets** (`Active Staff`, `Separated 2025`) that must combine
  before attrition means anything; `separation_date` and `separation_reason` are **entirely
  empty on the active sheet**; cost centre typed four ways; DD-MM-YYYY dates.
- `payroll_h1_2025.csv` + `payroll_h2_2025.csv` - **two half-year files that must combine**
  (10,133 payslips), **Grand Total footer on H2**, and **USD and INR in the same amount
  column** with the unit in a `currency` column beside it. A plain SUM adds dollars to
  rupees and looks perfectly reasonable.
- `attendance_monthly.csv` - **UTF-8 BOM**, **30 duplicated rows**, blanks and `N/A` in `lop_days`.
- `performance_reviews.csv` - **title row**, one **orphan** row (`staff_no` 999999).
- `revenue_targets.csv` - **semicolon-separated, Windows-1252**, title row, Total footer,
  `$` amounts, attainment as a percent string.

### company_manufacturing_full (Girnar Auto Components, 2,500 workers)
- `workforce_master.csv` - **title row**, plant typed four ways, `date_of_leaving` blank for
  everyone still employed, `contractor_name` as `N/A` for permanents, DD-MM-YYYY dates.
- `wage_register_h1.csv` - **semicolon-separated, Windows-1252**, 14,494 rows, **Grand Total
  footer** repeating every column total, `Rs.` amounts with a non-breaking space, PF and ESI.
- `shift_attendance.csv` - **all-empty column** (`remarks`), **50 duplicated rows**, one
  **orphan** ticket (`099999`), **MM/DD/YYYY** month stamps (see the honest list below).
- `safety_incidents.csv` - **UTF-8 BOM**, `3 Mar 2025` dates.
- `production_targets.xlsx` - **four sheets, one per plant**, identical columns, a **title
  row on each**. All four must combine.

## Analyses to try (guided, no AI)

| Pack | Try |
|---|---|
| recruitment | Count candidates by source; average `expected_ctc` by department; offers over time |
| leave_and_shifts | Leave days by type and by month; balance distribution; shift mix by site |
| learning | Completion rate by category; budget vs spend by department; certifications expiring |
| benefits_and_claims | Claim amount by type and month; premium by plan; rejection reasons |
| retail_sales | Net sales by month on the combined view; top SKUs; returns rate by store |
| performance_and_engagement | Rating distribution; survey score by department; exits by month |
| company_fintech_full | Headcount by band; net pay by month on the combined payroll view; attrition by cost centre |
| company_manufacturing_full | Wage bill by month; overtime hours by plant; incidents by type and severity |

## What the app gets wrong today

Run on 2026-09-21 against the engine as it stands. **None of this has been worked around in
the data and nothing in the engine was changed to make the packs look better.** Every file
in every pack ingests without an exception.

1. **`shift_attendance.csv` month stamps are read as the wrong date.** The file writes months
   US-style (`02/01/2025` for February 2025). Every value has `01` as one of its parts, so
   the format is genuinely ambiguous: the app reads it day-first (2 January) and **says so**
   in the receipt - "Dates in month could be day-first or month-first... They were read as
   day-first, the usual order in India." The warning is honest and correct, but any
   *per-month* answer from that file will be wrong. Per-plant and per-worker answers are fine.
   Nothing in `EXPECTED.md` depends on that column.
2. **Duplicate rows are only removed when the table has an identifier column.** So the 3
   duplicates in `candidates.xlsx`, the 30 in `attendance_monthly.csv` and the 50 in
   `shift_attendance.csv` are dropped, but the **40 duplicated rows in `shift_roster.csv`
   are counted and kept** (that table has no id column). The receipt says which happened
   either way, but "how many night shifts?" on the roster will be 40 rows high unless the
   tester notices.
3. **A key under two different names is only *suggested*, never active.** In `recruitment`,
   `candidates.req_id -> requisitions.requisition_id` matches 98% of values and still arrives
   as a suggestion the tester has to accept, while same-name keys (`emp_code -> emp_code`)
   are switched on automatically. That is a deliberate design choice, but it means the
   cross-file recruitment questions answer wrongly until the link is accepted in the Data
   drawer. Worth watching a first-time user hit it.
4. **Some suggested links are true joins but meaningless.** `insurance_enrolment.emp_code ->
   reimbursement_claims.emp_code` and `okrs.employee_id -> review_ratings.emp_code` are both
   real key matches that no one would ever want to join directly. Harmless, but the Data
   drawer looks busier than it needs to.
5. **The canonical spelling chosen when folding variants is whichever is most common, not
   the tidiest.** In `learning/training_budget.csv` the receipt reads "'ENGINEERING' and
   'Engineering' were read as 'engineering'". The grouping is right; the label just looks
   odd in the answer.
6. **All-empty columns are kept, not dropped.** `Recruiter Notes`, `middle_name`,
   `feedback_comment`, `discontinued_on`, `remarks` and the two empty columns on the fintech
   active-staff sheet all survive into the table with a warning. Correct and honest, but a
   wide file gains dead columns in the catalog.
7. **A two-row header works - once there is a title row too.** `review_ratings.xlsx` (title
   row + group row + real header) is read correctly: 2 title rows skipped, the right 8
   columns. This is the case `test_files/appraisal_two_row_header.xlsx` declares unsupported,
   so the behaviour is better than documented, not worse. Worth confirming by eye.

## Git

`.gitignore` here keeps the zips, the generator, this README and `EXPECTED.md`, and ignores
the unzipped pack folders - they are regenerated on demand and would triple the repo's file
count for nothing.
