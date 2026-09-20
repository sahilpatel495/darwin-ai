"""The runner wired to the real app and the real sample data, with a scripted model.

This is the seam the unit tests cannot see: sample data loads, the pipeline is called the way
it expects, the answer is graded against the independent pandas truth, and the report lands
on disk. It also proves one golden question end to end without spending a token.
"""

import json

import pytest
from app.config import settings
from app.llm.fake import FakeLLM

from eval import run_eval
from eval.report import load_report

ACTIVE_HEADCOUNT_SQL = "SELECT count(*) AS active_employees FROM employees e WHERE e.exit_date IS NULL"


def scripted_model() -> FakeLLM:
    generation = {"status": "ok", "interpretation": "Count employees with no exit date.", "plan": ["Count"],
                  "assumptions": [], "sql": ACTIVE_HEADCOUNT_SQL, "clarify_question": "", "clarify_options": [],
                  "missing": "", "metrics_used": []}
    narration = {"text": "The table shows the number of active employees.", "reading": "Counts employees with no exit date.",
                 "followups": []}
    return FakeLLM({"sql": [json.dumps(generation)], "narrate": [json.dumps(narration)]})


@pytest.fixture
def real_app(tmp_path, monkeypatch):
    """Keys, cache and report all point away from the real ones; settings are put back after."""
    before = (settings.crosscheck, settings.llm_cache_dir)
    monkeypatch.setenv("GROQ_API_KEY", "not-a-real-key")  # only so a chain resolves; no call is made
    monkeypatch.delenv("LLM_SQL_CHAIN", raising=False)
    monkeypatch.setattr(run_eval, "OUT_DIR", tmp_path)
    monkeypatch.setattr(run_eval, "CACHE_DIR", tmp_path / "llm_cache")
    monkeypatch.setattr("app.llm.client.PoolClient", scripted_model)
    yield tmp_path
    object.__setattr__(settings, "crosscheck", before[0])
    object.__setattr__(settings, "llm_cache_dir", before[1])


def test_one_golden_question_end_to_end_on_the_sample_data(real_app, capsys):
    if not (run_eval.GOLDEN_PATH.exists() and any(settings.demo_data_dir.glob("*.csv"))):
        pytest.skip("the golden set or the sample data is not generated yet")
    try:
        exit_code = run_eval.main(["--ids", "tot-02", "--no-crosscheck"], sleep=lambda seconds: None)
    except NotImplementedError:
        pytest.skip("a module behind the sample session is not built yet")

    assert exit_code == 0, capsys.readouterr().out
    report = load_report(real_app / "report.json")
    case = report.cases[0]
    assert (case.id, case.got_kind) == ("tot-02", "answer"), case.note
    assert case.passed, case.note
    assert report.model == "openai/gpt-oss-120b" and report.crosscheck_agreement is None
    assert settings.llm_cache_dir == str(real_app / "llm_cache")
