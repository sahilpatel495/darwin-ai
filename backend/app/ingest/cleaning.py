"""Cell, column-name and type rules.

Why we infer types ourselves: pandas turns the employee code 000457 into 457 and leaves
"₹1,20,000" as a string. Both are wrong for HR data, and neither tells the user what
happened. Every rule here is one an analyst would recognise from their own spreadsheets,
and every conversion is written into the receipt (`DataHealth`).

The one threshold: a column converts when at least 95% of its non-empty values parse.
The few that do not become empty and are counted; below 95% the column stays text,
because guessing would hide too much.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.contracts import ColumnType

PARSE_THRESHOLD = 0.95
NEAR_MISS_THRESHOLD = 0.80  # "mostly numbers": worth telling the user why it stayed text
MAX_NAME_LENGTH = 60  # real headers are short; a long one is a paragraph, not a name
MAX_EXAMPLE_LENGTH = 40  # matches the cap prompt_context.py puts on category values

# --------------------------------------------------------------------------- cells

NULL_TOKENS = frozenset({"", "-", "--", "na", "n/a", "null", "nil", "none", "#n/a"})


def clean_cell(value: str | None) -> str | None:
    """Trim, collapse inner whitespace, and turn "no value" markers into None.

    Null tokens are missing data, not parse failures: "NA" in a salary column must not
    count against the 95% threshold or show up as an unreadable value.
    """
    if value is None:
        return None
    text = " ".join(value.split())
    if text == value:
        text = value  # keep the one copy already in memory; most cells are already clean
    return None if text.lower() in NULL_TOKENS else text


def is_null(value: str | None) -> bool:
    return clean_cell(value) is None


# --------------------------------------------------------------------------- names

# Words the model cannot write as a bare table or column name. Three sources:
# 1. DuckDB 1.5 keywords of category 'reserved' (SELECT keyword_name, keyword_category FROM
#    duckdb_keywords()), plus "user", which the SQL parser reads as CURRENT_USER;
# 2. category 'type_function': `SELECT left FROM t` is a syntax error too, and "Left" is a
#    real HR header;
# 3. words DuckDB accepts but sqlglot, which the SQL guard parses with, does not.
RESERVED_WORDS = frozenset(
    "all analyse analyze and any array as asc asymmetric both case cast check collate column "
    "constraint create default deferrable desc describe distinct do else end except false "
    "fetch for foreign from group having in initially intersect into lambda lateral leading "
    "limit not null offset on only or order pivot pivot_longer pivot_wider placing primary "
    "qualify references returning select show some summarize symmetric table then to "
    "trailing true union unique unpivot user using variadic when where window with "
    # type_function
    "anti asof at authorization binary by collation columns concurrently cross freeze full "
    "generated glob ilike inner is isnull join left like map natural notnull outer overlaps "
    "positional right semi similar struct tablesample try_cast unpack verbose "
    # sqlglot
    "alter between cube drop force grant if insert install lock revoke rollback rollup "
    "values".split()
)


def snake_case(text: str) -> str:
    """Lowercase ASCII words joined by underscores; "" when nothing usable is left."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    # EmpID -> Emp_ID, so the identifier rule below still recognises it.
    split_camel = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", ascii_text)
    name = re.sub(r"[^a-z0-9]+", "_", split_camel.lower()).strip("_")
    return name[:MAX_NAME_LENGTH].strip("_")


def safe_name(text: str, *, fallback: str, digit_prefix: str, reserved_suffix: str) -> str:
    """A bare SQL identifier: the model must be able to write it without quoting."""
    name = snake_case(text)
    if not name:
        return fallback
    if name[0].isdigit():
        name = digit_prefix + name
    if name in RESERVED_WORDS:
        name += reserved_suffix
    return name


def normalise_names(headers: list[str | None]) -> tuple[list[str], dict[str, str]]:
    """Header cells -> unique column names, plus name -> original text for display.

    Headers in other scripts ("कर्मचारी नाम") have no ASCII form, so they get a positional
    name; the label keeps the original so the UI still shows what the user wrote.
    """
    names: list[str] = []
    labels: dict[str, str] = {}
    for position, header in enumerate(headers, start=1):
        label = " ".join((header or "").split())
        base = safe_name(
            label, fallback=f"column_{position}", digit_prefix="c_", reserved_suffix="_col"
        )
        name, copy = base, 1
        while name in labels:
            copy += 1
            name = f"{base}_{copy}"
        names.append(name)
        labels[name] = label
    return names, labels


def _has_word(name: str, words: frozenset[str]) -> bool:
    """True when a whole word of the column name, or its plural, is in `words`.

    Whole words, not substrings: "net" must not match "network", nor "day" "holiday".
    """
    return any(
        token in words or token.removesuffix("s") in words or token.removesuffix("es") in words
        for token in name.split("_")
    )


# --------------------------------------------------------------------------- amounts

_GROUPED_DIGITS = r"(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3}|\d+)"  # western | Indian | plain
_AMOUNT = re.compile(
    rf"(?P<sign>[-+−])?\s*(?P<currency>₹|rs\.?|inr)?\s*(?P<sign2>[-+−])?\s*"
    rf"(?P<number>{_GROUPED_DIGITS}(?:\.\d+)?|\.\d+)\s*"
    r"(?P<unit>lakhs?|lacs?|lpa|l|crores?|cr)?\.?\s*(?:/-)?",  # LPA: lakhs per annum
    re.IGNORECASE,
)
_UNIT_MULTIPLIER = {"l": 100_000, "c": 10_000_000}  # keyed by the unit's first letter

_MONEY_WORDS = frozenset(
    "salary ctc gross net pay amount bonus deduction revenue price cost "
    "basic hra allowance incentive wage tax".split()
)
_NOT_MONEY_WORDS = frozenset({"center", "centre"})  # a cost centre is a code, not a cost


def _parse_number(text: str) -> tuple[float, str] | None:
    """(value, marker) where marker is "sign" for ₹/Rs/INR, "short" for L/Cr, else "".

    Commas must sit where a thousands separator can (1,234 or 1,20,000). "1,5" is left
    alone, because reading a decimal comma as fifteen would be a silent error.
    """
    # Collapse runs of spaces first. The pattern has several optional parts separated by
    # `\s*`, and on "-" followed by 2,000 spaces the regex engine tried every way to share
    # them out: one hostile header cell cost a minute of CPU.
    text = " ".join(text.split())
    bracketed = text.startswith("(") and text.endswith(")")  # accountants' negative
    match = _AMOUNT.fullmatch(text[1:-1].strip() if bracketed else text)
    if match is None:
        return None
    digits = match["number"].replace(",", "")
    unit = (match["unit"] or "").lower()
    # Decimal, because 1.2 * 100000 is 119999.99999999999 in floating point.
    value = float(Decimal(digits) * _UNIT_MULTIPLIER[unit[0]]) if unit else float(digits)
    if not math.isfinite(value):  # 400 nines: infinity would poison every SUM and the JSON
        return None
    negative = bracketed or any(sign in ("-", "−") for sign in (match["sign"], match["sign2"]))
    marker = "short" if unit else "sign" if match["currency"] else ""
    return (-value if negative else value), marker


def parse_amount(text: str) -> float | None:
    """One amount as a float: "₹1,20,000" -> 120000.0, "1.2L" -> 120000.0, "abc" -> None."""
    parsed = _parse_number(text)
    return parsed[0] if parsed else None


_PERCENT = re.compile(r"([-+−]?\d+(?:\.\d+)?)\s*%")


def parse_percent(text: str) -> float | None:
    """One percentage: "45%" -> 45.0. Stored as 45, not 0.45, because that is what was typed."""
    match = _PERCENT.fullmatch(text.strip())
    return float(match[1].replace("−", "-")) if match else None


_BOOLEANS = {"yes": True, "y": True, "true": True, "no": False, "n": False, "false": False}


def parse_boolean(text: str) -> bool | None:
    return _BOOLEANS.get(text.strip().lower())


# --------------------------------------------------------------------------- dates

_MIDNIGHT = r"(?:[T ]00:00(?::00(?:\.0+)?)?Z?)?"  # a time of 00:00 adds nothing to a date
_NUMERIC_DATE = re.compile(rf"(\d{{1,2}})([/\-.])(\d{{1,2}})\2(\d{{4}}|\d{{2}}){_MIDNIGHT}")
_ISO_DATE = re.compile(rf"(\d{{4}})([-/])(\d{{1,2}})\2(\d{{1,2}}){_MIDNIGHT}")
_NAMED_DATE = re.compile(r"(\d{1,2})([\s\-/])([A-Za-z]{3,9})\.?,?[\s\-/](\d{4}|\d{2})")
# A two-digit year needs a dash, slash or apostrophe (Apr-25, Apr'25). After a space it is
# just as likely a day: a birthday list's "Mar 31" must not become 1 March 1931.
_MONTH_YEAR = re.compile(r"([A-Za-z]{3,9})\.?(?:[\s\-/,]+(\d{4})|[\-/'’](\d{2}))")
_EXCEL_SERIAL = re.compile(r"(\d{5})(?:\.0+)?")

_MONTH_NAMES = (
    "january february march april may june july august september october november december".split()
)
_EXCEL_EPOCH = date(1899, 12, 30)
# Dates outside this window are placeholders ("31/12/9999" = no end date, the norm in SAP
# and SuccessFactors exports) or typos. They read as empty, which is what the user means,
# and that keeps every real value inside the range datetime64[ns] can hold.
_MIN_YEAR, _MAX_YEAR = 1900, 2100
_DATE_WORDS = frozenset("date dob doj joining exit month period day".split())
EXCEL_SERIAL_LABEL = "Excel date number"


def infer_dayfirst(values: Iterable[str]) -> tuple[bool, bool]:
    """(day_first, undecidable) from the evidence in dates like 03/04/2025.

    A first part above 12 can only be a day; a second part above 12 can only mean the
    month came first. With no such evidence we default to day-first, the Indian norm,
    and say so, because 03/04 silently read the wrong way moves people between quarters.
    """
    day_votes = month_votes = seen = 0
    for value in values:
        match = _NUMERIC_DATE.fullmatch(value.strip())
        if match is None:
            continue
        seen += 1
        first, second = int(match[1]), int(match[3])
        if first > 12 >= second:
            day_votes += 1
        elif second > 12 >= first:
            month_votes += 1
    if month_votes > day_votes:
        return False, False
    return True, seen > 0 and day_votes == 0


def parse_date(text: str, dayfirst: bool = True) -> date | None:
    parsed = _parse_date(text, dayfirst)
    return parsed[0] if parsed else None


def _parse_date(text: str, dayfirst: bool) -> tuple[date | None, str] | None:
    """(date, format label), or None when the text is not a date at all.

    The date is None for a placeholder such as 31/12/9999: well formed, but not a real day.
    The label feeds the receipt line "Dates read as DD/MM/YYYY"."""
    text = text.strip()
    if match := _ISO_DATE.fullmatch(text):
        year, sep, month, day = match.groups()
        return _build(int(year), int(month), int(day), f"YYYY{sep}MM{sep}DD")
    if match := _NUMERIC_DATE.fullmatch(text):
        first, sep, second, year = match.groups()
        day, month = (first, second) if dayfirst else (second, first)
        order = ("DD", "MM") if dayfirst else ("MM", "DD")
        return _build(_year(year), int(month), int(day), sep.join((*order, "Y" * len(year))))
    if match := _NAMED_DATE.fullmatch(text):
        day, sep, month_name, year = match.groups()
        return _build(
            _year(year), _month(month_name), int(day), f"DD{sep}MMM{sep}{'Y' * len(year)}"
        )
    if match := _MONTH_YEAR.fullmatch(text):
        month_name, long_year, short_year = match.groups()
        year = long_year or short_year
        return _build(_year(year), _month(month_name), 1, f"MMM-{'Y' * len(year)}")
    return None


def _parse_excel_serial(text: str) -> tuple[date | None, str] | None:
    """Excel stores dates as days since 1899-12-30; unformatted cells export as "45658"."""
    match = _EXCEL_SERIAL.fullmatch(text.strip())
    if match is None:
        return None
    day = _EXCEL_EPOCH + timedelta(days=int(match[1]))
    return (day, EXCEL_SERIAL_LABEL) if 1950 <= day.year <= _MAX_YEAR else None


def _build(year: int, month: int, day: int, label: str) -> tuple[date | None, str] | None:
    try:
        value = date(year, month, day)
    except ValueError:  # 31/02/2025, or a month name that is not a month
        return None
    return (value if _MIN_YEAR <= year <= _MAX_YEAR else None), label


def _year(text: str) -> int:
    """Two-digit years follow Excel's rule (00-29 -> 2000s, 30-99 -> 1900s), so a date
    reads the same here as it does in the analyst's spreadsheet."""
    year = int(text)
    if len(text) == 4:
        return year
    return 2000 + year if year < 30 else 1900 + year


def _month(name: str) -> int:
    """1-12 for "Apr", "April" or "Sept"; 0 for anything that is not a month name."""
    word = name.lower()
    return next((i for i, full in enumerate(_MONTH_NAMES, start=1) if full.startswith(word)), 0)


# --------------------------------------------------------------------------- columns

_IDENTIFIER_NAME = re.compile(r"(^|_)(id|code|no|num|number)$")


@dataclass
class InferredColumn:
    """One column after type inference, with everything the receipt needs to say about it."""

    type: ColumnType
    values: list  # converted Python values; None where the cell was empty or unreadable
    detail: str = ""  # receipt sentence; empty for text columns
    unparseable: int = 0
    examples: list[str] = field(default_factory=list)
    preserved_as_text: bool = False  # looks numeric but is a code, kept as text on purpose
    date_labels: Counter[str] = field(default_factory=Counter)
    numeric_date_example: str | None = None  # a value like 03/04/2025, if the column has one
    warning: str | None = None


@dataclass
class _Reading:
    """One attempt to read a whole column as a type. `parsed` maps each distinct text to its
    value, or None on failure. Parsing distinct values keeps large files fast."""

    type: ColumnType
    parsed: dict[str, object]
    detail: str
    near_miss_noun: str = ""  # "numbers" / "dates": set when a near miss is worth a warning
    # Texts that are well formed but mean "no value" (31/12/9999). They become empty and are
    # reported, yet do not count against the threshold: in many exports they are most rows.
    placeholders: set[str] = field(default_factory=set)
    date_labels: Counter[str] = field(default_factory=Counter)


def is_identifier_name(name: str) -> bool:
    return _IDENTIFIER_NAME.search(name) is not None


def infer_column(name: str, label: str, values: list[str | None], dayfirst: bool) -> InferredColumn:
    """Decide a cleaned column's type and convert it.

    Order: codes stay text; then boolean, percent, date, number; else text. The first type
    that at least 95% of non-empty values parse as wins.
    """
    counts = Counter(value for value in values if value is not None)
    if not counts:
        return InferredColumn("text", values)
    if _is_code_column(name, counts):
        return InferredColumn("text", values, preserved_as_text=True)

    total = sum(counts.values())
    warning = None
    for read in (_read_booleans, _read_percents, _read_dates, _read_numbers):
        reading = read(name, counts, dayfirst)
        considered = total - sum(counts[text] for text in reading.placeholders)
        failed = sum(
            n
            for text, n in counts.items()
            if reading.parsed[text] is None and text not in reading.placeholders
        )
        share = (considered - failed) / considered if considered else 0.0
        if share >= PARSE_THRESHOLD:
            return _converted(values, counts, reading)
        if reading.near_miss_noun and share >= NEAR_MISS_THRESHOLD and warning is None:
            warning = (
                f"{display_name(label, name)} looks like a column of {reading.near_miss_noun}, "
                f"but {failed} of {considered} values could not be read that way, so it was kept "
                "as text. Correct those cells and upload the file again to use it in calculations."
            )
    return InferredColumn("text", values, warning=warning)


def _converted(values: list[str | None], counts: Counter[str], reading: _Reading) -> InferredColumn:
    """Everything that did not yield a value becomes empty, and the receipt says how many."""
    failures = [text for text, _ in counts.most_common() if reading.parsed[text] is None]
    return InferredColumn(
        type=reading.type,
        values=[None if value is None else reading.parsed[value] for value in values],
        detail=reading.detail,
        unparseable=sum(counts[text] for text in failures),
        examples=[shorten(text, MAX_EXAMPLE_LENGTH) for text in failures[:3]],
        date_labels=reading.date_labels,
        numeric_date_example=next(
            (t for t in counts if _NUMERIC_DATE.fullmatch(t) and reading.parsed[t] is not None),
            None,
        )
        if reading.type == "date"
        else None,
    )


def _is_code_column(name: str, counts: Counter[str]) -> bool:
    """Columns that look numeric but are labels: as numbers they would lose leading zeros,
    break text-to-text joins, and (for phone, Aadhaar or account numbers) have their
    smallest and largest real values described to the model as a "range"."""
    if is_identifier_name(name):
        return True
    # Original text -> its digits. A leading "+" is allowed because "+919876543210" is a
    # phone number, not a positive integer of 919 billion.
    digits = {
        text: text.removeprefix("+")
        for text in counts
        if text.isascii() and text.removeprefix("+").isdigit()
    }
    if sum(counts[text] for text in digits) < PARSE_THRESHOLD * sum(counts.values()):
        return False
    if any(len(d) > 1 and d[0] == "0" for d in digits.values()):
        return True  # 000457, 0123
    if any(len(d) > 15 for d in digits.values()):
        return True  # too long to survive as a float or a 64-bit integer
    widths = {len(d) for d in digits.values()}
    fixed_width = len(digits) == len(counts) and len(widths) == 1
    return fixed_width and min(widths) >= 9 and not _is_money_name(name)


def _is_money_name(name: str) -> bool:
    return _has_word(name, _MONEY_WORDS) and not _has_word(name, _NOT_MONEY_WORDS)


def _read_booleans(name: str, counts: Counter[str], dayfirst: bool) -> _Reading:
    return _Reading("boolean", {t: parse_boolean(t) for t in counts}, "Read as yes/no values.")


def _read_percents(name: str, counts: Counter[str], dayfirst: bool) -> _Reading:
    detail = "Read as percentages, so 45% is stored as 45."
    return _Reading("percent", {t: parse_percent(t) for t in counts}, detail)


def _read_dates(name: str, counts: Counter[str], dayfirst: bool) -> _Reading:
    """Excel date numbers are only trusted under a date-like header that is not also a
    money header: 45658 under "Date of Joining" is 1 Jan 2025, under "Holiday Pay" it is pay."""
    parsers: list[Callable[[str], tuple[date | None, str] | None]] = [
        lambda t: _parse_date(t, dayfirst)
    ]
    if _has_word(name, _DATE_WORDS) and not _is_money_name(name):
        parsers.append(_parse_excel_serial)
    found = {t: next((hit for parse in parsers if (hit := parse(t))), None) for t in counts}
    labels: Counter[str] = Counter()
    for text, hit in found.items():
        if hit and hit[0] is not None:
            labels[hit[1]] += counts[text]
    dominant = labels.most_common(1)[0][0] if labels else ""
    detail = (
        "Read as dates stored as Excel date numbers."
        if dominant == EXCEL_SERIAL_LABEL
        else f"Read as dates written as {dominant}."
    )
    parsed = {t: hit[0] if hit else None for t, hit in found.items()}
    placeholders = {t for t, hit in found.items() if hit and hit[0] is None}
    return _Reading(
        "date",
        parsed,
        detail,
        near_miss_noun="dates",
        date_labels=labels,
        placeholders=placeholders,
    )


def _read_numbers(name: str, counts: Counter[str], dayfirst: bool) -> _Reading:
    found = {t: _parse_number(t) for t in counts}
    numbers = [hit[0] for hit in found.values() if hit]
    markers = {hit[1] for hit in found.values() if hit}
    column_type: ColumnType
    if "short" in markers:
        column_type = "currency"
        detail = "Read as rupee amounts; short forms such as 1.2L or 3 Cr were written out in full."
    elif "sign" in markers:
        column_type = "currency"
        detail = "Read as rupee amounts, with currency signs and commas removed."
    elif _is_money_name(name):
        column_type, detail = "currency", "Read as amounts of money, because of the column name."
    elif all(n.is_integer() and abs(n) < 2**63 for n in numbers):
        column_type, detail = "integer", "Read as whole numbers."
    else:
        column_type, detail = "decimal", "Read as decimal numbers."
    convert = int if column_type == "integer" else float
    parsed = {t: convert(hit[0]) if hit else None for t, hit in found.items()}
    return _Reading(column_type, parsed, detail, near_miss_noun="numbers")


def display_name(label: str, name: str) -> str:
    """The user's own header in messages, shortened so a pasted paragraph cannot flood one."""
    return shorten(label or name, MAX_NAME_LENGTH)


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
