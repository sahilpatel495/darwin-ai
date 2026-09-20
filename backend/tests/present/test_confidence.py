"""The confidence badge: fixed arithmetic, and every point gained or lost has a sentence."""

import pytest
from app.query.confidence import Signals, score


def test_a_clean_run_is_high_and_says_why():
    confidence = score(Signals())
    assert (confidence.level, confidence.score) == ("high", 0.8)
    assert any("No repairs were needed" in reason for reason in confidence.reasons)


def test_a_disagreeing_second_model_leads_the_reasons_and_lowers_the_level():
    confidence = score(Signals(cross_check="disagreed"))
    assert confidence.level in ("medium", "low") and confidence.score == 0.45
    assert "second model" in confidence.reasons[0]


@pytest.mark.parametrize(
    ("signals", "expected_score", "expected_level", "reason_contains"),
    [
        (Signals(cross_check="agreed"), 0.95, "high", "same result"),
        (Signals(cross_check="agreed", vetted_metric=True), 1.0, "high", "vetted definition"),
        (Signals(vetted_metric=True), 0.85, "high", "vetted definition"),
        (Signals(repairs=1), 0.65, "medium", "1 repair "),
        (Signals(repairs=2), 0.5, "low", "2 repairs"),
        (Signals(fan_out=True), 0.55, "medium", "more than once"),
        (Signals(period_unfiltered=True), 0.6, "medium", "names a period"),
        (Signals(max_null_fraction=0.34), 0.7, "medium", "34%"),
        (Signals(max_null_fraction=0.19), 0.8, "high", "No repairs"),
        (Signals(min_join_match=0.62), 0.65, "medium", "62%"),
        (Signals(used_unconfirmed_link=True), 0.7, "medium", "not confirmed"),
        (Signals(narration_fallback=True), 0.75, "medium", "template"),
        (Signals(truncated=True), 0.75, "medium", "row limit"),
        (Signals(assumptions=2), 0.75, "medium", "2 assumptions"),
        (Signals(assumptions=1), 0.8, "high", "No repairs"),
        (Signals(repairs=1, max_null_fraction=0.2), 0.55, "medium", "20%"),  # 0.8-0.15-0.1 in floats is 0.5499...
    ],
)
def test_each_signal_moves_the_score_as_documented(signals, expected_score, expected_level, reason_contains):
    confidence = score(signals)
    assert (confidence.score, confidence.level) == (expected_score, expected_level)
    assert any(reason_contains in reason for reason in confidence.reasons)


def test_an_unavailable_cross_check_is_mentioned_but_costs_nothing():
    confidence = score(Signals(cross_check="unavailable"))
    assert confidence.score == 0.8 and any("could not run" in reason for reason in confidence.reasons)
    assert not any("second model" in reason for reason in score(Signals(cross_check="skipped")).reasons)


def test_the_score_is_clamped_and_every_problem_is_listed_in_plain_sentences():
    confidence = score(Signals(repairs=2, cross_check="disagreed", fan_out=True, max_null_fraction=0.5,
                               min_join_match=0.4, used_unconfirmed_link=True, narration_fallback=True,
                               truncated=True, assumptions=3, period_unfiltered=True))
    assert (confidence.score, confidence.level) == (0.0, "low")
    assert len(confidence.reasons) == 10
    for reason in confidence.reasons:
        assert reason.endswith(".") and "_" not in reason and reason[0].isupper()
