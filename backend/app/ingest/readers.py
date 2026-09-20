"""Readers: turn an uploaded file into grids of text, inferring nothing.

Why text only: pandas and Excel both "help" by guessing types, which turns the employee
code 000457 into 457 and breaks every join. Here every cell comes back as the text a person
would see, or None, and `cleaning.py` decides types with rules we can explain and report.

Uploads are untrusted. Each limit below exists so a hostile file costs bounded memory and
ends in a plain sentence, never a stack trace.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import logging
import re
import zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path, PureWindowsPath

import openpyxl

from app.config import settings
from app.ingest.errors import IngestError
from app.ingest.types import RawTable

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = (".csv", ".tsv", ".txt")
EXCEL_EXTENSIONS = (".xlsx", ".xlsm")
DELIMITERS = ",;\t|"
SNIFF_CHARS = 65536  # enough lines to see the delimiter, small enough to read twice

# Real HR exports are a few hundred columns at most; Excel itself stops at 1,048,576 rows.
# All three limits are per file, so a workbook cannot multiply them by its number of sheets.
MAX_COLUMNS = 1000
MAX_ROWS = 1_000_000
# Rows x widest row. Every row is padded to the widest, so one 1,000-cell line above
# 100,000 one-cell lines (a 0.2 MB file) used to cost 800 MB. At five bytes a cell, which
# is short for HR data, a 25 MB CSV holds half this many.
MAX_CELLS = 10_000_000
MAX_SHEET_NAME = 31
# A workbook is a zip. A few kilobytes can unpack to gigabytes, so the declared unpacked
# size is checked before anything is opened. Honest 25 MB workbooks unpack to well under this.
MAX_UNZIPPED_BYTES = 500 * 1024 * 1024


def read_raw_tables(path: Path, original_name: str) -> list[RawTable]:
    """Read `path` as the type named by `original_name`'s extension.

    Returns one RawTable per CSV, or per worksheet that has at least one value. The
    extension comes from the original name because the file on disk is a temporary upload.
    """
    # Browsers may send a client-side path; only the last part is a name, and
    # PureWindowsPath splits on both kinds of slash.
    name = PureWindowsPath(original_name).name
    extension = Path(name).suffix.lower()
    if extension == ".xls":
        raise IngestError(
            "Old .xls files are not supported. Open the file in Excel and save it as .xlsx."
        )
    if extension not in TEXT_EXTENSIONS + EXCEL_EXTENSIONS:
        supported = ", ".join(TEXT_EXTENSIONS + EXCEL_EXTENSIONS)
        raise IngestError(
            f"{name} is not a file type Verity can read. Upload one of these instead: {supported}."
        )
    # The API caps uploads while streaming them to disk. Checking again here keeps the
    # guarantee for every other caller, because both readers load the file into memory.
    if path.stat().st_size > settings.max_upload_mb * 1024 * 1024:
        raise IngestError(
            f"{name} is larger than the {settings.max_upload_mb} MB limit. Remove the sheets "
            "or columns you do not need, or split the file, and upload it again."
        )
    if extension in TEXT_EXTENSIONS:
        tables = [_read_text_file(path, name)]
    else:
        tables = _read_workbook(path, name)
    tables = [t for t in tables if _grid_has_value(t.grid)]
    if not tables:
        raise IngestError(f"{name} is empty.")
    return tables


# --------------------------------------------------------------------------- text files


def _read_text_file(path: Path, name: str) -> RawTable:
    """Stream the file through the csv module, trying encodings until one decodes it all.

    Streaming matters: holding the decoded text next to the grid roughly doubled peak
    memory on a 20 MB file, and the hosted demo has 512 MB in total.
    """
    unreadable = IngestError(
        f"{name} could not be read as a table. Open it in Excel, save it again as CSV "
        "and upload the new file."
    )
    for encoding in _candidate_encodings(path):
        try:
            with path.open(encoding=encoding, newline="") as handle:
                sample = handle.read(SNIFF_CHARS)
                if "\x00" in sample:  # zips, images and BOM-less UTF-16 all have NULs early
                    raise IngestError(
                        f"{name} does not look like a text file. If it is an Excel workbook, "
                        "save it as .xlsx and upload that; otherwise export it again as CSV."
                    )
                handle.seek(0)
                # skipinitialspace: `1, "Rao, Asha"` must still honour the quotes.
                reader = csv.reader(
                    handle, delimiter=sniff_delimiter(sample), skipinitialspace=True
                )
                rows = _bounded(reader, name, MAX_ROWS, MAX_CELLS)
        except UnicodeDecodeError:
            continue  # wrong guess, possibly found late in the file: start again
        except csv.Error:  # for example a single cell larger than the csv module allows
            raise unreadable from None
        return RawTable(name_hint=Path(name).stem, source_file=name, sheet=None, grid=_pad(rows))
    raise unreadable


def _candidate_encodings(path: Path) -> tuple[str, ...]:
    """UTF-8 first, then cp1252, which is what Excel on Windows writes for "CSV"; latin-1
    maps every byte, so one odd symbol never blocks a file. A UTF-16 byte-order mark
    means Excel's "Unicode Text" export."""
    with path.open("rb") as handle:
        if handle.read(2) in (b"\xff\xfe", b"\xfe\xff"):
            return ("utf-16",)
    return ("utf-8-sig", "cp1252", "latin-1")


def sniff_delimiter(text: str) -> str:
    """Pick the delimiter that splits the most rows into the same number of cells.

    Why not csv.Sniffer: it guesses from character frequency and is thrown by title lines
    and by the commas inside Indian amounts ("1,20,000"). Counting consistent rows is not.
    On a tie the rarer character wins: a tab on every line is a delimiter, while a comma on
    every line may just be "Rao, Asha".
    """
    sample = text[:SNIFF_CHARS]
    best, best_score = ",", (0, False, 0)
    for delimiter in DELIMITERS:
        try:
            rows = list(csv.reader(io.StringIO(sample, newline=""), delimiter=delimiter))[:50]
        except csv.Error:
            continue
        widths = Counter(len(row) for row in rows if len(row) > 1)
        if not widths:
            continue
        width, frequency = widths.most_common(1)[0]
        score = (frequency, delimiter != ",", width)
        if score > best_score:
            best, best_score = delimiter, score
    return best


# --------------------------------------------------------------------------- Excel


def _read_workbook(path: Path, name: str) -> list[RawTable]:
    """Every worksheet becomes a grid. Any failure inside the parser is reported as one
    sentence: openpyxl raises many different errors on damaged or protected files, and
    none of them should reach the user."""
    try:
        with zipfile.ZipFile(path) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_UNZIPPED_BYTES:
                raise IngestError(
                    f"{name} is too large to open safely once unpacked. Split it into "
                    "smaller workbooks, or save the sheet you need as CSV."
                )
        # A file handle, not the path: openpyxl rejects any *path* that does not end in an
        # Excel extension, and uploads are stored under temporary names. read_only streams
        # rows; data_only gives formula results; keep_links=False skips parsing references
        # to other workbooks, which we never follow.
        with path.open("rb") as handle:
            workbook = openpyxl.load_workbook(
                handle, read_only=True, data_only=True, keep_links=False
            )
            try:
                sheets = []
                # One budget for the whole file: each sheet may use what the others left,
                # so fifty sheets cannot cost fifty times the limit.
                rows_left, cells_left = MAX_ROWS, MAX_CELLS
                for ws in workbook.worksheets:
                    grid = _pad(_bounded(_sheet_rows(ws), name, rows_left, cells_left))
                    rows_left -= len(grid)
                    cells_left -= sum(map(len, grid))
                    # Excel caps a sheet name at 31 characters; only a crafted file has
                    # more, and the name is shown to the user and to the model.
                    sheets.append((ws.title[:MAX_SHEET_NAME], grid))
            finally:
                workbook.close()
    except IngestError:
        raise
    except Exception as error:  # noqa: BLE001 - fail closed on whatever the parser throws
        # The type only: parser messages can quote cell text or server paths. Without this
        # line a bug on our side is indistinguishable from a damaged file.
        logger.warning("Workbook %r was rejected: %s", name, type(error).__name__)
        raise IngestError(
            f"{name} could not be opened as an Excel workbook. It may be password-protected "
            "or damaged. Open it in Excel, save a fresh copy as .xlsx and upload that."
        ) from None

    stem = Path(name).stem
    filled = [(title, grid) for title, grid in sheets if _grid_has_value(grid)]
    return [
        RawTable(
            name_hint=stem if len(filled) == 1 else f"{stem}_{title}",
            source_file=name,
            sheet=title,
            grid=grid,
        )
        for title, grid in filled
    ]


def _sheet_rows(sheet):
    # A workbook can declare any size it likes (A1:XFD1048576 is common from HR tools).
    # Resetting makes openpyxl yield the rows that are really there.
    sheet.reset_dimensions()
    for row in sheet.iter_rows():
        yield [_cell_text(cell.value, cell.number_format) for cell in row]


_QUOTED_LITERAL = re.compile(r'"[^"]*"|\\.')  # text an Excel number format shows as-is


def _cell_text(value: object, number_format: str | None) -> str | None:
    """Render a cell the way its owner sees it in Excel, without losing information."""
    if value is None:
        return None
    if isinstance(value, bool):  # before int: bool is an int in Python
        return str(value)
    if isinstance(value, dt.datetime):
        # A pure date reads as a date. A real time of day is kept, so it is never lost.
        if value.time() == dt.time(0):
            return value.date().isoformat()
        return value.isoformat(sep=" ")
    if isinstance(value, (int, float)):
        # Excel stores 45% as 0.45; the analyst sees, and asks about, 45. A quoted or
        # escaped sign (0.00"%") is decoration on a cell that really holds 45: no scaling.
        if number_format and "%" in _QUOTED_LITERAL.sub("", number_format):
            return _number_text(round(value * 100, 10)) + "%"
        return _number_text(value)
    return str(value)  # text, dates without a time, times and durations


def _number_text(value: float) -> str:
    """Whole-number floats print as "120000", not "120000.0", so codes and counts stay clean.
    Small ones print as "0.00001", not repr's "1e-05", which no analyst ever typed."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return format(Decimal(repr(value)), "f")


# --------------------------------------------------------------------------- shared


def _grid_has_value(grid: list[list[str | None]]) -> bool:
    return any(cell is not None and cell.strip() != "" for row in grid for cell in row)


def _bounded(rows, name: str, rows_left: int, cells_left: int) -> list[list[str | None]]:
    """Materialise rows, stopping at the limits before memory is spent on padding.

    `rows_left` and `cells_left` are what remains of the file's budget: a CSV passes the
    full limits, a workbook passes what earlier sheets have not used.
    """
    out: list[list[str | None]] = []
    width = 0
    for row in rows:
        if len(row) > MAX_COLUMNS:
            raise IngestError(
                f"{name} has more than {MAX_COLUMNS:,} columns, which Verity cannot analyse. "
                "Keep only the columns you need and upload it again."
            )
        if len(out) >= rows_left:
            raise IngestError(
                f"{name} has more than {MAX_ROWS:,} rows, which Verity cannot analyse. "
                "Split it into smaller files and upload those. If your data is shorter than "
                "that, delete the empty rows below it, save the file and upload it again."
            )
        width = max(width, len(row))
        if width * (len(out) + 1) > cells_left:
            raise IngestError(
                f"{name} has more than {MAX_CELLS:,} cells (rows times columns), which Verity "
                "cannot analyse. Keep only the rows and columns you need and upload it again."
            )
        out.append([cell if cell != "" else None for cell in row])
    return out


def _pad(rows: list[list[str | None]]) -> list[list[str | None]]:
    """Give every row the same width; exports often stop a line at its last value."""
    width = max((len(row) for row in rows), default=0)
    return [row if len(row) == width else row + [None] * (width - len(row)) for row in rows]
