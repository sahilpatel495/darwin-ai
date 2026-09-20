"""Generate frontend fixtures from the Pydantic contracts so mock data can never drift.

Run: uv run python backend/scripts/make_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path

from app.contracts import (
    Answer, Attempt, CalibrationBucket, ChartSpec, Clarification, ClarifyOption, Coercion,
    Confidence, CrossCheck, EvalCase, EvalReport, ModelPayload, ModelScore, ResultTable,
    StepEvent, Work,
)
from tests.fixtures import make_session

OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "fixtures"


def catalog():
    cat = make_session().catalog
    pay = next(t for t in cat.tables if t.name == "salary_register")
    pay.sheet = "Register"
    pay.health.skipped_title_rows = 3
    pay.health.dropped_total_rows = 1
    pay.health.duplicate_rows = 6
    pay.health.duplicates_removed = True
    pay.health.date_format = "DD/MM/YYYY"
    pay.health.preserved_id_columns = ["emp_code"]
    pay.health.null_hotspots = {"net": 0.08}
    pay.health.coercions = [
        Coercion(column="gross", to_type="currency", unparseable=3, examples=["TBD", "N/A"],
                 detail="Parsed ₹ strings with Indian digit grouping"),
        Coercion(column="pay_month", to_type="date", detail="Parsed day-first dates"),
    ]
    pay.health.warnings = ["3 values in gross could not be read as numbers and were left empty."]
    cat.suggested_questions = [
        "What is the total gross pay by department?",
        "How has headcount changed month by month?",
        "What is the attrition rate for FY25?",
        "Which location has the highest average CTC?",
    ]
    return cat


PAYLOAD = ModelPayload(
    purpose="generate", provider="groq", model="openai/gpt-oss-120b", latency_ms=840,
    messages=[
        {"role": "system", "content": "You translate questions into one DuckDB SELECT..."},
        {"role": "user", "content": "TABLE employees (8 rows) from employees.csv\n  emp_id text [id, unique]\n  email text [PII:email, values hidden]\n\nQuestion: total gross pay by department"},
    ],
)


def bar_answer() -> Answer:
    rows = [["Engineering", 1200000.0], ["Sales", 633334.0], ["HR", 270000.0]]
    return Answer(
        id="a1", kind="answer", question="What is the total gross pay by department?",
        text="Engineering has the highest total gross pay at ₹12.00 L, followed by Sales at ₹6.33 L and HR at ₹2.70 L.",
        chart=ChartSpec(type="bar", x="department", y=["total_gross"], title="Total gross pay by department", value_format="currency_inr"),
        table=ResultTable(columns=["department", "total_gross"], rows=rows,
                          display=[["Engineering", "₹12.00 L"], ["Sales", "₹6.33 L"], ["HR", "₹2.70 L"]], row_count=3),
        work=Work(
            interpretation="Sum of gross pay from the salary register, grouped by each employee's department.",
            reading="Joins employees to the salary register on employee ID, then adds up gross pay for each department.",
            plan=["Join employees to salary_register on emp_id = emp_code", "Sum gross per department", "Sort from highest to lowest"],
            sql="SELECT e.department, sum(s.gross) AS total_gross\nFROM employees e JOIN salary_register s ON e.emp_id = s.emp_code\nGROUP BY e.department ORDER BY total_gross DESC",
            tables_used=["employees", "salary_register"], rows_scanned=24,
            assumptions=["All pay months in the file are included (Jan–Feb 2025)."],
            caveats=["6 exact duplicate rows in salary_register were excluded.", "8% of net values are empty (not used here)."],
            attempts=[Attempt(sql="SELECT department, sum(gross) FROM salary_register GROUP BY 1", model="openai/gpt-oss-120b", reason="initial", error='Column "department" not found in salary_register. Did you mean employees.department?'),
                      Attempt(sql="SELECT e.department, sum(s.gross) ...", model="openai/gpt-oss-120b", reason="guard_rejected")],
            payloads=[PAYLOAD],
            cross_check=CrossCheck(status="agreed", model="deepseek-v4-flash", detail="A second model wrote different SQL and got the same 3 rows."),
            timings_ms={"generate": 840, "execute": 12, "narrate": 410},
        ),
        confidence=Confidence(level="high", score=0.8, reasons=["A second model independently reached the same result.", "One SQL repair was needed.", "100% of join keys matched."]),
        followups=["Split that by location", "Show the monthly trend", "Which department has the highest average gross?"],
    )


def kpi_answer() -> Answer:
    return Answer(
        id="a2", kind="answer", question="What is the attrition rate for 2025?",
        text="Attrition for 2025 is 28.6%: 2 exits against an average headcount of 7.",
        chart=ChartSpec(type="kpi", y=["attrition_pct"], title="Attrition rate, 2025", value_format="percent"),
        table=ResultTable(columns=["exits", "avg_headcount", "attrition_pct"], rows=[[2, 7.0, 28.6]], display=[["2", "7", "28.6%"]], row_count=1),
        work=Work(interpretation="Exits in 2025 divided by average headcount in 2025.", reading="Counts employees whose exit date falls in 2025 and divides by the average of opening and closing headcount.",
                  plan=["Count exits in 2025", "Average opening and closing headcount", "Divide and express as a percentage"],
                  sql="WITH ... SELECT exits, avg_headcount, round(100.0 * exits / avg_headcount, 1) AS attrition_pct FROM ...",
                  tables_used=["employees"], rows_scanned=8, metrics_used=["attrition_rate"], payloads=[PAYLOAD],
                  cross_check=CrossCheck(status="disagreed", model="deepseek-v4-flash", detail="A second model got 25.0% by dividing by closing headcount instead of the average.")),
        confidence=Confidence(level="medium", score=0.6, reasons=["Used the vetted definition of attrition rate.", "A second model reached a different number (25.0%)."]),
        followups=["Break attrition down by department", "Show exits by reason"],
    )


def line_answer() -> Answer:
    months = ["2025-01-01", "2025-02-01", "2025-03-01", "2025-04-01", "2025-05-01", "2025-06-01"]
    values = [168, 170, 165, 171, 169, 172]
    return Answer(
        id="a3", kind="answer", question="Show total days present per month across both attendance files",
        text="Total days present ranged from 165 in Mar 2025 to 172 in Jun 2025.",
        chart=ChartSpec(type="line", x="month", y=["days_present"], title="Days present per month"),
        table=ResultTable(columns=["month", "days_present"], rows=[[m, v] for m, v in zip(months, values)],
                          display=[[f"{m[5:7]}/2025", str(v)] for m, v in zip(months, values)], row_count=6),
        work=Work(interpretation="Monthly total of days_present across Q1 and Q2 files.", sql="SELECT month, sum(days_present) AS days_present FROM attendance_all GROUP BY 1 ORDER BY 1",
                  tables_used=["attendance_all"], rows_scanned=48, payloads=[PAYLOAD], cross_check=CrossCheck(status="unavailable", detail="The second model was rate-limited.")),
        confidence=Confidence(level="high", score=0.8, reasons=["No repairs needed.", "Cross-check was unavailable."]),
    )


def clarify_answer() -> Answer:
    return Answer(
        id="a4", kind="clarify", question="What is the average salary by department?",
        text='"Salary" could mean more than one column in your data. Which one should I use?',
        clarification=Clarification(term="salary", question="Which salary figure do you mean?", options=[
            ClarifyOption(label="CTC, annual (employees.ctc)", value="employees.ctc"),
            ClarifyOption(label="Gross pay, monthly (salary_register.gross)", value="salary_register.gross"),
            ClarifyOption(label="Net pay, monthly (salary_register.net)", value="salary_register.net"),
        ]),
    )


def refusal_answer() -> Answer:
    return Answer(
        id="a5", kind="refusal", question="What is our customer churn rate?",
        text="I can't answer that from the uploaded files: none of them contain customer or subscription data.",
        missing="A table of customers with a start date and an end (churn) date.",
        work=Work(interpretation="Customer churn needs customer records with start and end dates.", payloads=[PAYLOAD]),
    )


def report() -> EvalReport:
    cases = [
        EvalCase(id="tot-01", category="totals", split="dev", question="What is the total gross pay for 2025?", expected_kind="answer", got_kind="answer", passed=True, confidence="high", latency_ms=2100),
        EvalCase(id="hr-03", category="hr_metrics", split="dev", question="What is the attrition rate for FY25?", expected_kind="answer", got_kind="answer", passed=False, confidence="medium", latency_ms=3900, repairs=1, note="Used closing headcount instead of the average."),
        EvalCase(id="una-02", category="unanswerable", split="holdout", question="What is our customer churn rate?", expected_kind="refusal", got_kind="refusal", passed=True, latency_ms=1500),
    ]
    return EvalReport(generated_at="2026-09-20T21:00:00+05:30", model="openai/gpt-oss-120b", runs=3, total=40, accuracy=0.925,
                      accuracy_holdout=0.9, trust_score=0.88, by_category={"totals": 1.0, "joins": 0.9, "hr_metrics": 0.8, "unanswerable": 1.0},
                      p50_ms=2400, p95_ms=5200, repair_rate=0.12, crosscheck_agreement=0.86,
                      calibration={"high": CalibrationBucket(n=29, accuracy=0.97), "medium": CalibrationBucket(n=8, accuracy=0.75), "low": CalibrationBucket(n=3, accuracy=0.33)},
                      models=[ModelScore(model="openai/gpt-oss-120b", accuracy=0.925, p50_ms=2400), ModelScore(model="deepseek-v4-flash", accuracy=0.9, p50_ms=4100)],
                      cases=cases)


STEPS = [
    StepEvent(stage="understand", status="ok", detail="No ambiguous terms"),
    StepEvent(stage="generate", status="ok", detail="openai/gpt-oss-120b wrote a 3-step plan"),
    StepEvent(stage="guard", status="warn", detail="Rejected: unknown column department in salary_register"),
    StepEvent(stage="repair", status="ok", detail="Rewrote the query with a join"),
    StepEvent(stage="guard", status="ok", detail="Read-only, 2 tables, 3 columns"),
    StepEvent(stage="execute", status="ok", detail="3 rows in 12 ms"),
    StepEvent(stage="verify", status="ok", detail="Second model agreed; no fan-out risk"),
    StepEvent(stage="chart", status="ok", detail="Bar chart"),
    StepEvent(stage="narrate", status="ok", detail="All numbers grounded"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "catalog.json": catalog(), "answer_bar.json": bar_answer(), "answer_kpi.json": kpi_answer(),
        "answer_line.json": line_answer(), "answer_clarify.json": clarify_answer(),
        "answer_refusal.json": refusal_answer(), "eval_report.json": report(),
    }
    for name, model in files.items():
        (OUT / name).write_text(model.model_dump_json(indent=2), encoding="utf-8")
    (OUT / "steps.json").write_text(json.dumps([s.model_dump() for s in STEPS], indent=2), encoding="utf-8")
    print(f"wrote {len(files) + 1} fixtures to {OUT}")


# --------------------------------------------------------------------------
# The no-AI half: automatic overview and guided analyses
# --------------------------------------------------------------------------
from app.insights.models import (  # noqa: E402
    AnalysisCatalog, AnalysisInput, AnalysisKind, AnalysisOption, ColumnChoice, Dashboard,
    DashboardSection, InsightTile,
)


def _table(columns, rows, display=None) -> ResultTable:
    display = display or [[str(v) for v in r] for r in rows]
    return ResultTable(columns=columns, rows=rows, display=display, row_count=len(rows))


def tiles() -> list[InsightTile]:
    months = [f"2025-{m:02d}-01" for m in range(1, 13)]
    pay = [4.38, 4.41, 4.45, 4.49, 4.52, 4.57, 4.6, 4.64, 4.69, 4.72, 4.76, 4.73]
    return [
        InsightTile(id="kpi-headcount", title="Active employees", kind="kpi", statement="430 people are active today.",
                    insights=["70 have left since 2015", "14% of everyone ever hired"],
                    chart=ChartSpec(type="kpi", y=["active_employees"], title="Active employees"),
                    table=_table(["active_employees"], [[430]], [["430"]]), sql="SELECT count(*) AS active_employees FROM employees WHERE exit_date IS NULL",
                    tables_used=["employees"], ask="How has headcount changed year by year?"),
        InsightTile(id="kpi-pay", title="Gross pay, 2025", kind="kpi", statement="Total gross pay in 2025 was ₹54.67 Cr.",
                    insights=["₹4.56 Cr a month on average"], chart=ChartSpec(type="kpi", y=["total_gross"], title="Gross pay, 2025", value_format="currency_inr"),
                    table=_table(["total_gross"], [[546657000.0]], [["₹54.67 Cr"]]), sql="SELECT sum(gross) AS total_gross FROM salary_register", tables_used=["salary_register"]),
        InsightTile(id="trend-pay", title="Gross pay by month", kind="trend", statement="Gross pay rose from ₹4.38 Cr in Jan 2025 to ₹4.73 Cr in Dec 2025; the highest month was Nov 2025 at ₹4.76 Cr.",
                    insights=["Up 8.0% over the year", "Highest: Nov 2025"], chart=ChartSpec(type="area", x="pay_month", y=["total_gross"], title="Gross pay by month", value_format="currency_inr"),
                    table=_table(["pay_month", "total_gross"], [[m, v * 1e7] for m, v in zip(months, pay)], [[m[:7], f"₹{v:.2f} Cr"] for m, v in zip(months, pay)]),
                    sql="SELECT date_trunc('month', pay_month) AS pay_month, sum(gross) AS total_gross FROM salary_register GROUP BY 1 ORDER BY 1", tables_used=["salary_register"],
                    ask="Why did gross pay dip in December 2025?"),
        InsightTile(id="break-dept", title="Employees by department", kind="breakdown", statement="Engineering is the largest department with 168 people; Finance is the smallest with 32.",
                    insights=["Top 2 departments hold 58% of people", "Largest is 5.3× the smallest"], chart=ChartSpec(type="bar", x="department", y=["employees"], title="Employees by department"),
                    table=_table(["department", "employees"], [["Engineering", 168], ["Sales", 121], ["Support", 84], ["Operations", 55], ["HR", 40], ["Finance", 32]]),
                    sql="SELECT department, count(*) AS employees FROM employees GROUP BY 1 ORDER BY 2 DESC", tables_used=["employees"]),
        InsightTile(id="share-gender", title="Gender mix", kind="share", statement="Women make up 41% of employees.",
                    chart=ChartSpec(type="donut", x="gender", y=["employees"], title="Gender mix"),
                    table=_table(["gender", "employees"], [["Male", 282], ["Female", 205], ["Not stated", 13]]), sql="SELECT gender, count(*) AS employees FROM employees GROUP BY 1", tables_used=["employees"]),
        InsightTile(id="dist-ctc", title="How annual CTC is spread", kind="distribution", statement="Half of employees earn between ₹6.2 L and ₹16.8 L; the median is ₹10.4 L.",
                    insights=["Median ₹10.4 L", "Top 10% earn above ₹28.0 L"], chart=ChartSpec(type="histogram", x="ctc_band", y=["employees"], title="How annual CTC is spread"),
                    table=_table(["ctc_band", "employees"], [["Under ₹5 L", 74], ["₹5–10 L", 161], ["₹10–15 L", 118], ["₹15–25 L", 92], ["₹25–40 L", 41], ["Over ₹40 L", 14]]),
                    sql="SELECT ... width_bucket ...", tables_used=["employees"]),
        InsightTile(id="stack-loc", title="Departments across locations", kind="comparison", statement="Bengaluru holds the most people in every department except Sales, where Mumbai leads.",
                    chart=ChartSpec(type="stacked_bar", x="location", y=["employees"], series="department", title="Departments across locations"),
                    table=_table(["location", "department", "employees"], [[loc, d, n] for loc, row in {"Bengaluru": (62, 28, 22), "Mumbai": (30, 41, 16), "Hyderabad": (34, 20, 19), "Pune": (26, 18, 15), "Gurugram": (16, 14, 12)}.items() for d, n in zip(("Engineering", "Sales", "Support"), row)]),
                    sql="SELECT location, department, count(*) AS employees FROM employees GROUP BY 1, 2", tables_used=["employees"]),
        InsightTile(id="heat-rating", title="Ratings by grade", kind="relationship", statement="Rating 3 is the most common in every grade; grade L5 has the highest share of 5s.",
                    chart=ChartSpec(type="heatmap", x="grade", y=["employees"], series="rating", title="Ratings by grade"),
                    table=_table(["grade", "rating", "employees"], [[g, r, max(1, (7 - abs(r - 3) * 3) * (6 - i))] for i, g in enumerate(("L1", "L2", "L3", "L4", "L5")) for r in range(1, 6)]),
                    sql="SELECT e.grade, p.rating, count(*) ...", tables_used=["employees", "performance_reviews"]),
        InsightTile(id="quality", title="What to check in your data", kind="quality", statement="1 of 7 tables needs a look: 3 amounts in the salary register could not be read.",
                    insights=["6 duplicate rows removed", "4 personal-data columns hidden from the AI", "93% of employees have pay records"]),
    ]


def dashboard() -> Dashboard:
    t = {x.id: x for x in tiles()}
    return Dashboard(session_id="fixture", catalog_version=1, generated_ms=84, sections=[
        DashboardSection(title="People", description="Who works here today.", tiles=[t["kpi-headcount"], t["break-dept"], t["share-gender"], t["stack-loc"]]),
        DashboardSection(title="Pay", description="What was paid, and how it is spread.", tiles=[t["kpi-pay"], t["trend-pay"], t["dist-ctc"]]),
        DashboardSection(title="Performance", tiles=[t["heat-rating"]]),
        DashboardSection(title="Data quality", tiles=[t["quality"]]),
    ])


def analyses() -> AnalysisCatalog:
    m, c, d = ["measure"], ["category"], ["date"]
    agg = AnalysisOption(key="aggregate", label="How to combine", choices=["sum", "average", "count", "median", "min", "max"])
    kinds = [
        AnalysisKind(key="breakdown", name="Break down", description="Split one number by a group.", example="Average CTC by department", inputs=[AnalysisInput(key="measure", label="What to measure", accepts=m), AnalysisInput(key="by", label="Split by", accepts=c)], options=[agg]),
        AnalysisKind(key="trend", name="Trend over time", description="See how a number moves month by month.", example="Gross pay by month", inputs=[AnalysisInput(key="measure", label="What to measure", accepts=m), AnalysisInput(key="date", label="Over which date", accepts=d), AnalysisInput(key="by", label="Separate lines for", accepts=c, optional=True)], options=[agg, AnalysisOption(key="grain", label="Every", choices=["month", "quarter", "year", "week"])]),
        AnalysisKind(key="top_n", name="Top and bottom", description="Find the highest and lowest groups.", example="Top 5 locations by headcount", inputs=[AnalysisInput(key="measure", label="What to measure", accepts=m), AnalysisInput(key="by", label="Rank what", accepts=c)], options=[agg, AnalysisOption(key="top_n", label="How many", choices=["5", "10", "20"])]),
        AnalysisKind(key="distribution", name="Distribution", description="See how values are spread, with the median and the tails.", example="How CTC is spread", inputs=[AnalysisInput(key="measure", label="Which number", accepts=m)]),
        AnalysisKind(key="share", name="Share of total", description="What part of the whole each group makes up.", example="Share of gross pay by department", inputs=[AnalysisInput(key="measure", label="What to measure", accepts=m), AnalysisInput(key="by", label="Split by", accepts=c)], options=[agg]),
        AnalysisKind(key="pivot", name="Two-way table", description="Cross one group with another.", example="Headcount by department and location", inputs=[AnalysisInput(key="measure", label="What to measure", accepts=m), AnalysisInput(key="by", label="Rows", accepts=c), AnalysisInput(key="across", label="Columns", accepts=c)], options=[agg]),
        AnalysisKind(key="correlation", name="Do two numbers move together?", description="Compare two measures row by row.", example="CTC against rating", inputs=[AnalysisInput(key="measure", label="First number", accepts=m), AnalysisInput(key="measure_b", label="Second number", accepts=m)]),
        AnalysisKind(key="change", name="Change between periods", description="Compare one period with the one before.", example="Gross pay, this month vs last", inputs=[AnalysisInput(key="measure", label="What to measure", accepts=m), AnalysisInput(key="date", label="Over which date", accepts=d), AnalysisInput(key="by", label="Split by", accepts=c, optional=True)], options=[agg, AnalysisOption(key="grain", label="Compare by", choices=["month", "quarter", "year"])]),
        AnalysisKind(key="outliers", name="Unusual values", description="List the rows far outside the usual range.", example="Unusually high deductions", inputs=[AnalysisInput(key="measure", label="Which number", accepts=m)]),
    ]
    cat = make_session().catalog
    kind_of = {"currency": "measure", "integer": "measure", "decimal": "measure", "percent": "measure", "date": "date"}
    columns = [ColumnChoice(ref=f"{t.name}.{c.name}", label=c.label, table_label=t.source_file, kind=kind_of.get(c.type, "category"))
               for t in cat.tables if not t.is_view for c in t.columns if not c.pii and not c.is_identifier]
    return AnalysisCatalog(kinds=kinds, columns=columns)


def write_insight_fixtures() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dashboard.json").write_text(dashboard().model_dump_json(indent=2), encoding="utf-8")
    (OUT / "analyses.json").write_text(analyses().model_dump_json(indent=2), encoding="utf-8")
    (OUT / "tile.json").write_text(tiles()[3].model_dump_json(indent=2), encoding="utf-8")
    print("wrote 3 insight fixtures")


if __name__ == "__main__":
    main()
    write_insight_fixtures()
