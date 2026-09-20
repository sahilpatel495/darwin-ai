"""The Trust Report's numbers, recomputed by hand on a case list small enough to check by eye."""

import json

from app.contracts import EvalCase, EvalReport, ModelScore

from eval.report import build_report, load_report, render_markdown, trust_points, write_report


def case(id: str, passed: bool, *, category="totals", split="dev", expected="answer", got="answer",
         confidence: str | None = "high", latency_ms=1000, repairs=0, note="") -> EvalCase:
    return EvalCase(id=id, category=category, split=split, question=f"Question {id}?",
                    expected_kind=expected, got_kind=got, passed=passed, confidence=confidence,
                    latency_ms=latency_ms, repairs=repairs, note=note)


CASES = [
    case("tot-01", True, latency_ms=1000),
    case("tot-02", True, latency_ms=2000, repairs=1),
    case("join-01", False, category="joins", confidence="medium", latency_ms=3000,
         note="The result does not match the expected value."),                       # wrong: -1
    case("join-02", False, category="joins", got="refusal", confidence=None, latency_ms=4000,
         note="The app declined to answer a question the data can answer."),          # abstained: 0
    case("una-01", True, category="unanswerable", split="holdout", expected="refusal", got="refusal",
         confidence=None, latency_ms=500),
    case("hr-09", False, category="hr_metrics", split="holdout", confidence="high", latency_ms=0,
         note="Used closing headcount instead of the average."),                      # wrong: -1
]


def report(**overrides) -> EvalReport:
    args = {"model": "openai/gpt-oss-120b", "runs": 1, "crosscheck_agreement": 0.75, "other_models": []}
    return build_report(CASES, **{**args, **overrides})


def test_headline_numbers():
    r = report()
    assert r.total == 6
    assert r.accuracy == 0.5
    assert r.accuracy_holdout == 0.5
    assert r.by_category == {"totals": 1.0, "joins": 0.0, "unanswerable": 1.0, "hr_metrics": 0.0}
    assert r.crosscheck_agreement == 0.75
    assert r.generated_at  # an ISO timestamp with a timezone
    assert [c.id for c in r.cases] == [c.id for c in CASES]


def test_trust_score_rewards_correct_forgives_abstaining_and_punishes_wrong():
    assert [trust_points(c) for c in CASES] == [1, 1, -1, 0, 1, -1]
    assert report().trust_score == round((1 + 1 - 1 + 0 + 1 - 1) / 6, 3)


def test_latency_percentiles_skip_questions_that_were_never_timed():
    r = report()  # timed: 500, 1000, 2000, 3000, 4000; hr-09 has 0 = served from cache
    assert (r.p50_ms, r.p95_ms) == (2000, 4000)


def test_repair_rate_is_the_share_of_questions_that_needed_a_repair():
    assert report().repair_rate == round(1 / 6, 3)


def test_calibration_says_how_often_each_badge_was_right():
    calibration = report().calibration
    assert (calibration["high"].n, calibration["high"].accuracy) == (3, round(2 / 3, 3))
    assert (calibration["medium"].n, calibration["medium"].accuracy) == (1, 0.0)
    assert "low" not in calibration  # no question got a Low badge, so there is nothing to claim


def test_model_comparison_keeps_other_models_and_replaces_this_one():
    others = [ModelScore(model="qwen/qwen3.8-27b", accuracy=0.8, p50_ms=4100),
              ModelScore(model="openai/gpt-oss-120b", accuracy=0.1, p50_ms=1)]
    models = report(other_models=others).models
    assert [(m.model, m.accuracy, m.p50_ms) for m in models] == [
        ("openai/gpt-oss-120b", 0.5, 2000), ("qwen/qwen3.8-27b", 0.8, 4100)]


def test_an_empty_run_is_all_zeros_not_a_crash():
    r = build_report([], model="m", runs=1, crosscheck_agreement=None, other_models=[])
    assert (r.total, r.accuracy, r.accuracy_holdout, r.trust_score, r.p50_ms, r.p95_ms) == (0, 0.0, 0.0, 0.0, 0, 0)


def test_markdown_lists_every_failure_with_its_reason():
    text = render_markdown(report())
    assert "50.0%" in text and "openai/gpt-oss-120b" in text
    for failed in (c for c in CASES if not c.passed):
        assert failed.id in text and failed.note in text
    assert "tot-01" not in text  # passes are counted, not listed


def test_markdown_can_hide_holdout_failures_from_the_tuning_loop():
    text = render_markdown(report(), hide_holdout_failures=True)
    assert "join-01" in text
    assert "hr-09" not in text and "closing headcount" not in text
    assert "1 holdout question failed" in text


def test_markdown_says_so_when_the_holdout_has_not_been_run():
    dev_only = build_report(CASES[:4], model="m", runs=1, crosscheck_agreement=None, other_models=[])
    text = render_markdown(dev_only)
    assert "holdout questions have not been run" in text.lower()
    assert "Cross-check was off" in text


def test_report_files_round_trip(tmp_path):
    write_report(report(), tmp_path)
    assert load_report(tmp_path / "report.json") == report(generated_at=load_report(tmp_path / "report.json").generated_at)
    assert json.loads((tmp_path / "report.json").read_text())["total"] == 6
    assert (tmp_path / "REPORT.md").read_text().startswith("# Verity evaluation report")


def test_a_missing_or_unreadable_report_is_simply_no_report(tmp_path):
    assert load_report(tmp_path / "report.json") is None
    (tmp_path / "report.json").write_text("{not json")
    assert load_report(tmp_path / "report.json") is None
