"""PII detection, role detection and the table profile (including the duplicates policy)."""

from __future__ import annotations

import pandas as pd
import pytest
from app.contracts import Coercion, DataHealth
from app.profile import profile_table
from app.profile.pii import detect_pii
from app.profile.roles import ROLE_SYNONYMS, ROLES, detect_role

from tests.data_engine.helpers import ingested

# --------------------------------------------------------------------------
# PII
# --------------------------------------------------------------------------


def _text(values: list) -> pd.Series:
    return pd.Series(values, dtype="str")


@pytest.mark.parametrize(
    ("header", "values", "expected"),
    [
        ("contact", ["asha.rao@example.com", "v.shah@corp.co.in", "meera@x.org"], "email"),
        ("contact", ["9876543210", "+91 98765 43210", "+91-9876543210"], "phone"),
        ("tax_ref", ["ABCDE1234F", "PQRST5678K", "LMNOP4321Z"], "pan"),
        ("branch_ref", ["HDFC0001234", "SBIN0KLMN12", "ICIC0000001"], "ifsc"),
        ("national_ref", ["1234 5678 9012", "234567890123", "9999 8888 7777"], "aadhaar"),
        ("UAN", ["100123456789", "100987654321", "100555555555"], "uan"),
        ("A/C No", ["12345678901234", "987654321", "123456789012345678"], "bank_account"),
        ("bank_account_number", ["12345678901234", "50100234567891", "30987654321000"], "bank_account"),
    ],
)
def test_value_patterns_flag_the_right_kind(header, values, expected):
    assert detect_pii(header.lower().replace(" ", "_"), header, "text", _text(values)) == expected


def test_phone_numbers_stored_as_integers_are_still_caught():
    series = pd.Series([9876543210, 9123456780, None], dtype="Int64")
    assert detect_pii("reach_on", "Reach On", "integer", series) == "phone"


@pytest.mark.parametrize(("values", "expected"), [
    (["abcde1234f", "Pqrst5678k", "LMNOP4321Z"], "pan"),  # exports are not always upper case
    (["hdfc0001234", "sbin0klmn12"], "ifsc"),
    (["asha+hr@example.com", "v.shah+payroll@corp.co.in"], "email"),
    (["Asha Rao <asha@example.com>", "mailto:v.shah@corp.co.in", "a@x.org; b@x.org"], "email"),  # an email inside a longer cell
])
def test_pii_that_hides_behind_case_or_extra_text_is_still_caught(values, expected):
    assert detect_pii("ref", "Ref", "text", _text(values)) == expected


def test_personal_numbers_that_ingest_read_as_amounts_are_still_caught():
    """Ingest types a digits-only "Salary Account" column as currency because of the word
    salary. Its min and max would otherwise reach the model as two real account numbers."""
    accounts = pd.Series([50100234567891.0, 30987654321000.0, 123456789012345678.0], dtype="float64")
    assert detect_pii("salary_account", "Salary Account", "currency", accounts) == "bank_account"
    mobiles = pd.Series([9876543210.0, 9123456780.0, None], dtype="float64")
    assert detect_pii("net_banking_mobile", "Net Banking Mobile", "currency", mobiles) == "phone"
    assert detect_pii("reach_on", "Reach On", "decimal", mobiles) == "phone"


def test_a_number_column_named_after_pii_is_flagged_only_when_its_numbers_are_long_enough():
    allowance = pd.Series([1500, 2000, 1500], dtype="Int64")
    assert detect_pii("mobile_allowance", "Mobile Allowance", "integer", allowance) is None  # an amount
    assert detect_pii("phone_reimbursement", "Phone Reimbursement", "currency", allowance.astype("float64")) is None
    landlines = pd.Series([23456789, 26543210], dtype="Int64")  # not mobiles, but the header says phone
    assert detect_pii("office_phone", "Office Phone", "integer", landlines) == "phone"


def test_long_digit_strings_are_not_a_bank_account_without_the_header():
    assert detect_pii("invoice_ref", "Invoice Ref", "text", _text(["12345678901234", "50100234567891"])) is None


def test_a_column_below_sixty_percent_is_not_flagged():
    values = ["asha@example.com", "see notes", "call later", "n/a today", "pending"]
    assert detect_pii("remarks", "Remarks", "text", _text(values)) is None
    assert detect_pii("remarks", "Remarks", "text", _text(values[:1] * 3 + values[1:3])) == "email"  # 3 of 5


def test_a_header_that_names_pii_is_flagged_even_when_the_values_are_messy():
    """Fail closed: a column called Email with half its values mistyped still holds real emails."""
    values = ["asha@example.com", "vikram at example dot com", "none given"]
    assert detect_pii("email", "Email", "text", _text(values)) == "email"
    assert detect_pii("pan_no", "PAN No", "text", _text(["ABCDE1234F", "applied for", "pending"])) == "pan"
    assert detect_pii("company", "Company", "text", _text(["Acme", "Globex"])) is None  # "pan" inside a word


@pytest.mark.parametrize("header", ["Name", "Employee Name", "full_name", "Manager Name", "Reporting Manager",
                                    "Team Lead Name", "Project Manager Name", "Father's Name", "Staff", "Reviewer"])
def test_name_headers_are_person_names(header):
    name = header.lower().replace(" ", "_")
    assert detect_pii(name, header, "text", _text(["Asha Rao", "Vikram Shah"])) == "person_name"


@pytest.mark.parametrize("header", ["Department Name", "file_name", "Product Name", "Company Name",
                                    "sheet_name", "table_name", "City Name", "Project Name", "Team Name"])
def test_names_of_things_are_not_person_names(header):
    name = header.lower().replace(" ", "_")
    assert detect_pii(name, header, "text", _text(["Alpha", "Beta"])) is None


def test_a_name_header_on_a_number_column_is_not_a_person_name():
    assert detect_pii("name", "Name", "integer", pd.Series([1, 2], dtype="Int64")) is None


def test_an_empty_column_is_not_pii():
    assert detect_pii("notes", "Notes", "text", _text([None, None])) is None


# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "ctype", "role"),
    [
        ("DOJ", "date", "join_date"), ("Date of Joining", "date", "join_date"),
        ("joining_date", "date", "join_date"), ("hire_date", "date", "join_date"),
        ("LWD", "date", "exit_date"), ("last_working_day", "date", "exit_date"),
        ("exit_date", "date", "exit_date"), ("date_of_exit", "date", "exit_date"),
        ("separation_date", "date", "exit_date"), ("relieving_date", "date", "exit_date"),
        ("Emp Code", "text", "employee_id"), ("Employee ID", "text", "employee_id"),
        ("emp_id", "text", "employee_id"), ("employee_code", "text", "employee_id"),
        ("emp_no", "text", "employee_id"),
        ("manager_id", "text", "manager_id"), ("reporting_manager_code", "text", "manager_id"),
        ("CTC", "currency", "ctc"), ("annual_ctc", "currency", "ctc"), ("cost_to_company", "decimal", "ctc"),
        ("gross", "currency", "gross"), ("gross_pay", "currency", "gross"), ("gross_salary", "integer", "gross"),
        ("Gross (₹)", "currency", "gross"),
        ("net", "currency", "net"), ("net_pay", "currency", "net"), ("take_home", "currency", "net"),
        ("dept", "text", "department"), ("Department", "text", "department"),
        ("LOP Days", "integer", "lop_days"), ("Pay Month", "date", "pay_month"),
        ("month", "date", "date"), ("Rating", "integer", "rating"), ("Rating", "text", "rating"),
    ],
)
def test_headers_map_to_roles(label, ctype, role):
    from app.profile.roles import normalise_header

    assert detect_role(normalise_header(label), label, ctype) == role


def test_the_original_label_is_used_when_the_normalised_name_was_changed():
    """Ingest may rename a duplicate header to gross_2; the label still says what it is."""
    assert detect_role("column_4", "Date of Joining", "date") == "join_date"


@pytest.mark.parametrize(("label", "ctype"), [("DOJ", "text"), ("exit_date", "text"), ("CTC", "text"),
                                             ("gross", "date"), ("department", "integer"), ("notes", "text")])
def test_a_role_needs_the_right_type(label, ctype):
    assert detect_role(label.lower(), label, ctype) is None


def test_every_role_is_reachable_and_no_header_means_two_things():
    assert set(ROLE_SYNONYMS) == set(ROLES)
    for role in ROLES:
        assert role in ROLE_SYNONYMS[role], f"{role} should be its own synonym"
    every = [s for synonyms in ROLE_SYNONYMS.values() for s in synonyms]
    assert len(every) == len(set(every)), sorted({s for s in every if every.count(s) > 1})


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------


def _employees(**overrides):
    columns = {
        "emp_id": ("text", ["000457", "000458", "000459", "000460"]),
        "name": ("text", ["Asha Rao", "Vikram Shah", "Meera Iyer", "Zebulon Quartermaine"]),
        "department": ("text", ["Sales", "Engineering", "Sales", None]),
        "date_of_joining": ("date", ["2019-04-01", "2020-07-15", "2018-01-10", "2024-01-08"]),
        "ctc": ("currency", [2400000.0, 1800000.5, None, 900000.0]),
        "is_active": ("boolean", [True, False, True, True]),
        "phone": ("integer", [9876543210, 9123456780, 9988776655, 9000000001]),
    }
    columns.update(overrides)
    return ingested("employees", columns, labels={"emp_id": "Emp ID", "ctc": "CTC"})


def _column(profile, name):
    return next(c for c in profile.columns if c.name == name)


def test_profile_describes_each_column():
    df, profile = profile_table(_employees())
    assert profile.name == "employees" and profile.source_file == "employees.csv"
    assert profile.row_count == len(df) == 4 and not profile.is_view

    emp_id = _column(profile, "emp_id")
    assert emp_id.label == "Emp ID" and emp_id.role == "employee_id"
    assert emp_id.is_identifier and emp_id.is_unique and emp_id.distinct_count == 4
    assert emp_id.values == ["000457", "000458", "000459", "000460"]  # leading zeros survive
    assert emp_id.min is None and emp_id.max is None  # text has no range

    department = _column(profile, "department")
    assert department.values == ["Engineering", "Sales"] and department.role == "department"
    assert department.null_fraction == 0.25 and not department.is_unique and department.distinct_count == 2

    joined = _column(profile, "date_of_joining")
    assert (joined.min, joined.max, joined.values) == ("2018-01-10", "2024-01-08", None)
    ctc = _column(profile, "ctc")
    assert (ctc.min, ctc.max, ctc.values) == ("900000", "2400000", None)
    assert not ctc.is_unique  # it has a null
    assert _column(profile, "is_active").values == ["false", "true"]


def test_pii_columns_expose_no_values_and_no_range():
    _, profile = profile_table(_employees())
    name, phone = _column(profile, "name"), _column(profile, "phone")
    assert (name.pii, name.values, name.min) == ("person_name", None, None)
    assert (phone.pii, phone.values, phone.min, phone.max) == ("phone", None, None, None)  # a range is two real numbers
    assert profile.health.pii_columns == ["name", "phone"]


def test_a_date_of_birth_has_no_range():
    """The earliest date of birth in a file is one employee's date of birth."""
    _, profile = profile_table(_employees(dob=("date", ["1990-05-01", "1985-11-23", "1979-02-14", None])))
    dob = _column(profile, "dob")
    assert (dob.role, dob.min, dob.max) == ("birth_date", None, None)


def test_values_are_listed_only_for_thirty_or_fewer():
    many = ingested("t", {"city": ("text", [f"City {i}" for i in range(31)]),
                          "zone": ("text", [f"Zone {i % 30}" for i in range(31)])})
    _, profile = profile_table(many)
    assert _column(profile, "city").values is None
    assert len(_column(profile, "zone").values) == 30


def test_identifier_by_header_pattern_even_without_a_role():
    table = ingested("orders", {"order_no": ("text", ["A1", "A2"]), "voucher_code": ("text", ["X", "X"]),
                                "units": ("integer", [1, 2])})
    _, profile = profile_table(table)
    assert _column(profile, "order_no").is_identifier and _column(profile, "voucher_code").is_identifier
    assert not _column(profile, "units").is_identifier


def test_exact_duplicates_are_removed_when_the_table_has_an_identifier():
    table = ingested("payroll", {"emp_code": ("text", ["E1", "E2", "E2", "E3"]),
                                 "gross": ("currency", [100.0, 200.0, 200.0, 300.0])})
    df, profile = profile_table(table)
    assert len(df) == 3 and profile.row_count == 3 and list(df.index) == [0, 1, 2]
    assert profile.health.duplicate_rows == 1 and profile.health.duplicates_removed
    assert profile.health.rows == 3  # the receipt agrees with the table the user queries
    assert table.health.duplicates_removed is False  # the input receipt is not mutated


def test_exact_duplicates_are_kept_when_there_is_no_identifier():
    table = ingested("sales", {"region": ("text", ["North", "North", "South"]),
                               "revenue": ("currency", [100.0, 100.0, 300.0])})
    df, profile = profile_table(table)
    assert len(df) == 3 and profile.row_count == 3
    assert profile.health.duplicate_rows == 1 and not profile.health.duplicates_removed


def test_unreadable_examples_from_pii_columns_are_not_kept_in_the_receipt():
    health = DataHealth(rows=4, columns=7, coercions=[
        Coercion(column="phone", to_type="integer", detail="Read as whole numbers", unparseable=1, examples=["98765-43210 (home)"]),
        Coercion(column="ctc", to_type="currency", detail="Parsed ₹ amounts", unparseable=1, examples=["TBD"]),
    ])
    table = _employees()
    table.health = health
    _, profile = profile_table(table)
    examples = {c.column: c.examples for c in profile.health.coercions}
    assert examples == {"phone": [], "ctc": ["TBD"]}


def test_an_empty_table_profiles_without_error():
    table = ingested("empty", {"emp_id": ("text", []), "ctc": ("currency", [])})
    _, profile = profile_table(table)
    assert profile.row_count == 0
    assert all(c.null_fraction == 0.0 and not c.is_unique and c.min is None for c in profile.columns)
