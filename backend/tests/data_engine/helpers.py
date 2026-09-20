"""Hand-built IngestedTables, so these tests never depend on the ingest module.

The dtypes follow the convention documented on IngestedTable: integer -> Int64,
decimal/currency/percent -> float64, date -> datetime64, boolean -> boolean, text -> str.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from app.contracts import DataHealth
from app.ingest.types import IngestedTable

_DTYPES = {"integer": "Int64", "decimal": "float64", "currency": "float64",
           "percent": "float64", "boolean": "boolean", "text": "str"}


def ingested(name: str, columns: dict[str, tuple[str, list]], *, labels: dict[str, str] | None = None,
             source_file: str | None = None, sheet: str | None = None,
             health: DataHealth | None = None) -> IngestedTable:
    """columns = {column name: (ColumnType, values)}."""
    data = {
        col: pd.to_datetime(pd.Series(values)) if ctype == "date" else pd.Series(values, dtype=_DTYPES[ctype])
        for col, (ctype, values) in columns.items()
    }
    df = pd.DataFrame(data)
    return IngestedTable(
        table_name=name, source_file=source_file or f"{name}.csv", sheet=sheet, df=df,
        labels={col: (labels or {}).get(col, col) for col in columns},
        types={col: ctype for col, (ctype, _) in columns.items()},
        health=health or DataHealth(rows=len(df), columns=len(columns)),
    )


def tiny_ingest(path: Path, original_name: str, taken_table_names: set[str]) -> list[IngestedTable]:
    """A stand-in for app.ingest.ingest_file: CSV only, every column text except *_date
    (date) and ctc/gross (currency). Enough to drive Session.add_files deterministically."""
    from app.ingest import IngestError

    raw = pd.read_csv(path, dtype=str)
    if raw.empty:
        raise IngestError("has column headers but no data rows.")  # deliberately omits the file name
    name = Path(original_name).stem.lower()
    while name in taken_table_names:
        name += "_2"
    columns: dict[str, tuple[str, list]] = {}
    for col in raw.columns:
        values = [None if pd.isna(v) else v for v in raw[col]]
        if col.endswith("_date"):
            columns[col] = ("date", values)
        elif col in ("ctc", "gross"):
            columns[col] = ("currency", [None if v is None else float(v) for v in values])
        else:
            columns[col] = ("text", values)
    return [ingested(name, columns, source_file=original_name)]
