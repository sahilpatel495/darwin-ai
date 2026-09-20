"""Ingest: turn a messy CSV/Excel upload into clean typed tables plus a receipt.

Pipeline, one step per module so each can be explained and tested alone:
  readers.py   file -> grids of text (nothing inferred, hostile files refused)
  header.py    which row is the header, which trailing rows are totals
  cleaning.py  cell, column-name and type rules
  this file    runs them in order and writes the receipt (`DataHealth`)

The receipt is the point. An analyst will only put a number in front of their CHRO if
they can see what was done to their file: what was skipped, converted or left empty.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from app.contracts import Coercion, DataHealth
from app.ingest.cleaning import (
    InferredColumn,
    clean_cell,
    display_name,
    infer_column,
    infer_dayfirst,
    is_null,
    normalise_names,
    safe_name,
    shorten,
)
from app.ingest.errors import IngestError
from app.ingest.header import (
    count_inner_totals,
    detect_header_row,
    drop_empty_columns,
    drop_footer_totals,
)
from app.ingest.readers import read_raw_tables
from app.ingest.types import IngestedTable, RawTable

__all__ = ["IngestError", "ingest_file"]

# The hand-off convention documented on IngestedTable.
_DTYPES = {
    "integer": "Int64",
    "decimal": "float64",
    "currency": "float64",
    "percent": "float64",
    "date": "datetime64[ns]",
    "boolean": "boolean",
    "text": "str",
}
NULL_HOTSPOT_THRESHOLD = 0.05
MAX_NULL_HOTSPOTS = 5


def ingest_file(path: Path, original_name: str, taken_table_names: set[str]) -> list[IngestedTable]:
    """Read one upload and return one IngestedTable per CSV or non-empty Excel sheet.

    Reads every cell as text first and infers types itself so IDs like "000457" survive.
    Supported: .csv .tsv .txt .xlsx .xlsm. Anything else, an empty file, or a header-only
    file raises IngestError with a sentence the user can act on.

    New table names are added to `taken_table_names`, so a caller ingesting several files
    in a loop can pass the same set and two files called employees never share a name.

    A sheet with no data rows (a cover or notes sheet) is skipped with a warning rather
    than failing the whole workbook; the error is raised only when nothing usable is left.
    """
    raw_tables = read_raw_tables(path, original_name)
    tables: list[IngestedTable] = []
    skipped_sheets: list[str] = []
    for raw in raw_tables:
        table_name = _unique_table_name(raw.name_hint, taken_table_names)
        table = _build_table(raw, table_name)
        if table is None:
            skipped_sheets.append(raw.sheet or raw.source_file)
            continue
        taken_table_names.add(table_name)
        tables.append(table)
    if not tables:
        raise IngestError(f"{raw_tables[0].source_file} has column headers but no data rows.")
    for table in tables:
        table.health.warnings += [
            f"The sheet “{shorten(sheet, 60)}” has no data rows, so it was skipped."
            for sheet in skipped_sheets
        ]
    return tables


def _unique_table_name(hint: str, taken: set[str]) -> str:
    base = safe_name(hint, fallback="data", digit_prefix="t_", reserved_suffix="_data")
    name, copy = base, 1
    while name in taken:
        copy += 1
        name = f"{base}_{copy}"
    return name


def _build_table(raw: RawTable, table_name: str) -> IngestedTable | None:
    """Clean one grid. Returns None when there is a header but nothing under it.

    Consumes `raw.grid` (leaves it empty) so a large upload is not held in memory twice."""
    grid = drop_empty_columns(raw.grid)
    header_index = detect_header_row(grid)
    body = [row for row in grid[header_index + 1 :] if not all(is_null(cell) for cell in row)]
    body, total_rows, note_rows = drop_footer_totals(body)
    if not body:
        return None
    inner_totals = count_inner_totals(body)

    names, labels = normalise_names(grid[header_index])
    cleaned = {name: [clean_cell(row[i]) for row in body] for i, name in enumerate(names)}
    # The text now lives in `cleaned`. Releasing the rows here, and each text column once it
    # is converted below, took peak memory on a 20 MB CSV from 416 MB to 372 MB.
    raw.grid = grid = body = []
    # One decision for the whole table: an export writes every date the same way, so a
    # 25/04/2025 in one column settles what 03/04/2025 means in another.
    dayfirst, undecidable = infer_dayfirst(
        text for column in cleaned.values() for text in set(column) if text is not None
    )
    columns = {
        name: infer_column(name, labels[name], cleaned.pop(name), dayfirst) for name in names
    }

    empty = [name for name, column in columns.items() if all(v is None for v in column.values)]
    columns = {name: column for name, column in columns.items() if name not in empty}
    if not columns:
        return None

    df = pd.DataFrame(
        {
            name: pd.Series(column.values, dtype=_DTYPES[column.type])
            for name, column in columns.items()
        }
    )
    warnings = _warnings(columns, labels, empty, note_rows, inner_totals, undecidable)
    health = _health(df, columns, header_index, total_rows, undecidable, warnings)
    return IngestedTable(
        table_name=table_name,
        source_file=raw.source_file,
        sheet=raw.sheet,
        df=df,
        labels={name: labels[name] for name in columns},
        types={name: column.type for name, column in columns.items()},
        health=health,
    )


def _health(
    df: pd.DataFrame,
    columns: dict[str, InferredColumn],
    header_index: int,
    total_rows: int,
    undecidable: bool,
    warnings: list[str],
) -> DataHealth:
    """Write the receipt. `pii_columns` and `duplicates_removed` belong to profiling, which
    knows about PII and identifiers; duplicates are only counted here, never removed."""
    date_labels: Counter[str] = sum((c.date_labels for c in columns.values()), Counter())
    null_share = df.isna().mean().sort_values(ascending=False, kind="stable")
    hotspots = null_share[null_share > NULL_HOTSPOT_THRESHOLD].head(MAX_NULL_HOTSPOTS)
    return DataHealth(
        rows=len(df),
        columns=len(df.columns),
        skipped_title_rows=header_index,
        dropped_total_rows=total_rows,
        duplicate_rows=int(df.duplicated().sum()),
        date_format=date_labels.most_common(1)[0][0] if date_labels else None,
        date_format_ambiguous=undecidable and _ambiguous_date_columns(columns) != [],
        coercions=[
            Coercion(
                column=name,
                to_type=column.type,
                detail=column.detail,
                unparseable=column.unparseable,
                examples=column.examples,
            )
            for name, column in columns.items()
            if column.type != "text"
        ],
        null_hotspots={name: round(float(share), 4) for name, share in hotspots.items()},
        preserved_id_columns=[name for name, column in columns.items() if column.preserved_as_text],
        warnings=warnings,
    )


def _ambiguous_date_columns(columns: dict[str, InferredColumn]) -> list[str]:
    return [name for name, column in columns.items() if column.numeric_date_example]


def _warnings(
    columns: dict[str, InferredColumn],
    labels: dict[str, str],
    empty: list[str],
    note_rows: int,
    inner_totals: int,
    undecidable: bool,
) -> list[str]:
    """Plain sentences about anything the user might not expect. Only header text and
    date-shaped values are quoted: free text from a cell never goes into a warning,
    because warnings may be repeated next to an answer."""
    warnings: list[str] = []
    if empty:
        shown = ", ".join(display_name(labels[name], name) for name in empty[:5])
        more = f" and {len(empty) - 5} more" if len(empty) > 5 else ""
        if len(empty) == 1:
            warnings.append(f"The column {shown} has no values and was left out.")
        else:
            warnings.append(
                f"{len(empty)} columns have no values and were left out: {shown}{more}."
            )
    if note_rows:
        rows_were = "row was" if note_rows == 1 else "rows were"
        warnings.append(f"{note_rows} note {rows_were} left out with the total row above.")
    if inner_totals:
        # The one warning that means "your sums are wrong until you act", so it says how.
        rows_are = "row inside the table is" if inner_totals == 1 else "rows inside the table are"
        warnings.append(
            f"{inner_totals} {rows_are} labelled Total or Sub Total and kept, because only "
            "totals at the end of a table are removed. Sums over this table count those "
            "amounts twice. Remove the subtotal rows from the file and upload it again."
        )
    ambiguous = _ambiguous_date_columns(columns) if undecidable else []
    if ambiguous:
        example = columns[ambiguous[0]].numeric_date_example
        as_read = next(v for v in columns[ambiguous[0]].values if v is not None)
        shown = ", ".join(display_name(labels[name], name) for name in ambiguous)
        warnings.append(
            f"Dates in {shown} could be day-first or month-first (for example {example}). "
            "They were read as day-first, the usual order in India. If that is wrong, export "
            f"the file again with dates written like {as_read.isoformat()}."
        )
    warnings += [column.warning for column in columns.values() if column.warning]
    return warnings
