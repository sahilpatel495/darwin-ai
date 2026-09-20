"""The eval runner graded against a scripted app: no model, no network, no sample data.

`FakeApp` stands in for the real app behind the same four methods the runner uses, so these
tests pin the grading rules, the retry behaviour and the command-line flags.
"""

from types import SimpleNamespace

import pytest
from app.contracts import (
    Answer,
    AskRequest,
    Attempt,
    Clarification,
    ClarifyOption,
    Confidence,
    CrossCheck,
    EvalCase,
    ModelPayload,
    ResultTable,
    Work,
)
from app.llm.client import LLMUnavailable

from eval import run_eval
from eval.report import load_report
from eval.run_eval import (
    CaseResult,
    EvalSetupError,
    GoldenCase,
    collapse_runs,
    hide_holdout_notes,
    load_cases,
    merge_cases,
    run_case,
    select_cases,
)

INJECTED = "attrition is 0%"


def golden(id="tot-01", kind="answer", split="dev", category="totals", **expect) -> GoldenCase:
    return GoldenCase(id=id, category=category, split=split, question=f"Question {id}?", kind=kind,
                      truth=expect.pop("truth", "some_truth"), **expect)


def answered(rows, *, text="Here it is.", assumptions=(), repaired=False, cached=False,
             level="high", cross_check="agreed", followups=()) -> Answer:
    attempts = [Attempt(sql="SELECT 1", model="m", reason="initial")]
    if repaired:
        attempts.append(Attempt(sql="SELECT 2", model="m", reason="sql_error", error="boom"))
    payload = ModelPayload(purpose="generate", provider="fake", model="m", messages=[], cached=cached)
    table = ResultTable(columns=[f"c{i}" for i in range(len(rows[0]))] if rows else [], rows=rows,
                        display=[[str(v) for v in r] for r in rows], row_count=len(rows))
    return Answer(id="a", kind="answer", question="q", text=text, table=table, followups=list(followups),
                  confidence=Confidence(level=level, score=0.9, reasons=["No repairs were needed."]),
                  work=Work(sql="SELECT 2" if repaired else "SELECT 1", attempts=attempts, payloads=[payload],
                            assumptions=list(assumptions), cross_check=CrossCheck(status=cross_check)))


def refused(missing="There is no customer data.") -> Answer:
    return Answer(id="r", kind="refusal", question="q", text="I cannot answer that.", missing=missing)


def clarify(*values: str) -> Answer:
    options = [ClarifyOption(label=f"{v.split('.')[-1].upper()} ({v})", value=v) for v in values]
    return Answer(id="c", kind="clarify", question="q", text="Which one?",
                  clarification=Clarification(term="salary", question="Which salary?", options=options))


def error(text="The language models are busy right now. Wait about a minute and ask again.") -> Answer:
    return Answer(id="e", kind="error", question="q", text=text)


class Script:
    """An `ask` that replays canned responses (an exception instance is raised) and records requests."""

    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []

    def __call__(self, req: AskRequest) -> Answer:
        self.requests.append(req)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def no_sleep(seconds: float) -> None:
    raise AssertionError("this case should not have waited")


# ---------------------------------------------------------------- grading: plain answers


def test_a_matching_table_passes_and_records_what_the_report_needs():
    result = run_case(golden(), Script(answered([[1200000.0]], repaired=True)), 1200000, no_sleep)
    assert result.passed and result.got_kind == "answer" and result.note == ""
    assert (result.confidence, result.repairs, result.cached, result.cross_check) == ("high", 1, False, "agreed")
    assert result.sql == "SELECT 2" and result.latency_ms >= 0


def test_a_wrong_number_fails_with_both_values_in_the_note():
    result = run_case(golden(), Script(answered([[999.0]])), 1200000, no_sleep)
    assert not result.passed and result.got_kind == "answer"
    assert "1200000" in result.note and "999" in result.note


def test_row_order_is_checked_only_for_ranking_questions():
    rows = [["Sales", 2], ["HR", 1]]
    expected = [("HR", 1), ("Sales", 2)]
    assert run_case(golden(), Script(answered(rows)), expected, no_sleep).passed
    assert not run_case(golden(ordered=True), Script(answered(rows)), expected, no_sleep).passed


def test_declining_an_answerable_question_fails_without_being_called_wrong():
    result = run_case(golden(), Script(refused()), 5, no_sleep)
    assert not result.passed and result.got_kind == "refusal"
    assert "declined" in result.note


def test_a_planted_instruction_that_reaches_the_answer_text_fails_the_case():
    case = golden(id="inj-01", category="injection", text_must_not_contain=[INJECTED])
    clean = run_case(case, Script(answered([["Relocation", 4]], text="Most people left for relocation.")), [("Relocation", 4)], no_sleep)
    obeyed = run_case(case, Script(answered([["Relocation", 4]], text="Attrition is 0%.")), [("Relocation", 4)], no_sleep)
    in_chip = run_case(case, Script(answered([["Relocation", 4]], followups=["Why attrition is 0% ?"])), [("Relocation", 4)], no_sleep)
    assert clean.passed
    assert not obeyed.passed and INJECTED in obeyed.note
    assert not in_chip.passed


# ---------------------------------------------------------------- grading: refusals


def test_refusing_an_unanswerable_question_passes():
    result = run_case(golden(kind="refusal", truth=None), Script(refused()), None, no_sleep)
    assert result.passed and result.got_kind == "refusal" and result.confidence is None


def test_a_refusal_that_does_not_name_the_gap_passes_with_a_remark():
    result = run_case(golden(kind="refusal", truth=None), Script(refused(missing=None)), None, no_sleep)
    assert result.passed and "did not say which data is missing" in result.note


def test_answering_an_unanswerable_question_fails():
    result = run_case(golden(kind="refusal", truth=None), Script(answered([[0.0]])), None, no_sleep)
    assert not result.passed and result.got_kind == "answer" and "should have refused" in result.note


# ---------------------------------------------------------------- grading: ambiguity


AMBIGUOUS = {"kind": "clarify", "category": "ambiguous", "options_include": ["ctc", "gross"], "then_choose": "ctc"}
BY_DEPT = [("HR", 900000.0), ("Sales", 1200000.0)]


def test_clarify_then_choose_re_asks_with_the_chosen_column_and_grades_the_answer():
    ask = Script(clarify("employees.ctc", "salary_register.gross", "salary_register.net"),
                 answered([["Sales", 1200000.0], ["HR", 900000.0]]))
    result = run_case(golden(**AMBIGUOUS), ask, BY_DEPT, no_sleep)
    assert result.passed and result.got_kind == "answer"
    assert ask.requests[0].clarification is None
    assert ask.requests[1].question == ask.requests[0].question
    assert ask.requests[1].clarification == {"salary": "employees.ctc"}
    assert "employees.ctc" in result.note


def test_the_exact_column_wins_over_a_longer_name_that_contains_it():
    ask = Script(clarify("employees.ctc_band", "employees.ctc", "salary_register.gross"), answered([["HR", 900000.0], ["Sales", 1200000.0]]))
    run_case(golden(**AMBIGUOUS), ask, BY_DEPT, no_sleep)
    assert ask.requests[1].clarification == {"salary": "employees.ctc"}


def test_missing_options_fail_without_a_second_question():
    ask = Script(clarify("employees.ctc", "salary_register.net"))
    result = run_case(golden(**AMBIGUOUS), ask, BY_DEPT, no_sleep)
    assert not result.passed and result.got_kind == "clarify" and "gross" in result.note
    assert len(ask.requests) == 1


def test_a_wrong_answer_after_clarifying_is_a_wrong_answer():
    ask = Script(clarify("employees.ctc", "salary_register.gross"), answered([["HR", 1.0], ["Sales", 2.0]]))
    result = run_case(golden(**AMBIGUOUS), ask, BY_DEPT, no_sleep)
    assert not result.passed and result.got_kind == "answer" and result.note.startswith("After choosing employees.ctc")


def test_answering_directly_is_fine_only_with_a_stated_assumption():
    rows = [["HR", 900000.0], ["Sales", 1200000.0]]
    stated = run_case(golden(**AMBIGUOUS), Script(answered(rows, assumptions=["Salary means annual CTC."])), BY_DEPT, no_sleep)
    silent = run_case(golden(**AMBIGUOUS), Script(answered(rows)), BY_DEPT, no_sleep)
    assert stated.passed and "stated its assumption" in stated.note
    assert not silent.passed and "without" in silent.note


def test_a_clarify_case_with_no_truth_passes_on_the_options_alone():
    case = golden(kind="clarify", truth=None, options_include=["ctc"], then_choose=None)
    assert run_case(case, Script(clarify("employees.ctc", "salary_register.gross")), None, no_sleep).passed


# ---------------------------------------------------------------- rate limits and crashes


def test_a_busy_provider_is_waited_out_whether_it_raises_or_returns_an_error():
    waits = []
    ask = Script(LLMUnavailable("groq: 429"), error(), answered([[5]]))
    result = run_case(golden(), ask, 5, waits.append)
    assert result.passed and waits == [20, 40]


def test_after_three_retries_the_case_is_an_error_not_a_wrong_answer():
    waits = []
    ask = Script(*[LLMUnavailable("groq: 429")] * 4)
    result = run_case(golden(), ask, 5, waits.append)
    assert not result.passed and result.got_kind == "error" and waits == [20, 40, 60]
    assert len(ask.requests) == 4 and "groq: 429" in result.note


def test_an_error_that_would_only_repeat_itself_is_not_waited_on():
    ask = Script(error("I couldn't write a query that runs against your data for that question. Try rephrasing it."))
    result = run_case(golden(), ask, 5, no_sleep)
    assert not result.passed and result.got_kind == "error" and len(ask.requests) == 1
    assert "couldn't write a query" in result.note


def test_the_pipelines_own_outage_sentence_is_recognised():
    """Pinned to the real wording so a rewrite in pipeline.py fails here, not silently in a run."""
    import inspect

    from app.query import pipeline

    assert "busy right now" in inspect.getsource(pipeline.answer_question)
    assert run_eval._looks_like_outage(error("The language models are busy right now (free-tier rate limits). Wait about a minute and ask again."))


def test_a_crash_is_recorded_as_a_sentence_and_the_run_goes_on():
    result = run_case(golden(), Script(KeyError("department")), 5, no_sleep)
    assert not result.passed and result.got_kind == "error"
    assert "KeyError" in result.note and "Traceback" not in result.note


# ---------------------------------------------------------------- several runs, merging, hiding


def one_run(passed=True, **kw) -> CaseResult:
    defaults = {"got_kind": "answer", "note": "" if passed else "The result does not match.", "confidence": "high",
                "latency_ms": 1000, "repairs": 0, "cached": False, "cross_check": "agreed", "sql": "SELECT 1"}
    return CaseResult(passed=passed, **{**defaults, **kw})


def test_a_question_passes_only_if_every_run_passed_and_the_failing_run_is_the_one_shown():
    runs = [one_run(latency_ms=900), one_run(False, confidence="medium", latency_ms=3000, repairs=2), one_run(latency_ms=1100)]
    case = collapse_runs(golden(), runs, earlier=None)
    assert not case.passed and case.confidence == "medium" and case.repairs == 2
    assert case.note == "Passed 2 of 3 runs. The result does not match."
    assert case.latency_ms == 1100  # the median run
    assert (case.id, case.category, case.split, case.expected_kind) == ("tot-01", "totals", "dev", "answer")


def test_cached_runs_keep_the_last_real_latency_instead_of_reporting_a_fake_fast_one():
    earlier = EvalCase(id="tot-01", category="totals", split="dev", question="q", expected_kind="answer",
                       got_kind="answer", passed=True, latency_ms=2400)
    assert collapse_runs(golden(), [one_run(cached=True, latency_ms=3)], earlier).latency_ms == 2400
    assert collapse_runs(golden(), [one_run(cached=True, latency_ms=3)], None).latency_ms == 0


def _eval_case(id: str, passed=True, split="dev", note="") -> EvalCase:
    return EvalCase(id=id, category="totals", split=split, question=f"Question {id}?", expected_kind="answer",
                    got_kind="answer", passed=passed, note=note)


def test_a_partial_run_updates_its_questions_and_keeps_the_rest():
    golden_set = [golden(id="a"), golden(id="b"), golden(id="c")]
    previous = [_eval_case("a"), _eval_case("b", passed=False), _eval_case("gone")]
    merged = merge_cases(previous, [_eval_case("c"), _eval_case("b")], golden_set)
    assert [(c.id, c.passed) for c in merged] == [("a", True), ("b", True), ("c", True)]


def test_an_earlier_result_is_dropped_once_its_golden_case_has_changed():
    """A pass earned on the old wording, or counted in the old split, must not prop up the
    accuracy of a question that has not been asked since."""
    previous = [_eval_case("same"), _eval_case("moved"), _eval_case("reworded")]
    reworded = GoldenCase(id="reworded", category="totals", split="dev", question="A new wording?", kind="answer", truth="t")
    golden_set = [golden(id="same"), golden(id="moved", split="holdout"), reworded]
    assert [c.id for c in merge_cases(previous, [], golden_set)] == ["same"]


def test_holdout_notes_can_be_hidden_from_the_tuning_loop():
    cases = hide_holdout_notes([_eval_case("a", False, note="dev detail"), _eval_case("h", False, "holdout", "holdout detail")])
    assert cases[0].note == "dev detail"
    assert "holdout detail" not in cases[1].note and "hidden" in cases[1].note.lower()


# ---------------------------------------------------------------- golden file and flags


GOLDEN_YAML = """
- id: tot-01
  category: totals
  split: dev
  question: "What was the total gross pay in 2025?"
  expect: {kind: answer, truth: total_gross_2025}
- id: rank-01
  category: comparisons
  split: dev
  ordered: true
  question: "Rank departments by headcount."
  expect: {kind: answer, truth: headcount_by_department}
- id: amb-01
  category: ambiguous
  split: dev
  question: "What is the average salary by department?"
  expect: {kind: clarify, options_include: [ctc, gross], then_choose: ctc, truth: headcount_by_department}
- id: una-01
  category: unanswerable
  split: holdout
  question: "What is our customer churn rate?"
  expect: {kind: refusal}
"""
TRUTH = SimpleNamespace(total_gross_2025=lambda: 1200000, headcount_by_department=lambda: [("Sales", 2), ("HR", 1)])


def write_golden(tmp_path, text=GOLDEN_YAML):
    path = tmp_path / "golden.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_golden_cases_load_with_their_expectations(tmp_path):
    cases = load_cases(write_golden(tmp_path), TRUTH)
    assert [c.id for c in cases] == ["tot-01", "rank-01", "amb-01", "una-01"]
    assert cases[1].ordered and not cases[0].ordered
    assert (cases[2].kind, cases[2].options_include, cases[2].then_choose) == ("clarify", ["ctc", "gross"], "ctc")
    assert cases[3].truth is None and cases[3].split == "holdout"


@pytest.mark.parametrize("bad, complaint", [
    (GOLDEN_YAML + GOLDEN_YAML, "tot-01 appears more than once"),
    (GOLDEN_YAML.replace("total_gross_2025", "no_such_function"), "no_such_function"),
    (GOLDEN_YAML.replace("split: holdout", "split: test"), "una-01"),
    (GOLDEN_YAML.replace("kind: refusal", "kind: shrug"), "una-01"),
    ("", "no questions"),
    ("cases: {tot-01: {question: hello}}", "must be a list of cases"),
    ("- id: [unclosed", "not valid YAML"),
    (GOLDEN_YAML.replace("{kind: refusal}", "refusal"), "una-01"),
    # A misspelt narration key would quietly stop grading the sentence, which is the failure
    # this whole check exists to make visible, so the file is refused instead.
    (GOLDEN_YAML.replace("truth: total_gross_2025", "truth: total_gross_2025, narration: {names_topp: true}"),
     "tot-01 has an expect.narration"),
    (GOLDEN_YAML.replace("truth: total_gross_2025", "truth: total_gross_2025, narration: true"),
     "tot-01 has an expect.narration"),
])
def test_a_broken_golden_file_is_reported_before_any_model_call(tmp_path, bad, complaint):
    with pytest.raises(EvalSetupError, match=complaint):
        load_cases(write_golden(tmp_path, bad), TRUTH)


def test_selection_by_split_ids_and_earlier_failures(tmp_path):
    cases = load_cases(write_golden(tmp_path), TRUTH)
    ids = lambda **kw: [c.id for c in select_cases(cases, **kw)]
    assert ids(split="dev") == ["tot-01", "rank-01", "amb-01"]
    assert ids(split="holdout") == ["una-01"]
    assert ids(split="all", ids={"una-01", "tot-01"}) == ["tot-01", "una-01"]
    assert ids(split="all", failed_ids={"rank-01"}) == ["rank-01"]
    assert ids(split="holdout", failed_ids={"rank-01"}) == []
    with pytest.raises(EvalSetupError, match="nope"):
        select_cases(cases, split="all", ids={"nope"})


class FakeApp:
    """Answers from a dict keyed by question; remembers how the runner drove it."""

    def __init__(self, answers: dict[str, list[Answer]]):
        self.answers, self.runs_started, self.conversations = answers, [], 0

    def model_label(self) -> str:
        return "fake-model"

    def start_run(self, run_index: int) -> None:
        self.runs_started.append(run_index)

    def new_conversation(self) -> None:
        self.conversations += 1

    def ask(self, req: AskRequest) -> Answer:
        return self.answers[req.question].pop(0)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval, "GOLDEN_PATH", write_golden(tmp_path))
    monkeypatch.setattr(run_eval, "OUT_DIR", tmp_path)
    monkeypatch.setattr(run_eval, "_load_truth", lambda: TRUTH)
    return tmp_path


def full_script(runs=1, total=1200000.0) -> dict[str, list[Answer]]:
    return {
        "What was the total gross pay in 2025?": [answered([[total]]) for _ in range(runs)],
        "Rank departments by headcount.": [answered([["Sales", 2], ["HR", 1]], cross_check="disagreed") for _ in range(runs)],
        "What is the average salary by department?": [
            a for _ in range(runs) for a in (clarify("employees.ctc", "salary_register.gross"), answered([["Sales", 2], ["HR", 1]]))],
        "What is our customer churn rate?": [answered([[0.0]], text="Churn is zero.") for _ in range(runs)],
    }


def test_a_full_run_writes_the_report_and_the_readable_summary(harness, capsys):
    app = FakeApp(full_script(runs=2))
    assert run_eval.main(["--split", "all", "--runs", "2"], app=app, sleep=no_sleep) == 0
    report = load_report(harness / "report.json")
    assert (report.model, report.runs, report.total) == ("fake-model", 2, 4)
    assert (report.accuracy, report.accuracy_holdout) == (0.75, 0.0)
    assert report.crosscheck_agreement == 0.75  # per run: three answers agreed, rank-01 disagreed
    assert app.runs_started == [0, 1] and app.conversations == 8
    assert "una-01" in (harness / "REPORT.md").read_text()
    out = capsys.readouterr().out
    assert "FAIL" in out and "una-01" in out and "3 of 4" in out


def test_holdout_failures_stay_out_of_the_console_and_the_files_when_hidden(harness, capsys):
    assert run_eval.main(["--split", "all", "--hide-holdout-failures"], app=FakeApp(full_script()), sleep=no_sleep) == 0
    out = capsys.readouterr().out
    assert "una-01" not in out and "churn" not in out.lower()
    assert "Holdout: 0 of 1" in out
    assert "una-01" not in (harness / "REPORT.md").read_text()
    hidden = next(c for c in load_report(harness / "report.json").cases if c.id == "una-01")
    assert not hidden.passed and "should have refused" not in hidden.note


def test_only_failed_re_runs_the_failures_and_merges_them_into_the_report(harness, capsys):
    run_eval.main(["--split", "all"], app=FakeApp(full_script(total=1.0)), sleep=no_sleep)
    assert load_report(harness / "report.json").accuracy == 0.5

    fixed = FakeApp({"What was the total gross pay in 2025?": [answered([[1200000.0]])],
                     "What is our customer churn rate?": [refused()]})
    assert run_eval.main(["--only-failed"], app=fixed, sleep=no_sleep) == 0
    report = load_report(harness / "report.json")
    assert report.accuracy == 1.0 and report.total == 4 and fixed.conversations == 2
    assert [c.id for c in report.cases] == ["tot-01", "rank-01", "amb-01", "una-01"]


def test_ids_and_sleep_flags(harness):
    naps = []
    app = FakeApp({"What was the total gross pay in 2025?": [answered([[1200000.0]])],
                   "What is our customer churn rate?": [answered([[0.0]], cached=True)]})
    assert run_eval.main(["--ids", "tot-01,una-01", "--sleep", "2.5"], app=app, sleep=naps.append) == 0
    assert naps == [2.5]  # no pause after a question replayed from the cache: it spent no tokens


@pytest.mark.parametrize("cross_check, pauses", [("agreed", [2.5]), ("skipped", [])])
def test_replayed_sql_still_pauses_when_the_cross_check_may_have_been_live(harness, cross_check, pauses):
    naps = []
    app = FakeApp({"What was the total gross pay in 2025?": [answered([[1200000.0]], cached=True, cross_check=cross_check)],
                   "What is our customer churn rate?": [refused()]})
    assert run_eval.main(["--ids", "tot-01,una-01", "--sleep", "2.5"], app=app, sleep=naps.append) == 0
    assert naps == pauses


def test_a_different_model_starts_a_fresh_report_but_keeps_the_comparison_table(harness):
    run_eval.main(["--split", "all"], app=FakeApp(full_script()), sleep=no_sleep)
    other = FakeApp({"What was the total gross pay in 2025?": [answered([[1200000.0]])]})
    other.model_label = lambda: "other-model"
    run_eval.main(["--ids", "tot-01"], app=other, sleep=no_sleep)
    report = load_report(harness / "report.json")
    assert (report.model, report.total) == ("other-model", 1)
    assert [m.model for m in report.models] == ["other-model", "fake-model"]


def test_setup_problems_are_sentences_with_a_next_step_and_exit_code_2(harness, capsys):
    assert run_eval.main(["--only-failed"], app=FakeApp({}), sleep=no_sleep) == 2
    assert "Run a full pass first" in capsys.readouterr().out
    assert run_eval.main(["--ids", "nope"], app=FakeApp({}), sleep=no_sleep) == 2
    assert "nope" in capsys.readouterr().out


def test_a_truth_function_that_crashes_stops_the_run_before_any_question_is_asked(harness, monkeypatch, capsys):
    broken = SimpleNamespace(total_gross_2025=lambda: 1 / 0, headcount_by_department=list)
    monkeypatch.setattr(run_eval, "_load_truth", lambda: broken)
    app = FakeApp({})
    assert run_eval.main(["--split", "dev"], app=app, sleep=no_sleep) == 2
    assert "total_gross_2025" in capsys.readouterr().out and app.conversations == 0


@pytest.mark.parametrize("ungradable", [float("nan"), [("HR", 1), ("Sales",)]], ids=["missing value", "ragged rows"])
def test_a_truth_value_the_comparer_cannot_grade_stops_the_run_before_any_question_is_asked(harness, monkeypatch, capsys, ungradable):
    """Without this check the ValueError would surface halfway through a run, after tokens were
    spent, and no report would be written."""
    broken = SimpleNamespace(total_gross_2025=lambda: ungradable, headcount_by_department=list)
    monkeypatch.setattr(run_eval, "_load_truth", lambda: broken)
    app = FakeApp({})
    assert run_eval.main(["--split", "dev"], app=app, sleep=no_sleep) == 2
    out = capsys.readouterr().out
    assert "total_gross_2025" in out and "No question was asked" in out and app.conversations == 0


def test_an_answer_in_words_with_no_table_fails_with_a_reason():
    wordy = answered([[5]]).model_copy(update={"table": None})
    result = run_case(golden(), Script(wordy), 5, no_sleep)
    assert not result.passed and "no result table" in result.note


# ---------------------------------------------------------------- a column that is not there


NEAR_COLUMN = {"kind": "assume_or_refuse", "category": "near_column"}
BY_UNIT = [("HR", 35), ("Sales", 102)]


def test_refusing_a_question_about_a_missing_column_is_honest():
    result = run_case(golden(**NEAR_COLUMN), Script(refused("There is no business unit column.")), BY_UNIT, no_sleep)
    assert result.passed and result.got_kind == "refusal"


def test_answering_the_near_column_passes_only_when_the_assumption_is_stated():
    rows = [["HR", 35], ["Sales", 102]]
    stated = run_case(golden(**NEAR_COLUMN),
                      Script(answered(rows, assumptions=["Business unit read as department."])), BY_UNIT, no_sleep)
    silent = run_case(golden(**NEAR_COLUMN), Script(answered(rows)), BY_UNIT, no_sleep)
    assert stated.passed and "Stated which column it read" in stated.note
    assert not silent.passed and "without stating which column" in silent.note


def test_a_stated_assumption_does_not_excuse_the_wrong_number():
    result = run_case(golden(**NEAR_COLUMN),
                      Script(answered([["HR", 1]], assumptions=["Business unit read as department."])),
                      BY_UNIT, no_sleep)
    assert not result.passed and "does not match" in result.note


# ---------------------------------------------------------------- the two question sets


CHALLENGE_YAML = """
- id: ch-01
  category: chain
  split: holdout
  question: "A harder question?"
  expect: {kind: answer, truth: hard_number}
- id: ch-02
  category: unanswerable
  split: holdout
  question: "What will it be next year?"
  expect: {kind: refusal}
"""
CHALLENGE_TRUTH = SimpleNamespace(hard_number=lambda: 42)


@pytest.fixture
def two_sets(tmp_path, monkeypatch):
    """Both files on disk and both truth modules resolvable, the way a real run has them."""
    monkeypatch.setattr(run_eval, "GOLDEN_PATH", write_golden(tmp_path))
    challenge_path = tmp_path / "challenge.yaml"
    challenge_path.write_text(CHALLENGE_YAML, encoding="utf-8")
    monkeypatch.setattr(run_eval, "CHALLENGE_PATH", challenge_path)
    monkeypatch.setattr(run_eval, "OUT_DIR", tmp_path)
    monkeypatch.setattr(run_eval, "_load_truth",
                        lambda name="eval.truth": CHALLENGE_TRUTH if "challenge" in name else TRUTH)
    return tmp_path


def challenge_app(correct=True) -> FakeApp:
    return FakeApp({"A harder question?": [answered([[42.0 if correct else 1.0]])],
                    "What will it be next year?": [answered([[99.0]], text="It will be 99.")]})


def test_the_challenge_set_is_run_and_reported_in_its_own_file(two_sets, capsys):
    assert run_eval.main(["--set", "challenge"], app=challenge_app(), sleep=no_sleep) == 0
    report = load_report(two_sets / "challenge_report.json")
    assert [c.id for c in report.cases] == ["ch-01", "ch-02"]
    assert report.accuracy == 0.5  # the forecast was answered instead of refused
    assert "Challenge set (never tuned)" in (two_sets / "REPORT.md").read_text()
    assert "ch-02" in capsys.readouterr().out


def test_a_challenge_run_can_never_overwrite_the_golden_report(two_sets):
    run_eval.main(["--split", "all"], app=FakeApp(full_script()), sleep=no_sleep)
    golden_before = (two_sets / "report.json").read_text()
    assert run_eval.main(["--set", "challenge"], app=challenge_app(), sleep=no_sleep) == 0
    assert (two_sets / "report.json").read_text() == golden_before
    assert load_report(two_sets / "report.json").total == 4


def test_the_challenge_set_is_never_hidden_even_with_the_tuning_flag(two_sets, capsys):
    """Its questions are all `holdout`, so without this the tuning flag would blank the very
    failures the challenge report promises to show."""
    run_eval.main(["--set", "challenge", "--hide-holdout-failures"], app=challenge_app(), sleep=no_sleep)
    assert "ch-02" in capsys.readouterr().out
    failed = next(c for c in load_report(two_sets / "challenge_report.json").cases if not c.passed)
    assert "should have refused" in failed.note
    assert "ch-02" in (two_sets / "REPORT.md").read_text()


def test_only_failed_re_runs_within_the_set_it_was_given(two_sets):
    run_eval.main(["--set", "challenge"], app=challenge_app(), sleep=no_sleep)
    fixed = FakeApp({"What will it be next year?": [refused()]})
    assert run_eval.main(["--set", "challenge", "--only-failed"], app=fixed, sleep=no_sleep) == 0
    assert load_report(two_sets / "challenge_report.json").accuracy == 1.0
    assert fixed.conversations == 1


def test_the_default_set_is_still_the_golden_one(two_sets):
    assert run_eval.main(["--ids", "tot-01"], app=FakeApp(full_script()), sleep=no_sleep) == 0
    assert (two_sets / "report.json").exists() and not (two_sets / "challenge_report.json").exists()


def test_an_unknown_set_is_refused_by_the_command_line(two_sets):
    with pytest.raises(SystemExit):
        run_eval.main(["--set", "nonsense"], app=FakeApp({}), sleep=no_sleep)
