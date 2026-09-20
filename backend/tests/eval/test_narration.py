"""Grading the sentence, not only the table.

The golden set scored 40 of 40 while one answer read "Engineering has the highest average salary
at ₹13.34 L" and the top row of its own table was Support at ₹15.53 L. The eval graded the
table, so it never saw it. These tests pin the check that would have.

Everything here is decided from the expected answer in eval/truth.py, never from the table the
app returned: a sentence that agrees with a wrong table is still wrong.
"""

import pytest

from eval.report import NARRATION_FAILURE, failure_kind
from eval.run_eval import _narration_problem, _ranked_labels, run_case

from .test_run_eval import answered, golden, no_sleep

# The real numbers behind the failure, from eval/truth.py:avg_ctc_by_department().
BY_DEPARTMENT = [("Engineering", 1334250.0), ("Finance", 1298250.0), ("HR", 1307368.42),
                 ("Operations", 1038685.71), ("Sales", 1152300.0), ("Support", 1552875.0)]
THE_WRONG_SENTENCE = "Engineering has the highest average salary at ₹13.34 L."
THE_RIGHT_SENTENCE = "Support has the highest average salary at ₹15.53 L."

TOP = {"narration": True}  # read by `case()` below


def case(**flags):
    return golden(id="amb-01", category="ambiguous", truth="avg_ctc_by_department", **flags)


def problem(text: str, expected=BY_DEPARTMENT, **flags) -> str:
    return _narration_problem(case(**flags), text, expected)


# ---------------------------------------------------------------- the failure that got through


def test_the_sentence_that_got_through_the_golden_set_is_now_caught():
    note = problem(THE_WRONG_SENTENCE, names_top=True)
    assert NARRATION_FAILURE in note.casefold()
    assert "Engineering" in note and "Support" in note


def test_the_right_sentence_passes():
    assert problem(THE_RIGHT_SENTENCE, names_top=True) == ""


def test_the_whole_case_fails_so_the_question_is_counted_wrong():
    """The table matches exactly; only the sentence is wrong. The question must still fail."""
    rows = [[label, value] for label, value in BY_DEPARTMENT]
    right = run_case(case(names_top=True), lambda req: answered(rows, text=THE_RIGHT_SENTENCE), BY_DEPARTMENT, no_sleep)
    wrong = run_case(case(names_top=True), lambda req: answered(rows, text=THE_WRONG_SENTENCE), BY_DEPARTMENT, no_sleep)
    assert right.passed and not wrong.passed
    assert wrong.got_kind == "answer"  # it answered; it answered wrongly in words
    assert NARRATION_FAILURE in wrong.note.casefold()


def test_the_failure_is_reported_as_its_own_kind():
    from app.contracts import EvalCase

    narration = EvalCase(id="amb-01", category="ambiguous", split="dev", question="q", expected_kind="answer",
                         got_kind="answer", passed=False, note=problem(THE_WRONG_SENTENCE, names_top=True))
    wrong_number = narration.model_copy(update={"note": "The result does not match the expected value."})
    assert failure_kind(narration) == NARRATION_FAILURE
    assert failure_kind(wrong_number) == "wrong result"


# ---------------------------------------------------------------- naming the row at all


def test_a_sentence_that_never_names_the_top_row_fails():
    note = problem("Average salary varies a lot across the six departments.", names_top=True)
    assert NARRATION_FAILURE in note.casefold() and "Support" in note


def test_naming_the_top_row_without_a_ranking_word_is_enough():
    assert problem("Support pays ₹15.53 L on average, ahead of Engineering at ₹13.34 L.", names_top=True) == ""


def test_the_lowest_row_is_graded_only_when_the_case_asks_for_it():
    silent = "Support has the highest average salary at ₹15.53 L."
    assert problem(silent, names_top=True) == ""
    assert NARRATION_FAILURE in problem(silent, names_bottom=True).casefold()
    assert problem("Support is highest at ₹15.53 L and Operations lowest at ₹10.39 L.",
                   names_top=True, names_bottom=True) == ""


def test_a_wrong_lowest_claim_is_caught_when_the_case_asks_for_the_lowest():
    note = problem("Support is highest and Finance is the lowest.", names_top=True, names_bottom=True)
    assert "Finance" in note and "Operations" in note


# ---------------------------------------------------------------- what must not be graded


def test_a_case_without_the_narration_flag_is_not_graded_on_its_sentence():
    """Opt-in: a question whose truth has no single top row must not start failing on wording."""
    assert problem(THE_WRONG_SENTENCE) == ""


@pytest.mark.parametrize("expected", [
    1_200_000,                                   # one number: no rows, no ranking
    [(1.0,), (2.0,)],                            # a time series: the truth keeps no labels
    [("HR", 5), ("Sales", 5)],                   # flat: nothing is highest
    [("HR", "a"), ("Sales", "b")],               # nothing numeric to rank
    [("HR", 1, 2), ("Sales", 3, 4)],             # two measures: "the highest" would be a guess
], ids=["scalar", "time series", "flat", "not numeric", "two measures"])
def test_a_truth_that_is_not_a_ranked_breakdown_says_nothing_about_a_highest_row(expected):
    assert _ranked_labels(expected) is None
    assert _narration_problem(case(names_top=True), THE_WRONG_SENTENCE, expected) == ""


def test_a_ranking_word_about_something_that_is_not_a_row_label_is_left_alone():
    """"the most recent cycle" ranks a thing the result does not group by. The narrator's own
    grounding check owns that sentence; this check only ever judges labels it can see."""
    assert problem("Support has the highest average salary at ₹15.53 L in the most recent cycle.",
                   names_top=True) == ""


def test_a_tie_at_the_top_may_be_reported_as_either_row():
    tied = [("HR", 9.0), ("Sales", 9.0), ("Ops", 1.0)]
    assert _ranked_labels(tied)[1] == ["HR", "Sales"]
    for winner in ("HR", "Sales"):
        assert _narration_problem(case(names_top=True), f"{winner} is the highest at 9.", tied) == ""
    assert _narration_problem(case(names_top=True), "Ops is the highest at 1.", tied) != ""


def test_labels_are_matched_as_whole_words_and_case_does_not_matter():
    assert problem("SUPPORT has the highest average salary.", names_top=True) == ""
    # "Support" inside a longer word is not the label; the sentence then names nobody.
    assert NARRATION_FAILURE in problem("Supportability is highest.", names_top=True).casefold()


def test_a_claim_is_judged_clause_by_clause():
    """"Support is highest, Operations lowest" is two claims; only one of them may be wrong."""
    assert problem("Support leads at ₹15.53 L, while Operations trails at ₹10.39 L.",
                   names_top=True, names_bottom=True) == ""
    assert problem("Engineering leads at ₹13.34 L, while Support trails.", names_top=True) != ""


def test_a_number_written_with_indian_grouping_does_not_split_a_clause():
    """₹15,52,875 has commas in it; they must not end the clause and hide the claim."""
    assert problem("Engineering has the highest average salary at ₹13,34,250.", names_top=True) != ""


def test_a_ranking_claim_is_about_the_side_before_than():
    """"Engineering pays the most of any department other than Support" names both rows and has
    no comma to end the claim. Read whole, the clause contains Support and the wrong sentence
    goes through; the right row is the one the ranking word is attached to."""
    assert problem("Engineering pays the most of any department other than Support.", names_top=True) != ""
    assert problem("Support pays the most of any department other than Engineering.", names_top=True) == ""
    assert problem("Operations is the lowest, below every department other than Support.",
                   names_bottom=True) == ""


def test_a_superlative_about_nobody_in_particular_is_still_allowed():
    """"No department pays more than Support" claims a rank for nobody the result names, so the
    only thing left to check is that the winner was named at all, and it was."""
    assert problem("No department pays more than Support.", names_top=True) == ""
    assert problem("Support is highest, higher than any other department.", names_top=True) == ""
