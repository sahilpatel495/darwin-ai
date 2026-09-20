"""Ingest: turn a messy CSV/Excel upload into clean typed tables plus a receipt."""

from __future__ import annotations

from pathlib import Path

from app.ingest.types import IngestedTable


class IngestError(ValueError):
    """Raised with a human-readable message (shown to the user as-is)."""


def ingest_file(path: Path, original_name: str, taken_table_names: set[str]) -> list[IngestedTable]:
    """Read one upload and return one IngestedTable per CSV or non-empty Excel sheet.

    Reads every cell as text first and infers types itself so IDs like "000457" survive.
    Supported: .csv .tsv .txt .xlsx .xlsm. Anything else, an empty file, or a header-only
    file raises IngestError with a sentence the user can act on.
    """
    raise NotImplementedError
