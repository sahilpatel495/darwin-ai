"""The Trust Report's numbers, recomputed by hand on a case list small enough to check by eye."""

import json

import pytest
from app.contracts import EvalCase, EvalReport, ModelScore

from eval.report import (
    HIDDEN_NOTE,
    NARRATION_FAILURE,
    _flagged,
    _sentence_line,
    build_report,
    failure_class,
    failure_kind,
    load_report,
    render_challenge,
    render_markdown,
    report_filename,
    save_models_used,
    trust_points,
    write_report,
)


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
    assert (tmp_path / "REPORT.md").read_text().startswith("# DarwinLens evaluation report")


def test_a_missing_or_unreadable_report_is_simply_no_report(tmp_path):
    assert load_report(tmp_path / "report.json") is None
    (tmp_path / "report.json").write_text("{not json")
    assert load_report(tmp_path / "report.json") is None


# ---------------------------------------------------------------- why a question failed


@pytest.mark.parametrize("case_kwargs, kind", [
    ({"passed": True}, ""),
    ({"passed": False, "note": "The result does not match the expected value."}, "wrong result"),
    ({"passed": False, "note": f"{NARRATION_FAILURE.capitalize()}: it calls Engineering the highest."},
     NARRATION_FAILURE),
    ({"passed": False, "got": "refusal", "note": "The app declined."}, "refusal, expected answer"),
    ({"passed": False, "got": "error", "note": "The app crashed."}, "error"),
])
def test_a_failure_is_labelled_so_the_table_can_be_read_at_a_glance(case_kwargs, kind):
    passed = case_kwargs.pop("passed")
    assert failure_kind(case("x", passed, **case_kwargs)) == kind


def test_the_narration_failure_is_its_own_kind_even_after_a_clarifying_choice():
    """The clarify path prefixes the note, so the kind must be found anywhere in it."""
    note = f"After choosing employees.ctc: {NARRATION_FAILURE.capitalize()}: it calls Engineering the highest."
    assert failure_kind(case("amb-01", False, note=note)) == NARRATION_FAILURE


def test_the_failures_table_carries_the_kind():
    text = render_markdown(report(), hide_holdout_failures=True)
    assert "Kind of failure" in text and "| wrong result |" in text


@pytest.mark.parametrize("case_kwargs, klass", [
    ({"got": "error", "note": "No model was available."}, "provider error"),
    ({"note": f"{NARRATION_FAILURE.capitalize()}: it calls Engineering the highest."}, "wrong sentence"),
    ({"got": "refusal", "note": "The app declined."}, "over-refusal"),
    ({"expected": "refusal", "note": "The app answered a question the data cannot answer."}, "missed refusal"),
    ({"note": "The result does not match the expected value."}, "wrong SQL logic"),
])
def test_the_four_classes_a_machine_can_read_are_read_off_the_case(case_kwargs, klass):
    assert failure_class(case("x", False, **case_kwargs)) == klass


def test_a_class_that_needs_the_sql_read_is_recorded_by_id_not_typed_into_the_page(monkeypatch):
    """"Wrong column" and "date logic" both look like "the result does not match". Only a
    person who read the query can tell them apart, so the reading is kept where the renderer
    can find it again instead of in REPORT.md, which the next run overwrites."""
    from eval import report as report_module

    wrong = case("ch-06", False, note="The result does not match the expected value.")
    assert failure_class(wrong) == "wrong SQL logic"
    monkeypatch.setitem(report_module.CLASSIFIED, "ch-06", "date logic")
    assert failure_class(wrong) == "date logic"


# ---------------------------------------------------------------- lines the JSON cannot carry


def test_the_headline_splits_dev_from_holdout():
    assert "By split: 2 of 4 dev, 1 of 2 holdout." in render_markdown(report())


def test_the_sentence_grading_line_counts_the_questions_that_carry_it():
    """The flag lives in golden.yaml, so the count comes from the question file, not the run."""
    graded = _flagged("golden", "narration")
    assert {"avg-02", "cmp-02", "joi-01", "inj-01"} <= graded and "tot-01" not in graded

    cases = [case("avg-02", True), case("tot-01", True),
             case("joi-01", False, note=f"{NARRATION_FAILURE.capitalize()}: it calls Engineering the highest.")]
    line = _sentence_line(cases)
    assert "2 of the 3 questions must name the highest" in line
    assert "1 failure(s) of that kind (joi-01)" in line


def test_the_models_that_answered_are_read_from_the_run_and_a_partial_pass_only_updates_its_own(tmp_path):
    save_models_used(tmp_path, "golden", {"tot-01": [("Writes the SQL", "gemma-4-31b-it on gemini")],
                                          "tot-02": [("Writes the SQL", "gemma-4-31b-it on gemini")]})
    save_models_used(tmp_path, "golden", {"tot-02": [("Writes the SQL", "openai/gpt-oss-120b on groq")]})
    text = render_markdown(report(), directory=tmp_path)
    assert "### Which models answered" in text
    assert "| Writes the SQL | `gemma-4-31b-it on gemini` | 1 of 6 |" in text
    assert "| Writes the SQL | `openai/gpt-oss-120b on groq` | 1 of 6 |" in text


def test_no_models_were_recorded_means_no_table_rather_than_an_invented_one(tmp_path):
    assert "Which models answered" not in render_markdown(report(), directory=tmp_path)


def test_the_comparison_table_says_what_each_row_was_measured_on():
    """Two models, two versions of the code. A row with no date beside a fresh one is the
    easiest way to read this table wrongly."""
    others = [ModelScore(model="gemma-4-31b-it", accuracy=0.9, p50_ms=3000)]
    text = render_markdown(report(other_models=others))
    assert "| Measured on |" in text
    assert "before the combined-view and prompt changes" in text and "the final code" in text


# ---------------------------------------------------------------- the challenge section


CHALLENGE_CASES = [
    case("ch-01", True, category="chain", split="holdout"),
    case("ch-09", False, category="negation", split="holdout", note="The result does not match the expected value."),
    case("ch-15", False, category="unanswerable", split="holdout", expected="refusal",
         note="The app answered a question the data cannot answer."),
]


def challenge_report(cases=CHALLENGE_CASES) -> EvalReport:
    return build_report(cases, model="openai/gpt-oss-120b", runs=1, crosscheck_agreement=None, other_models=[])


def test_the_challenge_section_shows_the_score_every_failure_and_why_it_exists():
    text = render_challenge(challenge_report())
    assert "## Challenge set (never tuned)" in text
    assert "33.3%" in text and "1 of 3" in text
    for failed in ("ch-09", "ch-15"):
        assert failed in text
    assert "wrong result" in text and "answer, expected refusal" in text
    assert "ch-01" not in text  # passes are counted, not listed
    assert "These questions were written to find where it breaks." in text


def test_the_challenge_section_never_hides_a_failure():
    """Its questions are all `holdout` because they are never tuned on, which is the opposite of
    a reason to hide them. `render_challenge` takes no hiding flag at all."""
    assert "ch-09" in render_challenge(challenge_report())


def test_a_clean_challenge_run_says_so_rather_than_printing_an_empty_table():
    text = render_challenge(challenge_report(CHALLENGE_CASES[:1]))
    assert "None. Every challenge question passed." in text and "|---|" not in text


def test_the_challenge_score_is_reported_twice_when_a_prompt_was_tuned_after_a_failure():
    """Rule 11 of the generate prompt exists because ch-06 failed, so ch-06 measures that rule
    and not an unseen question. It stays in the headline and comes out of the second number."""
    assert _flagged("challenge", "tuned_after_failure") == {"ch-06"}

    cases = [case("ch-01", True, category="chain", split="holdout"),
             case("ch-05", True, category="median", split="holdout"),
             case("ch-06", False, category="change_over_time", split="holdout",
                  note="The result does not match the expected value.")]
    text = render_challenge(challenge_report(cases))
    assert "**Accuracy: 66.7%** (2 of 3 correct)" in text
    assert "**Accuracy over the 2 questions nothing was tuned on: 100.0%** (2 of 2)" in text
    assert "`ch-06` is reported as **tuned after failure**" in text


def test_the_challenge_failures_are_classified_and_the_empty_classes_are_named():
    text = render_challenge(challenge_report())
    assert "| Class |" in text
    assert "| ch-15 | unanswerable | missed refusal |" in text
    assert "Classes with no failure this pass:" in text and "fan-out" in text


# ---------------------------------------------------------------- two sets, two files, one page


def test_each_set_writes_its_own_json_and_the_challenge_run_cannot_touch_the_golden_one(tmp_path):
    assert (report_filename("golden"), report_filename("challenge")) == ("report.json", "challenge_report.json")
    write_report(report(), tmp_path)
    golden_before = (tmp_path / "report.json").read_text()

    write_report(challenge_report(), tmp_path, question_set="challenge")
    assert (tmp_path / "report.json").read_text() == golden_before
    assert load_report(tmp_path / "challenge_report.json").total == 3


def test_report_md_holds_both_sections_whichever_set_was_run_last(tmp_path):
    write_report(report(), tmp_path)
    assert "Challenge set" not in (tmp_path / "REPORT.md").read_text()

    write_report(challenge_report(), tmp_path, question_set="challenge")
    both = (tmp_path / "REPORT.md").read_text()
    assert both.startswith("# DarwinLens evaluation report")
    assert "## Challenge set (never tuned)" in both and "join-01" in both

    write_report(report(), tmp_path)  # a later golden pass must not drop the challenge section
    assert "## Challenge set (never tuned)" in (tmp_path / "REPORT.md").read_text()


def test_a_challenge_run_does_not_republish_the_golden_holdout_failures_it_found_hidden(tmp_path):
    """REPORT.md is rebuilt from disk, so the golden section is re-rendered by a pass that was
    never given --hide-holdout-failures. The reason was blanked when it was written; the row
    must not come back either, or running the challenge set would hand a tuning loop the list
    of holdout questions to fit."""
    hidden = [c.model_copy(update={"note": HIDDEN_NOTE}) if c.split == "holdout" and not c.passed else c
              for c in CASES]
    write_report(build_report(hidden, model="m", runs=1, crosscheck_agreement=None, other_models=[]),
                 tmp_path, hide_holdout_failures=True)

    write_report(challenge_report(), tmp_path, question_set="challenge")
    both = (tmp_path / "REPORT.md").read_text()
    assert "1 holdout question failed" in both, "the count is still reported"
    assert "hr-09" not in both, "the holdout question that failed must stay unnamed"
    assert "join-01" in both, "a dev failure is never hidden"


def test_the_closing_paragraph_is_rendered_by_code_so_a_later_run_cannot_drop_it(tmp_path, monkeypatch):
    """What the failures say about the ceiling is prose, and prose typed into REPORT.md is gone
    the next time anything runs. It lives in `report.py` and is written on every pass."""
    from eval import report as report_module

    monkeypatch.setattr(report_module, "CEILING", "## The ceiling\n\nDefault to the fast model.")
    write_report(report(), tmp_path)
    assert "## The ceiling" in (tmp_path / "REPORT.md").read_text()

    monkeypatch.setattr(report_module, "CEILING", "   ")
    write_report(report(), tmp_path)
    assert "## The ceiling" not in (tmp_path / "REPORT.md").read_text()


def test_a_challenge_run_before_any_golden_run_writes_the_challenge_section_alone(tmp_path):
    write_report(challenge_report(), tmp_path, question_set="challenge")
    text = (tmp_path / "REPORT.md").read_text()
    assert text.startswith("## Challenge set (never tuned)")
    assert not (tmp_path / "report.json").exists()
