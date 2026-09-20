"""Hand-off types between reading, cleaning and profiling."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.contracts import ColumnType, DataHealth


@dataclass
class RawTable:
    """One sheet or CSV exactly as read: every cell is text or None, nothing inferred yet."""

    name_hint: str  # file stem, or "stem_sheet" for multi-sheet workbooks
    source_file: str
    sheet: str | None
    grid: list[list[str | None]]


@dataclass
class IngestedTable:
    """A cleaned, typed table ready for profiling.

    DataFrame dtype convention: integer -> Int64, decimal/currency/percent -> float64,
    date -> datetime64[ns] (midnight), boolean -> boolean, text -> str. Percent "45%" -> 45.0.
    """

    table_name: str  # unique in the session, snake_case, valid bare SQL identifier
    source_file: str
    sheet: str | None
    df: pd.DataFrame  # columns are the normalised names
    labels: dict[str, str]  # normalised name -> original header text
    types: dict[str, ColumnType]
    health: DataHealth  # pii_columns and duplicates_removed are filled in by profiling
