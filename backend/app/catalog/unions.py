"""Detect same-schema tables (jan.csv, feb.csv) and expose them as one view.

Why: monthly or quarterly exports are one dataset cut into files. Asked for a half-year
total, a model that sees two separate tables tends to answer from one of them. A single
view with a `source_file` column makes the whole dataset the obvious thing to query, and
still lets the user compare the files.
"""

from __future__ import annotations

import duckdb

from app.contracts import ColumnProfile, DataHealth, TableProfile, UnionView
from app.profile import MAX_LISTED_VALUES, format_bound, may_show_range

SOURCE_COLUMN = "source_file"


def quote(identifier: str) -> str:
    """A double-quoted SQL identifier. Names are normalised upstream; this is the second lock."""
    return '"' + identifier.replace('"', '""') + '"'


def _literal(text: str) -> str:
    """A single-quoted SQL string. File names come from the uploader, so they are hostile."""
    return "'" + text.replace("'", "''") + "'"


def schema_signature(table: TableProfile) -> frozenset[tuple[str, str]]:
    """Two tables are the same export when their (column, type) sets are identical."""
    return frozenset((c.name, c.type) for c in table.columns)


def _view_name(members: list[str], taken: set[str], fallback_number: int) -> str:
    """attendance_q1 + attendance_q2 -> attendance_all: the leading words they share."""
    shared: list[str] = []
    for words in zip(*(name.split("_") for name in members)):
        if len(set(words)) > 1:
            break
        shared.append(words[0])
    base = "_".join(shared) + "_all" if shared else f"combined_{fallback_number}"
    name, n = base, 1
    while name in taken:
        n += 1
        name = f"{base}_{n}"
    return name


def detect_unions(tables: list[TableProfile], existing: list[UnionView]) -> list[UnionView]:
    """Group base tables whose normalised column names and types match exactly (>= 2 tables).

    view_name is the leading `_`-separated words the table names share plus "_all" (fallback
    "combined_<n>"). New unions are "active"; a union the user rejected stays rejected.

    ponytail: a union is remembered by its view name, so a rejected "combined_1" could be
    confused with a different unnamed group later. Key it by member set if that ever bites.
    """
    rejected = {u.id for u in existing if u.status == "rejected"}
    groups: dict[frozenset[tuple[str, str]], list[str]] = {}
    for table in tables:
        if not table.is_view and SOURCE_COLUMN not in {c.name for c in table.columns}:
            groups.setdefault(schema_signature(table), []).append(table.name)

    taken = {t.name for t in tables if not t.is_view}
    unions: list[UnionView] = []
    fallbacks = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        name = _view_name(members, taken, fallbacks + 1)
        fallbacks += name.startswith("combined_")
        taken.add(name)
        unions.append(UnionView(id=name, view_name=name, tables=members,
                                status="rejected" if name in rejected else "active"))
    return unions


def _source_labels(members: list[TableProfile]) -> list[str]:
    """What `source_file` says for each member: the file name, plus the sheet when two
    members come from the same workbook and the file name alone could not tell them apart."""
    files = [m.source_file for m in members]
    return [f"{m.source_file} / {m.sheet}" if m.sheet and files.count(m.source_file) > 1 else m.source_file
            for m in members]


def _profile_view(conn: duckdb.DuckDBPyConnection, union: UnionView, members: list[TableProfile],
                  labels: list[str]) -> TableProfile:
    """Profile the view from its real rows, in one query. Summing member statistics would be
    wrong where it matters most: an employee id that is unique in each quarter is not unique
    across the year, and the fan-out check trusts `is_unique`."""
    columns = members[0].columns
    # Same column in every member. If any member flags it as PII, the view does too.
    in_members = {c.name: [next(mc for mc in m.columns if mc.name == c.name) for m in members] for c in columns}
    pii = {name: next((mc.pii for mc in cols if mc.pii), None) for name, cols in in_members.items()}

    parts = ["count(*)"]
    for c in columns:
        ranged = may_show_range(c.type, pii[c.name], c.role)
        parts += [f"count({quote(c.name)})", f"count(DISTINCT {quote(c.name)})",
                  f"min({quote(c.name)})" if ranged else "NULL", f"max({quote(c.name)})" if ranged else "NULL"]
    total, *stats = conn.execute(f"SELECT {', '.join(parts)} FROM {quote(union.view_name)}").fetchone()

    profiled: list[ColumnProfile] = []
    for i, c in enumerate(columns):
        present, distinct, low, high = stats[4 * i: 4 * i + 4]
        listed = [mc.values for mc in in_members[c.name]]
        values = sorted({v for vs in listed for v in vs}) if all(vs is not None for vs in listed) else None
        if pii[c.name] or (values is not None and len(values) > MAX_LISTED_VALUES):
            values = None
        profiled.append(c.model_copy(update={
            "pii": pii[c.name], "values": values, "distinct_count": distinct,
            "is_unique": total > 0 and present == total and distinct == total,
            "null_fraction": round(1 - present / total, 4) if total else 0.0,
            "min": None if low is None else format_bound(low),
            "max": None if high is None else format_bound(high),
        }))
    profiled.append(ColumnProfile(name=SOURCE_COLUMN, label="Source file", type="text",
                                  distinct_count=len(labels), values=sorted(labels)))
    health = DataHealth(
        rows=total, columns=len(profiled), pii_columns=[c.name for c in profiled if c.pii],
        # Only duplicates that are still in the data can distort an answer from this view.
        duplicate_rows=sum(m.health.duplicate_rows for m in members if not m.health.duplicates_removed))
    return TableProfile(name=union.view_name, source_file=" + ".join(m.source_file for m in members),
                        row_count=total, columns=profiled, health=health, is_view=True)


def create_union_views(
    conn: duckdb.DuckDBPyConnection, unions: list[UnionView], tables: list[TableProfile]
) -> list[TableProfile]:
    """(Re)create one view per active union: UNION ALL BY NAME of members plus a
    `source_file` text column; drop views of rejected unions. Returns a TableProfile
    (is_view=True) per active view so the model can see it."""
    by_name = {t.name: t for t in tables if not t.is_view}
    profiles: list[TableProfile] = []
    for union in unions:
        conn.execute(f"DROP VIEW IF EXISTS {quote(union.view_name)}")
        if union.status != "active":
            continue
        members = [by_name[name] for name in union.tables]
        labels = _source_labels(members)
        selects = [f"SELECT *, {_literal(label)} AS {SOURCE_COLUMN} FROM {quote(m.name)}"
                   for m, label in zip(members, labels)]
        conn.execute(f"CREATE VIEW {quote(union.view_name)} AS " + " UNION ALL BY NAME ".join(selects))
        profiles.append(_profile_view(conn, union, members, labels))
    return profiles
