# Expected answers, pack by pack

Written by `test_files/packs/generate_packs.py` from the clean frames, with pandas,
before any mess was added. Nothing here is typed by hand, so these numbers are what
the files really contain, not what the app says they contain. If DarwinLens disagrees
with a number below, DarwinLens is wrong (or the question was read differently: the
trap line under each answer says exactly what was counted).

Two answers per pack are not numbers. **CLARIFY** means the app should ask a question
back rather than guess. **REFUSE** means the app should decline: a forecast, or a
column that does not exist.

## recruitment

### 1. How many requisitions are still open?

*Files:* requisitions.csv

21 of 40 requisitions.

> **Trap:** Two title rows above the header and a Total footer row. Counted in, the file has 43 rows.

### 2. What is the total budgeted CTC across all requisitions?

*Files:* requisitions.csv

Rs. 10,54,00,000 over 40 requisitions.

> **Trap:** Footer double count: the Total row already holds this number, so a naive sum doubles it. Amounts are text ('Rs. 12,50,000').

### 3. How many candidates applied in 2025?

*Files:* candidates.xlsx (both sheets)

420 real applications (216 in H1, 204 in H2). The file carries 424 rows: 3 pasted duplicates and 1 orphan row on top.

> **Trap:** Two sheets with identical columns must combine, then duplicates must be dropped.

### 4. Which source brought the most candidates?

*Files:* candidates.xlsx

1. Referral 129
2. Job Board 99
3. LinkedIn 74
4. Agency 63
5. Campus 55

> **Trap:** Spelling variants: 'Referral', 'referral ' and 'REFERRAL' are one source. Order matters.

### 5. What is the average interview score by round?

*Files:* interviews.csv

- Screening: 6.18
- Technical: 5.72

> **Trap:** Scores have 'N/A' and '-' gaps that must be skipped, not read as zero. Dates are '3 Mar 2025' style. The file has a UTF-8 BOM.

### 6. Which department received the most candidates?

*Files:* candidates.xlsx + requisitions.csv

1. Finance 86
2. Engineering 77
3. Operations 73
4. Customer Success 69
5. Marketing 62
6. Sales 53

> **Trap:** Cross-file. The key is 'Requisition ID' in one file and 'req_id' in the other, and one candidate points at requisition 009999, which does not exist.

### 7. How many offers were accepted, and what was the average accepted CTC?

*Files:* offers.csv

58 accepted of 111 offers (52%), average accepted CTC Rs. 22,77,069.

> **Trap:** 'accepted' holds Yes / No / '-', and joining_date holds 'N/A' for every declined offer.

### 8. For candidates who got an offer, how did the offer compare with what they expected?

*Files:* candidates.xlsx + offers.csv

Average expected Rs. 22,84,685, average offered Rs. 23,26,847.

> **Trap:** Cross-file on candidate_id, with currency text on both sides.

### 9. What did we spend on sourcing, and what did each application cost?

*Files:* job_boards_spend.csv

Rs. 30,77,000 for 6014 applications, Rs. 512 per application.
- Campus: Rs. 7,40,000
- Referral Bonus: Rs. 6,68,000
- Job Board: Rs. 6,26,000
- LinkedIn: Rs. 5,22,000
- Agency: Rs. 5,21,000

> **Trap:** Semicolon-separated, Windows-1252, a title row and a Total footer. Amounts are 'Rs. 1,20,000.00' with a non-breaking space.

### 10. How many strong candidates do we have?

*Files:* -

CLARIFY. 'Strong' is not in the data. The app should ask what to use - interview score above a threshold, stage reached, or offer made - and not guess.

> **Trap:** Ambiguous term.

### 11. How many candidates will we hire next quarter?

*Files:* -

REFUSE. This is a forecast; the files hold no future data. Also try 'What is each candidate's notice period?' - there is no such column.

> **Trap:** Forecast and missing column.

## leave_and_shifts

### 1. How many leave days were approved in 2025?

*Files:* leave_requests.csv

799 days across 340 approved requests.

> **Trap:** A Grand Total footer holds the same number plus the orphan row; counted in, the answer roughly doubles. Dates are MM/DD/YYYY in this file only.

### 2. Which leave type is used most?

*Files:* leave_requests.csv

1. Earned Leave 311 days
2. Sick Leave 223 days
3. Casual Leave 136 days
4. Comp Off 82 days
5. Unpaid Leave 47 days

> **Trap:** 'Sick Leave', 'sick leave ' and 'SICK LEAVE' are one type. Order matters.

### 3. Which department took the most approved leave?

*Files:* leave_requests.csv + employees_lite.csv

1. Marketing 174 days
2. Operations 143 days
3. Customer Success 134 days
4. Sales 129 days
5. Finance 115 days
6. Engineering 104 days

> **Trap:** Cross-file, and the key has a different name on each side: employee_id vs emp_code. One request (LR9999, employee 009999) has no matching employee and must be excluded.

### 4. Who has the highest total leave balance left?

*Files:* leave_balances.xlsx (sheet 'Balances FY25')

1. 004180 37 days
2. 004045 35 days
3. 004351 33 days
4. 004297 33 days
5. 004276 33 days

> **Trap:** A title row sits above the header, three rows per employee must be summed, and the workbook has a second sheet ('Balances FY24') with identical columns. Combining both sheets doubles every employee - the FY25 sheet alone is the answer.

### 5. How many night shifts are on the roster?

*Files:* shift_roster.csv

524 night shifts in the roster of 3600 real assignments (the file carries 3640 rows: 40 are a duplicated block).

> **Trap:** Duplicated rows. Dates are DD-MM-YYYY here and MM/DD/YYYY in leave_requests.csv.

### 6. How many public holidays are compulsory rather than optional?

*Files:* holidays.csv

9 compulsory of 12 holidays.

> **Trap:** Dates are written '14 Jan 2025'. 'optional' is Yes/No text, not a boolean.

### 7. How many approved leave days fell on a company holiday?

*Files:* leave_requests.csv + holidays.csv

This needs a date range on one side and a single date on the other. Expected: the app should either expand the range or say it cannot, not silently join from_date to holiday_date.

> **Trap:** Cross-file with no shared key - a genuine limit, and a good look at how it is explained.

### 8. How many people were absent last month?

*Files:* -

CLARIFY. 'Absent' could mean approved leave, a Week Off on the roster, or a missing roster row, and 'last month' has no anchor in a file that ends in September.

> **Trap:** Ambiguous term plus a floating date range.

### 9. What will our leave liability be in December?

*Files:* -

REFUSE. A forecast. Also try 'Show me each employee's leave encashment amount' - there is no such column.

> **Trap:** Forecast and missing column.

## learning

### 1. How many enrolments were completed?

*Files:* enrollments.csv

342 completed of 600 real enrolments (57%). The file has one extra row (EN9999) pointing at a course that does not exist.

> **Trap:** An all-empty 'feedback_comment' column, and 'N/A' scores on everything not completed.

### 2. What is the average score of completed courses?

*Files:* enrollments.csv

72.8% across 342 completed enrolments.

> **Trap:** Scores are percent strings ('82%'). 'N/A' must be skipped, not read as 0.

### 3. Which course category has the most enrolments?

*Files:* enrollments.csv + courses.csv

1. Compliance 131
2. Leadership 122
3. Sales Skills 121
4. Wellbeing 118
5. Technical 108

> **Trap:** Cross-file, plus 'Technical', 'technical ' and 'TECHNICAL' are one category. The orphan course CRS-999 drops out.

### 4. What did completed training cost us in seat fees?

*Files:* enrollments.csv + courses.csv

Rs. 43,17,000 - 342 completed seats priced from courses.csv.

> **Trap:** Cross-file fan-out: one course row prices many enrolment rows. Costs are '₹2,500' text.

### 5. Which department used the most of its training budget?

*Files:* training_budget.csv

1. Sales 160.7% (spent Rs. 11,25,000 of Rs. 7,00,000)
2. Finance 117.0% (spent Rs. 11,70,000 of Rs. 10,00,000)
3. Engineering 79.6% (spent Rs. 10,35,000 of Rs. 13,00,000)
4. Marketing 69.0% (spent Rs. 10,35,000 of Rs. 15,00,000)
5. Operations 67.5% (spent Rs. 6,75,000 of Rs. 10,00,000)
6. Customer Success 55.2% (spent Rs. 8,55,000 of Rs. 15,50,000)

> **Trap:** A Grand Total footer, four quarters per department to sum, and a utilisation column already written as a percent string.

### 6. How many certifications expire between October 2025 and March 2026?

*Files:* certifications.xlsx

31 of 180 certifications.

> **Trap:** A title row above the header, and two date columns where only one is the answer.

### 7. Which department completed the most training hours?

*Files:* enrollments.csv + employees_lite.csv

1. Finance 830 hours
2. Engineering 824 hours
3. Marketing 726 hours
4. Sales 712 hours
5. Operations 650 hours
6. Customer Success 544 hours

> **Trap:** Cross-file on emp_code (a leading-zero text id), plus department spelling variants.

### 8. Who is trained?

*Files:* -

CLARIFY. 'Trained' could mean any completed enrolment, a compliance course completed, or a live certification. The app should ask.

> **Trap:** Ambiguous term.

### 9. Which employees are likely to drop out of their current course?

*Files:* -

REFUSE. A prediction. Also try 'Show me the trainer's rating for each course' - there is no such column.

> **Trap:** Prediction and missing column.

## benefits_and_claims

### 1. What is the total value of approved claims?

*Files:* reimbursement_claims.csv

Rs. 1,94,61,439 across 647 approved claims (of 900 claims worth Rs. 2,73,48,366 in total).

> **Trap:** A title row, a Total footer holding the all-status total, semicolon separators and Windows-1252 encoding. Amounts are 'Rs. 4,500' text with a non-breaking space.

### 2. Which claim type costs the most?

*Files:* reimbursement_claims.csv

1. Mobile Rs. 44,69,498
2. Travel Rs. 43,43,153
3. Internet Rs. 43,04,958
4. Medical Rs. 24,95,593
5. Meal Rs. 22,85,397
6. Books & Periodicals Rs. 15,62,840

> **Trap:** 'Travel', 'travel ' and 'TRAVEL' are one type. Approved claims only. Order matters.

### 3. How many claims were rejected, and why?

*Files:* claim_approvals.csv

109 rejected.
- Receipt not legible: 32
- Late submission: 29
- Duplicate claim: 27
- Outside policy limit: 21

> **Trap:** Dates are MM/DD/YYYY in this file and DD-MM-YYYY in the claims file. One approval (CLM99999) refers to a claim that is not in the claims file.

### 4. What is our annual insurance premium, by plan?

*Files:* insurance_enrolment.xlsx

- Base: 34 people, Rs. 3,94,800, 79 dependants
- Family Floater: 33 people, Rs. 7,75,500, 60 dependants
- Plus: 33 people, Rs. 5,08,200, 66 dependants
Total Rs. 16,78,500 for 100 employees and 205 dependants.

> **Trap:** A title row above the header.

### 5. Who claimed the most this year?

*Files:* reimbursement_claims.csv

1. 004333 Rs. 3,59,823
2. 004027 Rs. 3,51,379
3. 004357 Rs. 3,21,125
4. 004318 Rs. 3,08,848
5. 004351 Rs. 3,06,776

> **Trap:** emp_code is a leading-zero id ('004512') that must stay text; read as a number the codes collide and the ranking is wrong.

### 6. Which employees claimed more than their monthly allowance limit allows?

*Files:* reimbursement_claims.csv + allowances_master.csv

Needs claim type matched to allowance name by hand: the two files share no key. Allowance limits range from Rs. 1,000 to Rs. 1,50,000.

> **Trap:** Cross-file with only a fuzzy text match available ('Travel' vs 'Travel Allowance'). A good look at whether the app invents a join.

### 7. Which department claims the most per head?

*Files:* reimbursement_claims.csv + employees_lite.csv

1. Marketing Rs. 1,90,978 per head
2. Finance Rs. 1,71,703 per head
3. Sales Rs. 1,61,366 per head
4. Operations Rs. 1,55,657 per head
5. Engineering Rs. 1,48,912 per head
6. Customer Success Rs. 1,44,452 per head

> **Trap:** Cross-file where the key is emp_code on one side and employee_id on the other, and the denominator is a head count from the other file, not a row count.

### 8. How much have we settled in claims?

*Files:* -

CLARIFY. 'Settled' could mean status Approved in the claims file or an approved_amount above zero in the approvals file; the two disagree because pending claims have no approval row at all.

> **Trap:** Ambiguous term that two files answer differently.

### 9. What will claims cost us next quarter?

*Files:* -

REFUSE. A forecast. Also try 'Show me the GST on each claim' - there is no such column.

> **Trap:** Forecast and missing column.

## retail_sales

### 1. What were total net sales in the first half of 2025?

*Files:* daily_sales_q1.csv + daily_sales_q2.csv

Rs. 17,44,34,504 over 121,632 sale lines (Q1 Rs. 8,67,23,382, Q2 Rs. 8,77,11,122).

> **Trap:** The two quarter files must combine, and daily_sales_q2.csv ends with a Grand Total row that adds the whole quarter a second time.

### 2. Which region sells the most?

*Files:* daily_sales_q1.csv + daily_sales_q2.csv + stores.csv

1. South Rs. 4,37,86,214
2. West Rs. 4,36,39,798
3. North Rs. 4,35,39,786
4. East Rs. 4,34,68,707

> **Trap:** Cross-file fan-out (one store row prices 60,000 sale lines) plus 'West', 'west ' and 'WEST' being one region. Order matters.

### 3. Which product category earns the most?

*Files:* daily_sales_q1.csv + daily_sales_q2.csv + products.xlsx

1. Beverages Rs. 3,94,83,626
2. Frozen Rs. 3,30,47,362
3. Personal Care Rs. 3,23,82,027
4. Snacks Rs. 2,73,76,172
5. Dairy Rs. 2,15,43,606
6. Home Care Rs. 2,06,01,712

> **Trap:** Cross-file on sku, with case and trailing-space variants in the category column and an all-empty 'discontinued_on' column in the workbook.

### 4. Which five stores sell the most?

*Files:* daily_sales_q1.csv + daily_sales_q2.csv + stores.csv

1. 0030 (Kochi) Rs. 73,85,834
2. 0027 (Lucknow) Rs. 73,36,118
3. 0032 (Patna) Rs. 73,31,631
4. 0024 (Surat) Rs. 73,27,600
5. 0028 (Bengaluru) Rs. 73,19,051

> **Trap:** store_id is '0010' and must stay text; read as a number it loses the leading zero and joins nothing.

### 5. How much of our revenue came from discounted lines?

*Files:* daily_sales_q1.csv + daily_sales_q2.csv

Rs. 7,45,04,450 from 54,685 discounted lines, 42.7% of net sales.

> **Trap:** 'discount' is a percent string ('10%'), not a number.

### 6. What did we refund, and for what reason?

*Files:* returns.csv

Rs. 30,08,436 over 1500 returns (the file has 1501 rows: RET9999 points at a SKU and a store that do not exist).
- Damaged: Rs. 8,96,488
- Wrong item: Rs. 7,82,651
- Expired: Rs. 5,72,677
- Changed mind: Rs. 4,25,558
- Quality issue: Rs. 3,31,062

> **Trap:** Dates are MM/DD/YYYY here and DD-MM-YYYY in the sales files. UTF-8 BOM. Orphan keys on two columns at once.

### 7. Which store has the highest sales per head of store staff?

*Files:* daily_sales_q1.csv + daily_sales_q2.csv + staff_by_store.csv

1. 0024 Rs. 7,32,760 per head
2. 0017 Rs. 6,62,770 per head
3. 0011 Rs. 6,62,644 per head
4. 0033 Rs. 6,02,898 per head
5. 0021 Rs. 5,99,333 per head

> **Trap:** Four staff rows per store must be summed before the division; joining first and dividing after multiplies the sales by four (classic fan-out). staff_by_store.csv is semicolon-separated Windows-1252 with a title row and a Total footer.

### 8. How are our best stores doing?

*Files:* -

CLARIFY. 'Best' could be net sales, units, sales per day open, or the lowest return rate. The app should ask which.

> **Trap:** Ambiguous term.

### 9. What will sales be in Q3?

*Files:* -

REFUSE. A forecast. Also try 'Show me the footfall per store' - there is no such column.

> **Trap:** Forecast and missing column.

## performance_and_engagement

### 1. How many OKRs hit their target?

*Files:* okrs.csv

95 of 300 OKRs (32%).

> **Trap:** 'progress_percent' is already a percent string; recomputing from target and achieved is the safe route.

### 2. Which department is furthest along on its OKRs?

*Files:* okrs.csv

1. Engineering 89% average progress
2. Sales 87% average progress
3. Marketing 82% average progress
4. Customer Success 82% average progress
5. Operations 77% average progress
6. Finance 76% average progress

> **Trap:** Department spelling variants. Average of ratios, not ratio of sums. Order matters.

### 3. How are final ratings distributed?

*Files:* review_ratings.xlsx

- 1: 5 people
- 2: 24 people
- 3: 53 people
- 4: 28 people
- 5: 10 people
Average final rating 3.12 across 120 reviews.

> **Trap:** A title row AND a two-row header with merged group cells above the real header. If the app reads row 2 as the header, every column is called Ratings or None.

### 4. What is the average hike by final rating?

*Files:* review_ratings.xlsx

- rating 1: 6.02%
- rating 2: 8.49%
- rating 3: 10.59%
- rating 4: 12.87%
- rating 5: 15.33%

> **Trap:** Hike is a percent string under a two-row header.

### 5. Which engagement question scored the worst?

*Files:* engagement_survey.csv

"I can see a path to grow here" at 3.64/5.
- I know what is expected of me at work: 3.66
- I have the tools I need to do my job well: 3.66
- My manager gives me useful feedback: 3.65
- I can see a path to grow here: 3.64
- I would recommend this company to a friend: 3.66
- My workload is manageable: 3.69
- I feel respected by my team: 3.64
- Leadership communicates openly: 3.7

> **Trap:** Wide format: one column per question, with blanks that must be skipped rather than counted as zero. The headers are whole sentences.

### 6. Which department is least engaged?

*Files:* engagement_survey.csv

1. Sales 3.61/5 average across all questions
2. Finance 3.62/5 average across all questions
3. Marketing 3.66/5 average across all questions
4. Customer Success 3.67/5 average across all questions
5. Engineering 3.67/5 average across all questions
6. Operations 3.72/5 average across all questions

> **Trap:** Wide format plus department spelling variants; the average has to run across eight columns and then across rows.

### 7. Why are people leaving, and would we rehire them?

*Files:* exit_interviews.csv

45 exits (the file has 46 rows: emp_code 009999 matches no master file). Would rehire: 39 yes, 6 no. Median tenure 39 months. Reasons are free text - pay, relocation, manager churn, higher studies, commute.

> **Trap:** Free text with commas, quotes and newlines inside cells. Dates as '3 Mar 2025'. An orphan emp_code.

### 8. What is the average final rating by manager location?

*Files:* review_ratings.xlsx + employees_lite.csv + managers.csv

- Chennai Plant: 3.38
- Pune Campus: 3.11
- Bengaluru HQ: 3.00
- Remote: 2.96
(20 managers, average span of control 9.1.)

> **Trap:** Three files deep: ratings sit under a two-row header, employees_lite.csv carries the manager_id, and managers.csv is semicolon-separated Windows-1252 with a title row.

### 9. Who are our top performers?

*Files:* -

CLARIFY. 'Top performer' could be final rating 5, OKR attainment above 100%, or the largest hike. The app should ask.

> **Trap:** Ambiguous term.

### 10. Who is likely to resign next quarter?

*Files:* -

REFUSE. A prediction about named people. Also try 'Show me each employee's flight risk score' - there is no such column.

> **Trap:** Prediction and missing column.

## company_fintech_full

### 1. What was our attrition rate in 2025?

*Files:* staff_master.xlsx (both sheets)

12.4% - 103 separations against an average headcount of 834 (opening 870, closing 797).

> **Trap:** The leavers are on a second sheet. Read one sheet only and attrition is 0% or 100%. 'Average headcount' is the denominator; simple leavers/closing gives 12.9% instead.

### 2. How many people work here, by band?

*Files:* staff_master.xlsx

797 active staff.
- B1: 210
- B2: 237
- B3: 153
- B4: 111
- B5: 62
- B6: 24

> **Trap:** Two sheets: only the active one counts. staff_no is a six-digit text id, not a number.

### 3. What is the average fixed pay by band?

*Files:* staff_master.xlsx

Rupee-paid staff only (the Singapore desk is paid in USD):
- B1: Rs. 4,29,476
- B2: Rs. 7,30,968
- B3: Rs. 11,72,926
- B4: Rs. 19,38,340
- B5: Rs. 33,45,918
- B6: Rs. 53,88,917
725 of 797 active staff are paid in INR; the other 72 are in USD and must not be averaged in.

> **Trap:** The pay column holds INR and USD amounts with a separate currency column. Averaging without filtering on currency mixes two units - the honest answer names the split.

### 4. What was the total net payroll in 2025, month by month?

*Files:* payroll_h1_2025.csv + payroll_h2_2025.csv

INR payroll only, Rs. 89,39,60,012 across 9,229 INR payslips.
- Jan 2025: Rs. 7,56,15,923
- Feb 2025: Rs. 7,50,20,874
- Mar 2025: Rs. 8,85,51,187
- Apr 2025: Rs. 7,47,94,858
- May 2025: Rs. 7,36,71,719
- Jun 2025: Rs. 7,30,55,755
- Jul 2025: Rs. 7,23,36,087
- Aug 2025: Rs. 7,14,37,444
- Sep 2025: Rs. 8,31,21,695
- Oct 2025: Rs. 6,92,68,064
- Nov 2025: Rs. 6,90,69,887
- Dec 2025: Rs. 6,80,16,512
(USD payslips: 904, $ 924,170.18.)

> **Trap:** The two half-year files must combine, the Grand Total row at the foot of H2 must be dropped, and USD rows must not be added to INR rows - the amount column holds both, with the unit in the currency column beside it, so a plain SUM is a wrong number that looks right. March and September carry variable pay, so those months are higher on purpose.

### 5. Which cost centre has the most people, and which hit its revenue target?

*Files:* staff_master.xlsx + revenue_targets.csv

Headcount:
1. CC-200 Payments 136
2. CC-500 Customer Ops 136
3. CC-300 Risk 134
4. CC-400 Technology 132
5. CC-600 Corporate 130
6. CC-100 Lending 129

Target attainment:
1. CC-200 Payments 110.1%
2. CC-500 Customer Ops 95.6%
3. CC-100 Lending 91.8%
4. CC-400 Technology 90.8%
5. CC-300 Risk 77.6%
6. CC-600 Corporate 77.4%

> **Trap:** Cross-file on cost_centre, where the master has 'CC-200 Payments', 'cc-200 payments ' and 'CC-200 PAYMENTS'. revenue_targets.csv is semicolon-separated Windows-1252 with a title row and a Total footer.

### 6. Why did people leave?

*Files:* staff_master.xlsx (sheet 'Separated 2025')

1. Personal reasons 22
2. Performance 20
3. Higher studies 20
4. Better opportunity 17
5. Compensation 13
6. Relocation 11
103 separations in total.

> **Trap:** Only the separated sheet has a reason; the active sheet's column is empty throughout.

### 7. How are performance ratings distributed?

*Files:* performance_reviews.csv

- 1: 30 people
- 2: 96 people
- 3: 341 people
- 4: 243 people
- 5: 87 people
Average 3.33 across 797 reviewed staff. 120 promoted.

> **Trap:** A title row, and one orphan row (staff_no 999999) that matches nobody in the master.

### 8. What is the average LOP per person per month?

*Files:* attendance_monthly.csv

1.66 days across 2,400 real attendance rows (2,430 rows in the file: 30 are a duplicated January block).

> **Trap:** Duplicated rows inflate the count; blanks and 'N/A' in lop_days must be skipped, not read as zero. The file has a UTF-8 BOM.

### 9. Who are our expensive people?

*Files:* -

CLARIFY. 'Expensive' could mean fixed pay, fixed plus variable, or actual net pay drawn in 2025 - and the currency column means the comparison needs a unit first.

> **Trap:** Ambiguous term over a mixed-currency column.

### 10. What will attrition be next year?

*Files:* -

REFUSE. A forecast. Also try 'Show me each person's notice period' - there is no such column in any of these files.

> **Trap:** Forecast and missing column.

## company_manufacturing_full

### 1. How many people work at each plant, permanent versus contractor?

*Files:* workforce_master.csv

2,093 active workers of 2,500 on the register.
- Chakan Plant: 350 permanent, 168 contractor
- Haridwar Plant: 367 permanent, 165 contractor
- Hosur Plant: 350 permanent, 176 contractor
- Sanand Plant: 335 permanent, 182 contractor

> **Trap:** A title row above the header, plant names typed four ways ('Chakan Plant', 'chakan plant ', 'CHAKAN PLANT'), and leavers still on the register - filter on an empty date_of_leaving.

### 2. What was the attrition rate in 2025, and is it worse for contractors?

*Files:* workforce_master.csv

17.7% overall - 407 leavers against an average headcount of 2,296. Contractors leave at 27.6% of their own head count, permanents at 9.3%.

> **Trap:** date_of_leaving is blank for everyone still employed; counting blanks as a leaving date makes attrition 100%.

### 3. What did wages cost, month by month?

*Files:* wage_register_h1.csv

Rs. 34,28,42,088 net over six months (14,494 wage rows).
- Jan 2025: Rs. 5,93,93,820
- Feb 2025: Rs. 5,81,29,193
- Mar 2025: Rs. 5,78,34,319
- Apr 2025: Rs. 5,67,91,168
- May 2025: Rs. 5,59,90,002
- Jun 2025: Rs. 5,47,03,583
PF Rs. 2,38,24,000, ESI Rs. 13,36,402.

> **Trap:** Semicolon-separated Windows-1252 with a Grand Total footer that repeats every total. Counted in, every number here doubles.

### 4. How much overtime is each plant running, and what did it cost?

*Files:* shift_attendance.csv + wage_register_h1.csv

1. Sanand Plant 58,218.9 hours
2. Haridwar Plant 57,696.6 hours
3. Hosur Plant 57,252.9 hours
4. Chakan Plant 56,869.1 hours
Overtime wages across all plants: Rs. 5,62,35,991 (16.4% of net wages).

> **Trap:** Cross-file: the hours are in attendance, the money is in the wage register, and the attendance file carries 50 duplicated rows plus one orphan ticket (099999) that inflates the hours if kept. Dates are MM/DD/YYYY here, DD-MM-YYYY in the master.

### 5. Which plant has the worst safety record?

*Files:* safety_incidents.csv

1. Sanand Plant: 36 incidents, 158 days lost
2. Haridwar Plant: 44 incidents, 104 days lost
3. Hosur Plant: 31 incidents, 87 days lost
4. Chakan Plant: 29 incidents, 72 days lost
18 were lost-time injuries, 16 days lost between them.

> **Trap:** 'Worst' by count and by days lost can rank differently - the answer should say which it used. Dates read '3 Mar 2025'; the file has a UTF-8 BOM.

### 6. Which plant is closest to its production target?

*Files:* production_targets.xlsx (four sheets)

1. Hosur Plant 93.1% of target
2. Haridwar Plant 92.4% of target
3. Chakan Plant 90.7% of target
4. Sanand Plant 90.6% of target
All plants: 722,337 units against a target of 788,000.

> **Trap:** One sheet per plant with identical columns - all four must combine, and each sheet has its own title row above the header.

### 7. What is the overtime cost per unit produced, by plant?

*Files:* wage_register_h1.csv + workforce_master.csv + production_targets.xlsx

- Chakan Plant: Rs. 72 per unit
- Haridwar Plant: Rs. 81 per unit
- Hosur Plant: Rs. 82 per unit
- Sanand Plant: Rs. 76 per unit

> **Trap:** Three files and a fan-out: one worker row prices six wage rows, and production is per plant per line per month. Join at the wrong grain and the cost is multiplied.

### 8. How many workers are absent?

*Files:* -

CLARIFY. 'Absent' could be absent_days in the attendance file, days_worked below the month's working days in the wage register, or people who have left. The app should ask.

> **Trap:** Ambiguous term that three files answer differently.

### 9. How many units will Hosur produce next quarter?

*Files:* -

REFUSE. A forecast. Also try 'Show me the scrap rate per line' - there is no such column.

> **Trap:** Forecast and missing column.
