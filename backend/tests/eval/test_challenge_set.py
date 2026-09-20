"""The challenge set as a file: it loads, it is what it claims to be, and it can be graded.

The end-to-end proof that each question is answerable lives in test_challenge_sql.py. This is
the cheap half: shape, independence from the app, and a comparer that is not so forgiving that
a 1% error would pass.
"""

import re
from datetime import date, datetime
from pathlib import Path

import pytest
from app.contracts import ResultTable

from eval import run_eval
from eval.compare import _as_rows, matches

pytestmark = pytest.mark.skipif(not run_eval.CHALLENGE_PATH.exists(), reason="eval/challenge.yaml is not written yet")

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def challenge():
    truth = run_eval._load_truth("eval.truth_challenge")
    cases = run_eval.load_cases(run_eval.CHALLENGE_PATH, truth)
    return cases, run_eval._expected_values(cases, truth)


def json_safe(value):
    """What the app's result table would hold for this value: dates travel as ISO text."""
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def table_of(rows) -> ResultTable:
    plain = [[json_safe(v) for v in row] for row in rows]
    return ResultTable(columns=[f"c{i}" for i in range(len(rows[0]))], rows=plain,
                       display=[[str(v) for v in row] for row in plain], row_count=len(plain))


def test_the_challenge_set_is_16_questions_none_of_them_tuned_on(challenge):
    cases, _ = challenge
    assert len(cases) == 16
    assert {c.split for c in cases} == {"holdout"}, "a challenge question must never sit in a tuned split"
    assert len({c.id for c in cases}) == 16


def test_it_covers_the_shapes_it_was_written_for(challenge):
    """One question per boundary. If a category disappears, the set has drifted back towards
    the golden questions, which is the one thing it must not do."""
    cases, _ = challenge
    assert {c.category for c in cases} >= {
        "chain", "percent_of_total", "ties", "median", "change_over_time", "cohort",
        "conditional_aggregation", "negation", "per_group_row", "unions", "non_hr",
        "near_column", "unanswerable",
    }
    assert sum(c.kind == "refusal" for c in cases) == 2  # a forecast and a significance test
    assert sum(c.kind == "assume_or_refuse" for c in cases) == 1


def test_no_challenge_id_collides_with_a_golden_id(challenge):
    """The two sets share one REPORT.md. Colliding ids would make a failure unreadable."""
    cases, _ = challenge
    golden = run_eval.load_cases(run_eval.GOLDEN_PATH, run_eval._load_truth())
    assert not {c.id for c in cases} & {g.id for g in golden}


def test_every_expected_value_is_gradable_and_matches_itself(challenge):
    cases, expected = challenge
    for case in cases:
        value = expected[case.id]
        if value is None:
            assert case.kind == "refusal", f"{case.id} expects a result but its truth is None"
            continue
        rows = _as_rows(value) or [(value,)]
        assert rows, f"{case.id}: an empty expected result would pass on any empty table"
        assert matches(value, table_of(rows), ordered=case.ordered), case.id


def test_a_wrong_number_fails_every_numeric_case(challenge):
    cases, expected = challenge
    for case in cases:
        value = expected[case.id]
        rows = (_as_rows(value) or [(value,)]) if value is not None else []
        numeric = [i for i, cell in enumerate(rows[0] if rows else [])
                   if isinstance(cell, (int, float)) and not isinstance(cell, bool) and cell]
        if not numeric:
            continue
        off = [[v * 1.01 if i in numeric else v for i, v in enumerate(row)] for row in rows]
        assert not matches(value, table_of(off), ordered=case.ordered), case.id


def test_the_challenge_truth_never_imports_the_app():
    """Same rule as eval/truth.py: an expected answer computed with the app's own code would
    agree with the app's own bugs."""
    source = (ROOT / "eval" / "truth_challenge.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+(app|backend)\b", source, flags=re.MULTILINE)


def test_the_truth_returns_plain_python_so_the_report_can_be_written_as_json(challenge):
    _, expected = challenge
    for case_id, value in expected.items():
        cells = [cell for row in value for cell in row] if isinstance(value, list) else [value]
        assert all(cell is None or type(cell) in (int, float, str) for cell in cells), f"{case_id}: numpy leaked"


def test_the_ties_question_really_has_a_tie_inside_the_five(challenge):
    """If the generator ever changes and the tie goes away, ch-04 stops testing what it is for."""
    _, expected = challenge
    counts = [value for _, value in expected["ch-04"]]
    assert len(set(counts)) < len(counts)


def test_the_negation_question_has_a_row_to_return(challenge):
    """An empty expected result would pass on any query that happened to return nothing."""
    _, expected = challenge
    assert expected["ch-09"] == [("Finance",)]


def test_the_highest_paid_person_per_department_is_a_single_person(challenge):
    """ch-10 asks who earns most in each department. Two people tied at the top would give the
    question two honest answers, and the truth would silently return one of them."""
    _, expected = challenge
    departments = [department for department, _name, _ctc in expected["ch-10"]]
    assert len(departments) == len(set(departments))


def test_every_challenge_question_names_its_period_in_months_or_not_at_all(challenge):
    """"The first half of 2025" reads as April to September to anyone who has seen this company's
    H1/H2 review cycles, and as January to June to everyone else, which are different answers.
    A period in this set is named in months, in quarters of the calendar, or described from the
    data itself ("the last quarter of the data")."""
    cases, _ = challenge
    for case in cases:
        assert "half of" not in case.question.casefold(), case.id
