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
    """A single-quoted SQL string. Only member table names go through here now, and those are
    already normalised; the escaping stays as the second lock, exactly as `quote` does."""
    return "'" + text.replace("'", "''") + "'"


def schema_signature(table: TableProfile) -> frozenset[tuple[str, str]]:
    """Two tables are the same export when their (column, type) sets are identical."""
    return frozenset((c.name, c.type) for c in table.columns)


def union_signature(table: TableProfile) -> frozenset[str]:
    """Candidates to stack are matched on column NAMES. Types are then checked per column by
    `resolve_columns`, which is where a column that is empty on one side is forgiven."""
    return frozenset(c.name for c in table.columns)


def _is_empty(column: ColumnProfile) -> bool:
    """No values at all: "LWD" on the sheet of the people who have not left.

    The distinct count decides, not the null share: `null_fraction` is rounded to four
    decimals, so one value in 25,000 rows rounds to 1.0. Forgiving a type clash there let
    `_member_select` write that side as a bare NULL, and the one real value disappeared
    from the view while the base table still had it — a silent loss in the very place
    combined views exist to prevent one.
    """
    return column.distinct_count == 0 and column.null_fraction >= 1.0


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


def _compatible_parts(members: list[TableProfile]) -> list[list[TableProfile]]:
    """Split a name-matched group into parts that also agree on every column type.

    Why not all-or-nothing: three monthly exports where one file typed a column differently
    used to produce no view at all, and a half-year question then answered from one month
    with nothing on screen to say so. Two that agree are still one dataset; the odd file out
    stays a table of its own, which is what it is.

    ponytail: first fit, in upload order, so a different order could stack a different pair
    when more than one split is possible. Real exports differ from each other, not from an
    order; rank the parts by size if that ever stops being true.
    """
    parts: list[list[TableProfile]] = []
    for member in members:
        for part in parts:
            if resolve_columns([*part, member]) is not None:
                part.append(member)
                break
        else:
            parts.append([member])
    return parts


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
    """Group base tables by their column names, then split each group into parts that also
    agree on every type, and make a view of every part with two or more tables.

    view_name is the leading `_`-separated words the table names share plus "_all" (fallback
    "combined_<n>"). New unions are "active"; a union the user rejected stays rejected.

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
        for part in _compatible_parts(members):
            if len(part) < 2:
                continue  # a file nothing else stacks onto stays a table of its own
            names = [m.name for m in part]
            name = _view_name(names, taken, fallbacks + 1)
            fallbacks += name.startswith("combined_")
            taken.add(name)
            unions.append(UnionView(id=name, view_name=name, tables=names,
                                    status="rejected" if name in rejected else "active"))
    return unions


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
        # `source_file` holds member TABLE names, not the uploaded file names. The prompt
        # lists this column's values as filter literals, and a file name is text the
        # uploader chose (DECISIONS 16(b)); a table name is already normalised and is
        # printed in the schema block anyway, so it tells the parts apart at no cost.
        labels = [m.name for m in members]
        selects = [_member_select(m, resolved, label) for m, label in zip(members, labels)]
        conn.execute(f"CREATE VIEW {quote(union.view_name)} AS " + " UNION ALL BY NAME ".join(selects))
        profiles.append(_profile_view(conn, union, members, labels, resolved))
    return profiles
