"""The real golden set and truth module, checked together without asking the app anything.

Two agents wrote the two halves (questions and truth in Task 8, grading in Task 9). This is
the seam test: every case loads, and every expected value is in a shape the comparer can grade.
"""

from datetime import date, datetime

import pytest
from app.contracts import ResultTable

from eval import run_eval
from eval.compare import _as_rows, matches

pytestmark = pytest.mark.skipif(not run_eval.GOLDEN_PATH.exists(), reason="eval/golden.yaml is not written yet")


@pytest.fixture(scope="module")
def golden():
    truth = run_eval._load_truth()
    cases = run_eval.load_cases(run_eval.GOLDEN_PATH, truth)
    return cases, run_eval._expected_values(cases, truth)


def json_safe(value):
    """What the app's result table would hold for this value: dates travel as ISO text."""
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def test_the_golden_set_is_40_questions_split_30_dev_10_holdout(golden):
    cases, _ = golden
    splits = [c.split for c in cases]
    assert (len(cases), splits.count("dev"), splits.count("holdout")) == (40, 30, 10)
    assert {c.kind for c in cases} == {"answer", "clarify", "refusal"}


def test_every_expected_value_is_gradable_and_matches_itself(golden):
    cases, expected = golden
    for case in cases:
        value = expected[case.id]
        if value is None:
            assert case.kind != "answer", f"{case.id} expects an answer but its truth is None"
            continue
        rows = _as_rows(value) or [(value,)]
        assert rows, f"{case.id}: an empty expected result would pass on any empty table"
        table = ResultTable(columns=[f"c{i}" for i in range(len(rows[0]))],
                            rows=[[json_safe(v) for v in row] for row in rows],
                            display=[[str(v) for v in row] for row in rows], row_count=len(rows))
        assert matches(value, table, ordered=case.ordered), case.id


def test_every_dev_case_with_a_ranked_breakdown_grades_its_sentence(golden):
    """The header of golden.yaml promises it, and a case added later without `narration` would
    be graded on its table alone: exactly the hole that let "Engineering has the highest average
    salary" through while the top row was Support. `joi-02` is the one stated exception, and the
    reason is in the file: its top two departments both round to 3.45."""
    cases, expected = golden
    rankable = {c.id for c in cases
                if c.split == "dev" and run_eval._ranked_labels(expected[c.id]) is not None}
    graded = {c.id for c in cases if c.names_top or c.names_bottom}
    assert rankable - graded == {"joi-02"}
    assert graded <= rankable, "a case cannot name a top row its expected answer does not have"


def test_a_wrong_number_fails_every_numeric_case(golden):
    """The comparer must not be so forgiving that a 1% error passes anywhere in the real set."""
    cases, expected = golden
    for case in cases:
        value = expected[case.id]
        rows = _as_rows(value) or [(value,)] if value is not None else []
        if not rows or not any(isinstance(v, (int, float)) and not isinstance(v, bool) and v for v in rows[0]):
            continue
        off = [[v * 1.01 if isinstance(v, (int, float)) and not isinstance(v, bool) else json_safe(v) for v in row] for row in rows]
        table = ResultTable(columns=[f"c{i}" for i in range(len(rows[0]))], rows=off,
                            display=[[str(v) for v in row] for row in off], row_count=len(off))
        assert not matches(value, table, ordered=case.ordered), case.id
