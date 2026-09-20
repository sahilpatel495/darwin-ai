# Northwind Retail India: files to test Verity by hand

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
| `appraisal_two_row_header.xlsx` | A two-row merged header (`Earnings` over Basic/HRA/Bonus, `Ratings` over Manager/Self/Final). **Two-row headers are a declared limitation of Verity** | 334 rows, 1 title row skipped, the second header row used as column names, and `EmpNo` renamed to `column_1` because its cell in that row is empty. See "What the app gets wrong today" |
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

All sixteen links Verity finds on its own when the nine files are loaded together. The
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
any mess is added. If Verity disagrees with a number in it, Verity is wrong.

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
`SessionStore().create().add_files(...)` with no model in the loop. Nothing below is fixed
here; the files exist so these are visible.

1. **The two staff sheets do not combine.** `Active` has no leavers, so its `LWD` and
   `Exit Reason` columns are empty and ingestion drops them ("2 columns have no values and
   were left out"). The two sheets then no longer share a schema, so no combined view is
   offered, even though a person reading the workbook would obviously stack them.
2. **The payroll link to the leavers is only *suggested*.** 79% of separated staff appear in
   the payroll (the rest left before 2025), just under the 80% bar for switching a link on.
   With the default links, "net pay by region" answers from the `Active` sheet alone and
   comes out **₹12.67 crore instead of ₹13.51 crore, 6.3% low**, with no warning that a
   whole sheet was left out. This is the most dangerous thing in this file set.
3. **Case variants survive.** `Sales ` loses its trailing space, but `sales` and `SALES` do
   not fold into `Sales`. The department column reports 10 distinct values where there are
   5, and a plain `WHERE department = 'Sales'` returns 158 of the 164 people.
4. **The two-row header loses the key.** In `appraisal_two_row_header.xlsx` the second row
   wins as the header (correctly), but `EmpNo` sits in the first row, so the column is named
   `column_1`, gets no role, and the link detector will not join the file to the staff
   master. The file is readable but unjoinable.
5. **A completely empty sheet is dropped silently.** `Notes` produces no warning at all. The
   promise in `app/ingest/__init__.py` ("skipped with a warning") only holds for a sheet that
   has a header row with nothing under it.
6. **Punch times stay text.** `2025-01-02 09:14:23` is not a date and there is no time or
   timestamp type, so `Punch In` and `Punch Out` are text: the time between two swipes cannot
   be computed in SQL. Only the pre-computed `Hours Worked` column can answer hours questions.
7. **An email inside free text is not flagged.** One `Remarks` cell contains an address; PII
   detection needs 60% of sampled values to match, so the column is plain text. Nothing leaks
   into a prompt (a text column with more than 30 distinct values never has its values
   listed), but a preview will show it.
8. `stores.Manager EmpNo` gets no semantic role ("manager_emp_no" is not one of the known
   manager-id headers) and its link to the staff master stays *suggested*.
9. **Every table keyed on EmpNo is linked to every other one.** `exit_interviews -> payroll`
   (0.82 / 0.11) and `attendance -> exit_interviews` (0.11 / 0.82) both go *active*, because
   the detector compares columns pairwise and does not know that payroll, attendance and
   exit interviews are three fact tables that should meet at the staff master rather than at
   each other. Nothing here is false — they do share employee numbers — but the panel shows
   sixteen links where a person would draw seven, and the two most dangerous of the sixteen
   (the leaver links in finding 2) are the ones that are *off*.
