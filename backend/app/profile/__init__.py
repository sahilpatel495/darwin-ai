"""Profile: statistics, PII flags, semantic roles, identifier detection, duplicates policy."""

from __future__ import annotations

import pandas as pd

from app.contracts import TableProfile
from app.ingest.types import IngestedTable


def profile_table(table: IngestedTable) -> tuple[pd.DataFrame, TableProfile]:
    """Return the final DataFrame and its profile.

    Duplicates policy: exact full-row duplicates are dropped only when the table has an
    identifier column (rows identical *including the ID* are an export error); otherwise
    they are kept and only counted. Either way `health.duplicate_rows` reports the count and
    `health.duplicates_removed` says what happened. Also fills `health.pii_columns`.
    """
    raise NotImplementedError
