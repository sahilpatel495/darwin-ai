"""Decide which columns hold personal data, so their values never reach a model.

Why both values and headers: values catch a column nobody labelled ("Contact" full of
emails); headers catch a labelled column whose values are too messy to match ("Email" with
half the cells mistyped still holds real emails). Either signal is enough. A false alarm
only hides a column's values from the model; a miss leaks them, so ties go to "PII".
The one exception is a number column: "Mobile Allowance" is pay, so there the header counts
only when the numbers are long enough to be phone or ID numbers.

Not covered (no PiiKind for them in the contract): postal addresses and dates of birth.
Profiling hides the range of a date-of-birth column, which is the only place one could leak.
"""

from __future__ import annotations

import re

import pandas as pd

from app.contracts import ColumnType, PiiKind
from app.profile.roles import normalise_header

SAMPLE_SIZE = 500
MATCH_THRESHOLD = 0.6  # share of sampled values that must look like the pattern

_SEPARATORS = re.compile(r"[\s\-()]")
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(\.[\w\-]+)+")  # anywhere in the cell: "Asha <asha@x.com>" holds one too
_PHONE = re.compile(r"^(\+?91|0)?[6-9]\d{9}$")  # Indian mobile, separators removed first
_PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$", re.IGNORECASE)  # exports are not always upper case
_IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$", re.IGNORECASE)
_TWELVE_DIGITS = re.compile(r"^\d{12}$")  # Aadhaar and UAN look the same; the header decides
_ACCOUNT_DIGITS = re.compile(r"^\d{9,18}$")
_ACCOUNT_HEADER = re.compile(r"account|a/c|acct")
_LONG_NUMBER = re.compile(r"^\d{8,}$")  # long enough to be a phone or an ID; no allowance is

# Checked in this order. A "91..." mobile is also twelve digits, so phone comes before Aadhaar.
_VALUE_PATTERNS: tuple[tuple[PiiKind, re.Pattern[str], bool], ...] = (
    ("email", _EMAIL, False),
    ("phone", _PHONE, True),
    ("pan", _PAN, False),
    ("ifsc", _IFSC, False),
    ("aadhaar", _TWELVE_DIGITS, True),
)

# A header word that names the kind outright. Whole words only: "company" is not a PAN.
_HEADER_WORDS: dict[str, PiiKind] = {
    "email": "email", "mail": "email", "phone": "phone", "mobile": "phone", "whatsapp": "phone",
    "pan": "pan", "ifsc": "ifsc", "aadhaar": "aadhaar", "aadhar": "aadhaar", "adhaar": "aadhaar",
    "uan": "uan",
}

# "<thing> name" is the name of a thing, not of a person.
_NOT_A_PERSON = {
    "department", "dept", "file", "product", "company", "sheet", "table", "city", "project", "team",
    "location", "branch", "bank", "designation", "grade", "role", "division", "unit", "region",
    "state", "country", "category", "item", "brand", "course", "skill", "shift", "holiday", "leave",
    "policy", "plan",
}
# Headers that hold a person's name without saying "name".
_PERSON_HEADERS = {"employee", "staff", "manager", "reporting_manager", "supervisor", "reports_to",
                   "team_lead", "hrbp", "hr_partner", "reviewer", "appraiser", "approver", "approved_by",
                   "interviewer", "recruiter", "candidate", "nominee", "father", "mother", "spouse",
                   "emergency_contact"}


def _sample(series: pd.Series) -> list[str]:
    """Up to SAMPLE_SIZE non-null values spread evenly over the column, as text. Spread, not
    the first rows, so a block of junk at the top cannot hide what the rest contains."""
    values = series.dropna()
    step = max(1, len(values) // SAMPLE_SIZE)
    return [_as_text(v) for v in values.iloc[::step][:SAMPLE_SIZE]]


def _as_text(value: object) -> str:
    """A cell as its digits or text. An account number that ingest read as an amount is a
    float, and str() of a large float is '5.01e+13', which no pattern would recognise."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return re.sub(r"\.0$", "", str(value)).strip()


def _share(values: list[str], pattern: re.Pattern[str], strip_separators: bool) -> float:
    hits = sum(bool(pattern.search(_SEPARATORS.sub("", v) if strip_separators else v)) for v in values)
    return hits / len(values)


def _is_person_header(header: str) -> bool:
    """'manager_name' and 'team_lead_name' are people, 'department_name' is a thing. Only the
    word right before "name" decides: an earlier word ("team" in "team lead name") says whose
    name it is, not what kind of thing is named."""
    if header in _PERSON_HEADERS:
        return True
    if not header.endswith("name"):
        return False
    named_thing = header.removesuffix("name").rstrip("_").split("_")[-1]  # "" for a bare "name"
    return named_thing not in _NOT_A_PERSON


def detect_pii(name: str, label: str, ctype: ColumnType, series: pd.Series) -> PiiKind | None:
    """The kind of personal data in a column, or None. `name` is the normalised column name,
    `label` the original header text."""
    # Amounts are checked too: ingest reads a "Salary Account" column of digits as currency,
    # and its min and max would then reach the model as two real account numbers.
    if ctype in ("date", "boolean", "percent"):
        return None
    # Ingest may have renamed an unusable header to column_3; the label still says "Email".
    headers = {normalise_header(name), normalise_header(label)} - {""}
    words = {word for header in headers for word in header.split("_")}
    values = _sample(series)

    if values:
        is_account_header = _ACCOUNT_HEADER.search(" ".join([*headers, label.lower()]))
        if is_account_header and _share(values, _ACCOUNT_DIGITS, True) >= MATCH_THRESHOLD:
            return "bank_account"
        for kind, pattern, strip_separators in _VALUE_PATTERNS:
            if _share(values, pattern, strip_separators) >= MATCH_THRESHOLD:
                return "uan" if kind == "aadhaar" and "uan" in words else kind

    named = next((kind for word, kind in _HEADER_WORDS.items() if word in words), None)
    if ctype != "text":
        # "Mobile Allowance" is an amount, not a phone number. A number column named after a
        # kind is that kind only when its numbers are long enough to be one.
        is_long = bool(values) and _share(values, _LONG_NUMBER, True) >= MATCH_THRESHOLD
        return named if is_long else None
    if named:
        return named
    return "person_name" if any(_is_person_header(header) for header in headers) else None
