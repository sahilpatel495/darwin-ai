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


if __name__ == "__main__":
    main()
