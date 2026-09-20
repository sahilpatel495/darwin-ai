"""Profile: statistics, PII flags, semantic roles, identifier detection, duplicates policy.

A profile is everything the rest of the app is allowed to know about a table without
looking at its rows. The prompt builder reads profiles and nothing else, so what is decided
here (which columns are PII, which values may be listed) is the privacy boundary.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from app.contracts import ColumnProfile, ColumnType, PiiKind, TableProfile
from app.ingest.cleaning import MAX_EXAMPLE_LENGTH, display_name, shorten, spelling_variants
from app.ingest.types import IngestedTable
from app.profile.pii import detect_pii
from app.profile.roles import IDENTIFIER_PATTERN, detect_role

MAX_LISTED_VALUES = 30  # a column with more distinct values than this is not a category
MAX_SPELLING_NOTES = 5  # per column, as with the empty columns ingest lists: the rest are counted
RANGED_TYPES: tuple[ColumnType, ...] = ("integer", "decimal", "currency", "percent", "date")  # have a min and max


def may_show_range(ctype: ColumnType, pii: str | None, role: str | None) -> bool:
    """A min and max are two real cell values, so personal data gets none: the lowest phone
    number is somebody's phone number, and the earliest date of birth is somebody's birthday."""
    return pii is None and role != "birth_date" and ctype in RANGED_TYPES


def format_bound(value: object) -> str:
    """A min or max as text: ISO for dates, no trailing '.0' on whole amounts."""
    if hasattr(value, "isoformat"):  # pandas Timestamp, datetime or date
        return str(value.isoformat())[:10]
    number = float(value)  # type: ignore[arg-type]
    return str(int(number)) if number.is_integer() else str(round(number, 2))


def _is_identifier(name: str, label: str, ctype: ColumnType) -> bool:
    """A column whose job is to name a row: an employee or manager id by role, or a header
    ending in id/code/no/number (the same rule ingest uses to keep it as text)."""
    return detect_role(name, label, ctype) in ("employee_id", "manager_id") or bool(IDENTIFIER_PATTERN.search(name))


def _listed_values(series: pd.Series, ctype: ColumnType) -> list[str]:
    distinct = series.dropna().unique().tolist()
    if ctype == "boolean":
        return sorted(str(bool(v)).lower() for v in distinct)
    return sorted(str(v) for v in distinct)


def _profile_column(name: str, label: str, ctype: ColumnType, series: pd.Series,
                    pii: PiiKind | None) -> ColumnProfile:
    role = detect_role(name, label, ctype)
    present = series.dropna()
    distinct = int(present.nunique())

    has_range = may_show_range(ctype, pii, role) and not present.empty
    lists_values = pii is None and ctype in ("text", "boolean") and distinct <= MAX_LISTED_VALUES
    return ColumnProfile(
        name=name, label=label, type=ctype, role=role, pii=pii,
        is_identifier=_is_identifier(name, label, ctype),
        is_unique=len(series) > 0 and len(present) == len(series) and distinct == len(series),
        null_fraction=round(1 - len(present) / len(series), 4) if len(series) else 0.0,
        distinct_count=distinct,
        min=format_bound(present.min()) if has_range else None,
        max=format_bound(present.max()) if has_range else None,
        values=_listed_values(present, ctype) if lists_values else None,
    )


def _fold_spellings(df: pd.DataFrame, labels: dict[str, str], types: dict[str, ColumnType],
                    pii: dict[str, PiiKind | None]) -> tuple[pd.DataFrame, list[str]]:
    """Fold case and space variants of a category value together; return the frame and the
    receipt lines. Identifier and PII columns are never touched: two employee codes that
    differ only in case are two people, and a person's name is not a category.

    Here rather than in ingest because this is the first point that knows which columns hold
    personal data. The quoted spellings are capped the same way an unreadable-value example
    is, because a warning can be repeated next to an answer.
    """
    notes: list[str] = []
    folds: dict[str, dict[str, str]] = {}
    for name in df.columns:
        if types[name] != "text" or pii[name] or _is_identifier(name, labels[name], types[name]):
            continue
        counts = Counter(v for v in df[name] if isinstance(v, str))
        if folded := spelling_variants(counts):
            folds[name] = folded
            notes += _spelling_notes(display_name(labels[name], name), folded, counts)
    if not folds:
        return df, notes
    df = df.copy()  # only now: most files have nothing to fold and the frame can be large
    for name, folded in folds.items():
        df[name] = df[name].replace(folded)
    return df, notes


def _spelling_notes(label: str, folded: dict[str, str], counts: Counter[str]) -> list[str]:
    """One sentence per group of spellings, in the order the winners appear in the column."""
    groups: dict[str, list[str]] = {}
    for variant, winner in folded.items():
        groups.setdefault(winner, []).append(variant)
    notes = []
    for winner, variants in list(groups.items())[:MAX_SPELLING_NOTES]:
        variants.sort(key=lambda v: (-counts[v], v))
        shown = [repr(shorten(v, MAX_EXAMPLE_LENGTH)) for v in variants[:3]]
        if len(variants) > 3:
            shown.append(f"{len(variants) - 3} more")
        listed = shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]
        rows = sum(counts[v] for v in variants)
        was = "was" if len(variants) == 1 else "were"
        notes.append(f"{label}: {listed} {was} read as {winner!r} "
                     f"({rows} row{'' if rows == 1 else 's'}).")
    if (extra := len(groups) - MAX_SPELLING_NOTES) > 0:  # under-reporting is the worse receipt
        notes.append(f"{label}: {extra} more value{'' if extra == 1 else 's'} had "
                     f"{'its' if extra == 1 else 'their'} spellings folded together this way.")
    return notes


def profile_table(table: IngestedTable) -> tuple[pd.DataFrame, TableProfile]:
    """Return the final DataFrame and its profile.

    Duplicates policy: exact full-row duplicates are dropped only when the table has an
    identifier column (rows identical *including the ID* are an export error); otherwise
    they are kept and only counted. Either way `health.duplicate_rows` reports the count and
    `health.duplicates_removed` says what happened. Also fills `health.pii_columns`.

    Spelling variants of one category value ("sales", "SALES") are folded together first, so
    the duplicate count and every statistic below describe the table the user will query.
    """
    df = table.df
    labels = {name: table.labels.get(name, name) for name in df.columns}
    has_identifier = any(_is_identifier(name, labels[name], table.types[name]) for name in df.columns)
    pii = {name: detect_pii(name, labels[name], table.types[name], df[name]) for name in df.columns}

    df, spelling_notes = _fold_spellings(df, labels, table.types, pii)
    duplicates = int(df.duplicated().sum())
    removed = has_identifier and duplicates > 0
    if removed:
        df = df.drop_duplicates().reset_index(drop=True)

    # Profile after de-duplication so every statistic describes the table the user queries.
    columns = [_profile_column(name, labels[name], table.types[name], df[name], pii[name])
               for name in df.columns]
    pii_columns = [c.name for c in columns if c.pii]
    health = table.health.model_copy(update={
        "rows": len(df), "columns": len(columns), "duplicate_rows": duplicates,
        "duplicates_removed": removed, "pii_columns": pii_columns,
        "warnings": [*table.health.warnings, *spelling_notes],
        # Ingest cannot know a column is PII; its "could not read" examples are cell values.
        "coercions": [c.model_copy(update={"examples": []}) if c.column in pii_columns else c
                      for c in table.health.coercions],
    })
    profile = TableProfile(name=table.table_name, source_file=table.source_file, sheet=table.sheet,
                           row_count=len(df), columns=columns, health=health)
    return df, profile
