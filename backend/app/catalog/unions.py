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


def union_signature(table: TableProfile) -> frozenset[str]:
    """Candidates to stack are matched on column NAMES. Types are then checked per column by
    `resolve_columns`, which is where a column that is empty on one side is forgiven."""
    return frozenset(c.name for c in table.columns)


def _is_empty(column: ColumnProfile) -> bool:
    """No values at all: "LWD" on the sheet of the people who have not left."""
    return column.null_fraction >= 1.0


def resolve_columns(members: list[TableProfile]) -> dict[str, ColumnProfile] | None:
    """One column profile per name — the member that has values decides the type — or None
    when two members give a column different types and neither of them is empty.

    Why empty columns are forgiven: ingest keeps a named column with nothing in it, and it
    has no evidence of a type, so it reads as text. That is the only reason the Active and
    Separated sheets of a staff workbook would not stack, and not stacking them is how a
    total comes out 6% low with nothing on screen to say so. Anything else is a real
    disagreement: stacking a text "days" onto an integer one would hide a broken export.
    """
    resolved: dict[str, ColumnProfile] = {}
    for member in members:
        for column in member.columns:
            chosen = resolved.get(column.name)
            if chosen is None or (_is_empty(chosen) and not _is_empty(column)):
                resolved[column.name] = column
            elif chosen.type != column.type and not _is_empty(column):
                return None
    return resolved


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
    """Group base tables that share their column names and agree on every type (>= 2 tables).

    view_name is the leading `_`-separated words the table names share plus "_all" (fallback
    "combined_<n>"). New unions are "active"; a union the user rejected stays rejected.

    ponytail: a group is all-or-nothing. Three files where two agree on a type and the third
    does not produce no view at all, rather than a view of two. Split the group by type if a
    real export ever looks like that.

    ponytail: a union is remembered by its view name, so a rejected "combined_1" could be
    confused with a different unnamed group later. Key it by member set if that ever bites.
    """
    rejected = {u.id for u in existing if u.status == "rejected"}
    groups: dict[frozenset[str], list[TableProfile]] = {}
    for table in tables:
        if not table.is_view and SOURCE_COLUMN not in union_signature(table):
            groups.setdefault(union_signature(table), []).append(table)

    taken = {t.name for t in tables if not t.is_view}
    unions: list[UnionView] = []
    fallbacks = 0
    for members in groups.values():
        if len(members) < 2 or resolve_columns(members) is None:
            continue
        names = [m.name for m in members]
        name = _view_name(names, taken, fallbacks + 1)
        fallbacks += name.startswith("combined_")
        taken.add(name)
        unions.append(UnionView(id=name, view_name=name, tables=names,
                                status="rejected" if name in rejected else "active"))
    return unions


def _source_labels(members: list[TableProfile]) -> list[str]:
    """What `source_file` says for each member: the file name, plus the sheet when two
    members come from the same workbook and the file name alone could not tell them apart."""
    files = [m.source_file for m in members]
    return [f"{m.source_file} / {m.sheet}" if m.sheet and files.count(m.source_file) > 1 else m.source_file
            for m in members]


def _profile_view(conn: duckdb.DuckDBPyConnection, union: UnionView, members: list[TableProfile],
                  labels: list[str], resolved: dict[str, ColumnProfile]) -> TableProfile:
    """Profile the view from its real rows, in one query. Summing member statistics would be
    wrong where it matters most: an employee id that is unique in each quarter is not unique
    across the year, and the fan-out check trusts `is_unique`."""
    columns = list(resolved.values())
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


def _member_select(member: TableProfile, resolved: dict[str, ColumnProfile], label: str) -> str:
    """One branch of the view. A column that is empty here but typed elsewhere is selected as
    a bare NULL, which takes the other branch's type: without that cast, stacking an empty
    text column onto a date column would turn every date in the view into a string."""
    own = {c.name: c for c in member.columns}
    columns = [quote(name) if own[name].type == column.type else f"NULL AS {quote(name)}"
               for name, column in resolved.items()]
    return (f"SELECT {', '.join(columns)}, {_literal(label)} AS {SOURCE_COLUMN} "
            f"FROM {quote(member.name)}")


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
        resolved = resolve_columns(members)
        if resolved is None:  # only reachable if a caller hand-built a union; detection cannot
            continue
        labels = _source_labels(members)
        selects = [_member_select(m, resolved, label) for m, label in zip(members, labels)]
        conn.execute(f"CREATE VIEW {quote(union.view_name)} AS " + " UNION ALL BY NAME ".join(selects))
        profiles.append(_profile_view(conn, union, members, labels, resolved))
    return profiles
