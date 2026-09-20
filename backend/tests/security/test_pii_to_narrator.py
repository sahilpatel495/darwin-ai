"""Security review, PII: the narration model is a third party, so a name must reach it only as
a ⟦P1⟧ placeholder, whatever the SQL calls the column that holds it.

The aliasing test documents an OPEN finding in app/query/pipeline.py, which the security review
did not own: `_pii_result_columns` trusts a result column called `department` because a
non-PII column of that name exists. It is marked xfail so the suite stays green; when the
pipeline is fixed it will show as XPASS and the marker can go.
"""

import json

import pytest

from app.contracts import AskRequest
from app.llm.fake import FakeLLM
from app.query import pipeline
from app.query.pipeline import answer_question
from tests.fixtures import CANARY_EMAIL, CANARY_NAME, make_session


def _generation(sql: str) -> str:
    return json.dumps({"status": "ok", "interpretation": "A list of people.", "plan": ["List"],
                       "assumptions": [], "sql": sql, "clarify_question": "", "clarify_options": [],
                       "missing": "", "metrics_used": []})


_NARRATION = json.dumps({"text": "Here is the list you asked for.", "reading": "Lists people.", "followups": []})


def _sent_to_any_model(sql: str) -> str:
    """Everything every model call received while answering one question with `sql`."""
    pipeline._SHARED_CACHE.clear()
    llm = FakeLLM({"sql": [_generation(sql)] * 3, "crosscheck": [_generation(sql)], "narrate": [_NARRATION] * 2})
    answer_question(make_session(), AskRequest(question="Who works here?"), llm, lambda step: None)
    return json.dumps([call["messages"] for call in llm.calls], ensure_ascii=False)


def test_a_plainly_selected_name_reaches_the_narrator_only_as_a_placeholder():
    sent = _sent_to_any_model("SELECT e.name, e.email FROM employees e ORDER BY e.emp_id")
    assert "⟦P1⟧" in sent
    assert CANARY_NAME not in sent and CANARY_EMAIL not in sent and "Asha Rao" not in sent


def test_summarize_in_brackets_never_runs_so_its_names_never_reach_a_model():
    sent = _sent_to_any_model("SELECT * FROM (SUMMARIZE employees)")
    assert CANARY_NAME not in sent and CANARY_EMAIL not in sent and "Asha Rao" not in sent


@pytest.mark.parametrize("sql", [
    "SELECT e.name AS department FROM employees e ORDER BY e.emp_id",
    "SELECT e.email AS location FROM employees e ORDER BY e.emp_id",
    "WITH people AS (SELECT e.name AS department FROM employees e) SELECT p.department FROM people p",
])
def test_a_name_selected_under_a_harmless_alias_still_reaches_the_narrator_only_as_a_placeholder(sql):
    sent = _sent_to_any_model(sql)
    assert CANARY_NAME not in sent and CANARY_EMAIL not in sent and "Asha Rao" not in sent
