"""A sentence can be wrong with none of the numbers wrong.

"Engineering has the highest average salary at ₹13.34 L" passed the number check in front of a
real user while Support sat at ₹15.53 L in the top row: every number was in the result, and the
ranking was invented. These tests hold the line for the claims themselves — a name beside its
own row's number, and a rank word only over the row that holds the rank.
"""

import json

import pytest
from app.contracts import ResultTable
from app.llm.fake import FakeLLM
from app.query.narrator import narrate

SQL = "SELECT department, avg(ctc) AS avg_ctc FROM employees GROUP BY 1 ORDER BY 2 DESC"

CTC_QUESTION = "What is the average CTC by department?"
CTC = ResultTable(
    columns=["department", "avg_ctc"],
    rows=[["Support", 1553000.0], ["Engineering", 1334000.0], ["HR", 1307000.0],
          ["Finance", 1210000.0], ["Sales", 1150000.0], ["Operations", 1039000.0]],
    display=[["Support", "₹15.53 L"], ["Engineering", "₹13.34 L"], ["HR", "₹13.07 L"],
             ["Finance", "₹12.10 L"], ["Sales", "₹11.50 L"], ["Operations", "₹10.39 L"]],
    row_count=6,
)
# The sentence as it was shown to the user, under a High-confidence badge.
WRONG = ("Engineering has the highest average salary at ₹13.34 L, followed by HR at ₹13.07 L, "
         "and Operations has the lowest at ₹10.39 L.")
RIGHT = ("Support has the highest average CTC at ₹15.53 L, followed by Engineering at ₹13.34 L, "
         "and Operations has the lowest at ₹10.39 L.")

GROSS_QUESTION = "What was the total gross pay by department in 2025?"
GROSS = ResultTable(
    columns=["department", "total_gross_pay"],
    rows=[["Engineering", 204000000.0], ["Sales", 120500000.0], ["Operations", 70000000.0],
          ["Finance", 36900000.0]],
    display=[["Engineering", "₹20.40 Cr"], ["Sales", "₹12.05 Cr"], ["Operations", "₹7.00 Cr"],
             ["Finance", "₹3.69 Cr"]],
    row_count=4,
)

MONTHS_QUESTION = "How did total gross pay change month by month in 2025?"
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_CRORES = [4.38, 4.40, 4.42, 4.45, 4.50, 4.55, 4.60, 4.62, 4.65, 4.70, 4.76, 4.73]  # Nov is the peak
MONTHS = ResultTable(
    columns=["month", "total_gross_pay"],
    rows=[[f"2025-{i:02d}-01", round(crore * 10_000_000)] for i, crore in enumerate(_CRORES, start=1)],
    display=[[f"01 {name} 2025", f"₹{crore:.2f} Cr"] for name, crore in zip(_MONTHS, _CRORES)],
    row_count=12,
)

BONUS = ResultTable(
    columns=["employee", "bonus"],
    rows=[["Asha Rao", 300000.0], ["Rohan Das", 200000.0], ["Meera Iyer", 100000.0]],
    display=[["Asha Rao", "₹3.00 L"], ["Rohan Das", "₹2.00 L"], ["Meera Iyer", "₹1.00 L"]],
    row_count=3,
)

# Two label columns: "the highest" would have to pick a dimension, so nothing is checked.
GROUPED = ResultTable(
    columns=["department", "location", "headcount"],
    rows=[["Engineering", "Bengaluru", 150], ["Engineering", "Mumbai", 120], ["Sales", "Mumbai", 90]],
    display=[["Engineering", "Bengaluru", "150"], ["Engineering", "Mumbai", "120"], ["Sales", "Mumbai", "90"]],
    row_count=3,
)


def say(text: str, reading: str = "Averages CTC for each department.", followups=("Split that by location",)) -> str:
    return json.dumps({"text": text, "reading": reading, "followups": list(followups)})


def run(llm, table, question, *, caveats=(), pii_columns=(), notes=None):
    return narrate(llm, question=question, sql=SQL, table=table, caveats=list(caveats),
                   pii_columns=set(pii_columns), notes=notes)


def correction(llm: FakeLLM) -> str:
    """What the second call told the model about the first reply."""
    return llm.calls[1]["messages"][-1]["content"]


# --------------------------------------------------------------------------- facts in the prompt


def test_the_ranking_is_computed_and_handed_to_the_model():
    llm = FakeLLM({"narrate": [say(RIGHT)]})
    run(llm, CTC, CTC_QUESTION)
    prompt = llm.calls[0]["messages"][-1]["content"]
    assert "Facts you may state:" in prompt
    assert "- The result has 6 rows." in prompt
    assert "- Highest average CTC: Support at ₹15.53 L." in prompt
    assert "- Lowest average CTC: Operations at ₹10.39 L." in prompt
    assert "1553000" not in prompt  # facts are display strings, like everything else sent


def test_a_dated_series_also_gets_its_two_ends():
    llm = FakeLLM({"narrate": [say("Total gross pay ended the year at ₹4.73 Cr.")]})
    run(llm, MONTHS, MONTHS_QUESTION)
    prompt = llm.calls[0]["messages"][-1]["content"]
    assert "- Highest total gross pay: 01 Nov 2025 at ₹4.76 Cr." in prompt
    assert "- Earliest: 01 Jan 2025 at ₹4.38 Cr." in prompt
    assert "- Latest: 01 Dec 2025 at ₹4.73 Cr." in prompt


def test_notes_are_shown_beside_the_caveats():
    llm = FakeLLM({"narrate": [say(RIGHT)]})
    run(llm, CTC, CTC_QUESTION, caveats=["Duplicate rows were excluded."], notes=["CTC is annual."])
    prompt = llm.calls[0]["messages"][-1]["content"]
    assert "Notes about the data:\n- Duplicate rows were excluded.\n- CTC is annual." in prompt


# --------------------------------------------------------------------------- the live bug


def test_the_live_bug_is_rejected_and_the_model_is_told_exactly_what_was_wrong():
    llm = FakeLLM({"narrate": [say(WRONG), say(RIGHT)]})
    narration, _, used_fallback = run(llm, CTC, CTC_QUESTION)
    assert not used_fallback and narration.text == RIGHT  # the second attempt is right, so it is used
    assert "You wrote that Engineering is highest. The highest is Support at ₹15.53 L." in correction(llm)


def test_a_second_wrong_ranking_ends_in_a_sentence_code_wrote():
    llm = FakeLLM({"narrate": [say(WRONG), say("HR has the highest average CTC at ₹13.07 L.")]})
    narration, _, used_fallback = run(llm, CTC, CTC_QUESTION)
    assert used_fallback and narration.text == (
        "Support has the highest average CTC at ₹15.53 L and Operations the lowest at ₹10.39 L, "
        "across 6 groups.")
    assert narration.reading == "" and narration.followups == []  # nothing from the model is kept


def test_a_wrong_peak_in_a_monthly_series_ends_in_the_dated_sentence():
    wrong = "Total gross pay peaked in December at ₹4.73 Cr."
    llm = FakeLLM({"narrate": [say(wrong), say(wrong)]})
    narration, _, used_fallback = run(llm, MONTHS, MONTHS_QUESTION)
    assert used_fallback and narration.text == (
        "Total gross pay went from ₹4.38 Cr in Jan 2025 to ₹4.73 Cr in Dec 2025; "
        "the highest was ₹4.76 Cr in Nov 2025.")


def test_a_number_beside_the_wrong_name_is_rejected():
    swapped = "Engineering received ₹12.05 Cr, and Sales received ₹20.40 Cr."
    llm = FakeLLM({"narrate": [say(swapped), say(swapped)]})
    _, _, used_fallback = run(llm, GROSS, GROSS_QUESTION)
    assert used_fallback
    assert "You put 12.05 Cr next to Engineering. Engineering is ₹20.40 Cr" in correction(llm)


# --------------------------------------------------------------------------- sentences that must pass


@pytest.mark.parametrize(
    ("table", "question", "text"),
    [
        (GROSS, GROSS_QUESTION,
         ("Engineering received the highest total gross pay in 2025 at ₹20.40 Cr, followed by "
          "Sales at ₹12.05 Cr, while Finance had the lowest at ₹3.69 Cr.")),
        (MONTHS, MONTHS_QUESTION,
         ("Total gross pay rose from ₹4.38 Cr in January to ₹4.73 Cr in December 2025, peaking "
          "at ₹4.76 Cr in November before falling slightly in December.")),
        (CTC, CTC_QUESTION, "Support has the highest average CTC at ₹15.53 L."),
        (ResultTable(columns=["total_gross_pay"], rows=[[546700000.0]], display=[["₹54.67 Cr"]], row_count=1),
         "What was the total gross pay in 2025?", "The total gross pay in 2025 was ₹54.67 Cr."),
        (ResultTable(columns=["attrition_pct"], rows=[[8.9]], display=[["8.9%"]], row_count=1),
         "What was our attrition rate in 2025?", "Our attrition rate in 2025 was 8.9%."),
    ],
)
def test_answers_from_the_real_evaluation_are_left_alone(table, question, text):
    """Every one of these is true of its result. A check that rewrites them is a worse product."""
    llm = FakeLLM({"narrate": [say(text)]})
    narration, _, used_fallback = run(llm, table, question)
    assert not used_fallback and len(llm.calls) == 1 and narration.text == text


@pytest.mark.parametrize("winner", ["Support", "Sales"])
def test_a_tie_for_highest_accepts_either_name(winner):
    tied = ResultTable(
        columns=["department", "avg_ctc"],
        rows=[["Support", 1553000.0], ["Sales", 1553000.0], ["Operations", 1039000.0]],
        display=[["Support", "₹15.53 L"], ["Sales", "₹15.53 L"], ["Operations", "₹10.39 L"]],
        row_count=3,
    )
    text = f"{winner} has the highest average CTC at ₹15.53 L."
    narration, _, used_fallback = run(FakeLLM({"narrate": [say(text)]}), tied, CTC_QUESTION)
    assert not used_fallback and narration.text == text


@pytest.mark.parametrize("written", ["January", "Jan", "Jan 2025", "2025-01", "01 Jan 2025"])
def test_every_spelling_of_a_date_means_the_same_row(written):
    good = f"Total gross pay was ₹4.38 Cr in {written}."
    assert not run(FakeLLM({"narrate": [say(good)]}), MONTHS, MONTHS_QUESTION)[2]
    bad = f"Total gross pay was ₹4.76 Cr in {written}."  # November's figure, on January
    assert run(FakeLLM({"narrate": [say(bad), say(bad)]}), MONTHS, MONTHS_QUESTION)[2]


def test_a_short_label_is_not_found_inside_a_longer_one():
    teams = ResultTable(columns=["team", "headcount"], rows=[["HR Ops", 40], ["HR", 12]],
                        display=[["HR Ops", "40"], ["HR", "12"]], row_count=2)
    text = "HR Ops is the largest team with 40 people."  # not a claim about HR, which is smaller
    narration, _, used_fallback = run(FakeLLM({"narrate": [say(text)]}), teams, "headcount by team")
    assert not used_fallback and narration.text == text


# --------------------------------------------------------------------------- shapes with no facts


def test_a_tokenised_label_column_is_checked_and_still_hides_the_names():
    llm = FakeLLM({"narrate": [say("⟦P2⟧ has the highest bonus at ₹2.00 L."),
                               say("⟦P1⟧ has the highest bonus at ₹3.00 L.")]})
    narration, payload, used_fallback = run(llm, BONUS, "Who got the biggest bonus?", pii_columns={"employee"})
    assert not used_fallback and narration.text == "Asha Rao has the highest bonus at ₹3.00 L."
    assert "The highest is ⟦P1⟧ at ₹3.00 L." in correction(llm)
    for name in ("Asha Rao", "Rohan Das", "Meera Iyer"):
        assert name not in json.dumps(llm.calls, ensure_ascii=False) and name not in payload.model_dump_json()


def test_a_two_label_result_skips_the_claim_checks_rather_than_guess():
    text = "Engineering in Mumbai has the highest headcount at 120."  # Bengaluru's 150 is higher
    llm = FakeLLM({"narrate": [say(text)]})
    narration, payload, used_fallback = run(llm, GROUPED, "Headcount by department and location?")
    assert not used_fallback and narration.text == text and len(llm.calls) == 1
    assert "Facts you may state" not in payload.messages[-1]["content"]


def test_no_rows_and_one_row_do_not_crash():
    empty = ResultTable(columns=["department", "avg_ctc"], rows=[], display=[], row_count=0)
    narration, _, used_fallback = run(FakeLLM({"narrate": [say("Nothing matched those filters.")]}),
                                      empty, CTC_QUESTION)
    assert not used_fallback and narration.text == "Nothing matched those filters."
    one = ResultTable(columns=["department", "avg_ctc"], rows=[["Support", 1553000.0]],
                      display=[["Support", "₹15.53 L"]], row_count=1)
    text = "Support has the highest average CTC at ₹15.53 L."
    assert run(FakeLLM({"narrate": [say(text)]}), one, CTC_QUESTION)[0].text == text


def test_a_partly_sent_result_states_no_facts_because_the_top_row_may_be_unsent():
    rows = [[f"Team {chr(65 + i)}", 100 - i] for i in range(40)]
    big = ResultTable(columns=["team", "people"], rows=rows, display=[[r[0], str(r[1])] for r in rows],
                      row_count=40)
    llm = FakeLLM({"narrate": [say("Team A is the largest with 100 people.")]})
    _, payload, used_fallback = run(llm, big, "Headcount by team?")
    assert not used_fallback and "Facts you may state" not in payload.messages[-1]["content"]
