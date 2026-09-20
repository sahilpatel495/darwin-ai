"""Every answerable challenge question, proved without a model.

The challenge set is the one place where a bad question is expensive: it is never tuned on, so
a question that is impossible to answer *correctly* would show up as a permanent failure and be
read as a weakness of the app. So each question here is handed the SQL a careful analyst would
write, run through the real ingest, the real session and the real pipeline (only the model is
scripted), and its result is compared with eval/truth_challenge.py by the real comparer.

Three things have to agree for one of these to pass, which is the point: the question means what
the SQL does, the truth function computes the same thing from the clean files, and the comparer
can see that they match. A failure here is a bug in the question, not in the app.

Not covered: ch-15 and ch-16 expect refusals, and there is no SQL to prove.
"""

import json

import pytest
from app.config import settings
from app.contracts import AskRequest
from app.llm.fake import FakeLLM

from eval import truth_challenge
from eval.compare import matches
from eval.run_eval import CHALLENGE_PATH, _expected_values, load_cases

# The SQL a careful analyst would write, by case id. Table names are the ones ingestion gives
# the sample files (`salary_register_2025_register` is the Register sheet of the workbook).
HAND_WRITTEN_SQL = {
    "ch-01": """
        SELECT e.department, SUM(r.gross) AS total_gross
        FROM salary_register_2025_register r
        JOIN employees e ON r.emp_code = e.emp_id
        JOIN performance_reviews p ON p.employee_id = e.emp_id
        WHERE p.review_cycle = 'H2 2025' AND p.rating >= 4
        GROUP BY e.department
    """,
    "ch-02": """
        SELECT e.department,
               100.0 * SUM(r.gross) / (SELECT SUM(gross) FROM salary_register_2025_register) AS pct_of_gross
        FROM salary_register_2025_register r
        JOIN employees e ON r.emp_code = e.emp_id
        GROUP BY e.department
    """,
    "ch-03": """
        SELECT 100.0 * (SELECT SUM(amount) FROM salary_register_2025_bonuses) / SUM(gross) AS bonus_pct_of_gross
        FROM salary_register_2025_register
    """,
    "ch-04": """
        SELECT exit_reason, COUNT(*) AS people
        FROM employees
        WHERE exit_date >= DATE '2025-01-01' AND exit_date <= DATE '2025-12-31'
        GROUP BY exit_reason
        ORDER BY people DESC
        LIMIT 5
    """,
    "ch-05": """
        SELECT median(gross) AS median_gross
        FROM salary_register_2025_register
        WHERE pay_month >= DATE '2025-10-01' AND pay_month <= DATE '2025-12-31'
    """,
    "ch-06": """
        WITH monthly AS (
            SELECT pay_month, SUM(net) AS monthly_net
            FROM salary_register_2025_register
            GROUP BY pay_month
        ), changes AS (
            SELECT pay_month, monthly_net - LAG(monthly_net) OVER (ORDER BY pay_month) AS change_in_net
            FROM monthly
        )
        SELECT pay_month, change_in_net FROM changes WHERE change_in_net IS NOT NULL ORDER BY pay_month
    """,
    "ch-07": """
        SELECT 100.0 * SUM(CASE WHEN exit_date < date_of_joining + INTERVAL 1 YEAR THEN 1 ELSE 0 END)
               / COUNT(*) AS pct_left_within_12_months
        FROM employees
        WHERE date_of_joining >= DATE '2024-01-01' AND date_of_joining <= DATE '2024-12-31'
    """,
    "ch-08": """
        SELECT location,
               SUM(CASE WHEN ctc > 1500000 THEN 1 ELSE 0 END) AS above_15_lakh,
               SUM(CASE WHEN ctc <= 1500000 THEN 1 ELSE 0 END) AS at_or_below_15_lakh
        FROM employees
        WHERE exit_date IS NULL
        GROUP BY location
    """,
    "ch-09": """
        SELECT DISTINCT department
        FROM employees
        WHERE department NOT IN (
            SELECT department FROM employees
            WHERE exit_date >= DATE '2025-01-01' AND exit_date <= DATE '2025-06-30'
        )
    """,
    "ch-10": """
        WITH ranked AS (
            SELECT department, name, ctc,
                   ROW_NUMBER() OVER (PARTITION BY department ORDER BY ctc DESC) AS rank_in_department
            FROM employees
            WHERE exit_date IS NULL
        )
        SELECT department, name, ctc FROM ranked WHERE rank_in_department = 1 ORDER BY department
    """,
    "ch-11": """
        SELECT SUM(days_absent) AS days_absent
        FROM attendance_all
        WHERE source_file = 'attendance_q2.csv'
    """,
    "ch-12": """
        SELECT category, date_trunc('month', order_date) AS order_month, AVG(revenue) AS average_order_value
        FROM sales
        WHERE order_date >= DATE '2025-01-01' AND order_date <= DATE '2025-12-31'
        GROUP BY category, order_month
        ORDER BY category, order_month
    """,
    "ch-13": """
        SELECT COUNT(*) AS repeat_customers FROM (
            SELECT customer FROM sales
            WHERE order_date >= DATE '2025-12-01' AND order_date <= DATE '2025-12-31'
            GROUP BY customer HAVING COUNT(*) > 1
        )
    """,
    "ch-14": """
        SELECT department, COUNT(*) AS active_employees
        FROM employees
        WHERE exit_date IS NULL
        GROUP BY department
    """,
}


def scripted_model(sql: str) -> FakeLLM:
    """A model that only ever returns this SQL, and narrates without claiming anything.

    Several of each: a fan-out caveat or a grounding retry asks again, and a fake that runs dry
    would fail the test for a reason that has nothing to do with the question being graded."""
    generation = json.dumps({"status": "ok", "interpretation": "Hand-written SQL for a challenge question.",
                             "plan": ["Run the query"], "assumptions": [], "sql": " ".join(sql.split()),
                             "clarify_question": "", "clarify_options": [], "missing": "", "metrics_used": []})
    narration = json.dumps({"text": "The table shows the result.", "reading": "Runs the hand-written query.",
                            "followups": []})
    return FakeLLM({"sql": [generation] * 3, "narrate": [narration] * 3})


@pytest.fixture(scope="module")
def session():
    """One real session over the real sample files: ingestion runs once for all sixteen."""
    if not any(settings.demo_data_dir.glob("*.csv")):
        pytest.skip("the sample data is not generated yet")
    from app.sessions import SessionStore

    was_crosschecking = settings.crosscheck
    object.__setattr__(settings, "crosscheck", False)  # a second model would need a second script
    store = SessionStore()
    session = store.create()
    session.load_sample()
    yield session
    object.__setattr__(settings, "crosscheck", was_crosschecking)


@pytest.fixture(scope="module")
def challenge():
    cases = load_cases(CHALLENGE_PATH, truth_challenge)
    return {case.id: (case, expected) for case, expected in
            zip(cases, _expected_values(cases, truth_challenge).values())}


def ask(session, question: str, sql: str):
    from app.query.pipeline import answer_question, clear_answer_cache

    clear_answer_cache()  # the pipeline caches by question; each case must really run
    session.history.clear()
    session.answer_cache.clear()
    return answer_question(session, AskRequest(question=question), scripted_model(sql), lambda event: None)


@pytest.mark.parametrize("case_id", sorted(HAND_WRITTEN_SQL))
def test_the_question_the_truth_and_the_comparer_agree(session, challenge, case_id):
    case, expected = challenge[case_id]
    answer = ask(session, case.question, HAND_WRITTEN_SQL[case_id])
    assert answer.kind == "answer", f"{case_id}: {answer.text}"
    assert answer.table is not None
    assert matches(expected, answer.table, ordered=case.ordered), (
        f"{case_id} ({case.question})\nexpected {expected}\ngot {answer.table.rows[:6]}")


def test_every_answerable_challenge_question_is_proved_this_way(challenge):
    """If a question is added to the set without SQL to prove it, this is where it shows up."""
    answerable = {id for id, (case, _) in challenge.items() if case.kind != "refusal"}
    assert answerable == set(HAND_WRITTEN_SQL)


def test_the_names_in_the_highest_paid_answer_are_real_names(session, challenge):
    """ch-10 is the PII question: the analyst gets names in the table. That the model never saw
    them is the canary test's job (backend/tests/security); this only pins the half that would
    make the question pointless if it broke."""
    case, expected = challenge["ch-10"]
    answer = ask(session, case.question, HAND_WRITTEN_SQL["ch-10"])
    assert {row[1] for row in expected} <= {cell for row in answer.table.rows for cell in row}
