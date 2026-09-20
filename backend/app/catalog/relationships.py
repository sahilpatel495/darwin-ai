"""Detect join keys across tables by value overlap, with cardinality.

Why both headers and values: values alone lie. `order_id` 1..50 and `store_id` 1..50 overlap
perfectly and mean nothing, and a join on them gives a confident, wrong answer. So a link
is switched on automatically only when the headers agree (same role or a similar name)
*and* the values agree; agreement on values alone is offered to the user as a suggestion.

Why "values agree" looks at the better direction: HR child tables cover some employees,
not all. Only a quarter of staff get a bonus, yet every bonus row points at a known
employee, and that containment is what makes the join sound. How many rows an inner join
then leaves out is a caveat on the answer (the pipeline adds it), not a reason to doubt the key.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from itertools import combinations

import duckdb

from app.catalog.unions import quote, schema_signature
from app.contracts import ColumnProfile, Relationship, TableProfile, UnionView

KEEP_AT = 0.5  # share of one table's keys found in the other, below which a pair is noise
ACTIVE_AT = 0.8  # the same share, from which a link is on by default (if the headers agree)
_KEY_TYPES = ("text", "integer")  # nobody joins on an amount or a date
# ponytail: one overlap query per candidate pair, capped. 100 covers dozens of ordinary HR
# files; a hostile workbook of 300 "*_id" columns stops here instead of running 90,000 queries.
MAX_CANDIDATES = 100
MAX_LINKS = 40  # every kept link is a line in every prompt, and model tokens are the scarce resource


def _is_key_like(col: ColumnProfile) -> bool:
    """Identifiers, plus email: HR tools outside the HRIS (surveys, learning) key people by it."""
    return col.is_identifier or col.pii == "email"


def _headers_agree(left: ColumnProfile, right: ColumnProfile) -> bool:
    if left.role and right.role:
        return left.role == right.role
    return left.name == right.name or SequenceMatcher(None, left.name, right.name).ratio() >= 0.8


def _is_candidate(left: ColumnProfile, right: ColumnProfile) -> bool:
    if left.type != right.type or left.type not in _KEY_TYPES:
        return False
    if any(c.pii and c.pii != "email" for c in (left, right)):
        return False  # names and phone numbers are not join keys
    if left.role and right.role and left.role != right.role:
        return False  # an employee id is not a manager id, however well the values overlap
    if _is_key_like(left) and _is_key_like(right):
        return True
    # A shared category (department, region) is a key only into a lookup table, where it is
    # unique. Joining two fact tables on "department" multiplies rows.
    return _headers_agree(left, right) and (left.is_unique or right.is_unique)


def _overlap(conn: duckdb.DuckDBPyConnection, left: TableProfile, left_col: str,
             right: TableProfile, right_col: str) -> tuple[float, float]:
    """Share of distinct non-null keys found on the other side, in both directions. Both
    sides are compared as text, so '007' only ever matches '007'."""
    n_left, n_right, shared = conn.execute(
        f"WITH l AS (SELECT DISTINCT CAST({quote(left_col)} AS VARCHAR) AS v FROM {quote(left.name)}"
        f" WHERE {quote(left_col)} IS NOT NULL),"
        f" r AS (SELECT DISTINCT CAST({quote(right_col)} AS VARCHAR) AS v FROM {quote(right.name)}"
        f" WHERE {quote(right_col)} IS NOT NULL)"
        " SELECT (SELECT count(*) FROM l), (SELECT count(*) FROM r), (SELECT count(*) FROM l JOIN r USING (v))"
    ).fetchone()
    if not n_left or not n_right:
        return 0.0, 0.0
    return round(shared / n_left, 4), round(shared / n_right, 4)


def _cardinality(left: ColumnProfile, right: ColumnProfile) -> str:
    return {(True, True): "1:1", (True, False): "1:N", (False, True): "N:1", (False, False): "N:M"}[
        (left.is_unique, right.is_unique)]


def _joins_through_a_master(link: Relationship, links: list[Relationship]) -> bool:
    """True for a many-to-many link whose two keys both point at the same unique key, such as
    attendance.emp_id and payroll.emp_code, which both point at employees.emp_id. Joining
    those two directly multiplies rows; the master table is the honest path between them.

    ponytail: only N:M links. Two fact tables also meet at the master when one of them has
    one row per employee (exit interviews, an appraisal sheet), and those links are left on,
    so the panel shows more links than a person would draw. Dropping them needs more than
    cardinality: by cardinality alone a one-row-per-employee sheet that covers 80% of the
    staff looks exactly like a master, and the rule then throws away the payroll link to the
    real staff master. Upgrade path: rank candidate masters by key coverage and terminality
    (a master's key is not itself a foreign key) before using one to drop other links.
    """

    def masters(table: str, column: str) -> set[tuple[str, str]]:
        found = set()
        for r in links:
            if r.status == "rejected":
                continue
            if r.cardinality == "N:1" and (r.left_table, r.left_column) == (table, column):
                found.add((r.right_table, r.right_column))
            if r.cardinality == "1:N" and (r.right_table, r.right_column) == (table, column):
                found.add((r.left_table, r.left_column))
        return found

    return link.cardinality == "N:M" and bool(
        masters(link.left_table, link.left_column) & masters(link.right_table, link.right_column))


def linkable_tables(tables: list[TableProfile], unions: list[UnionView]) -> list[TableProfile]:
    """The tables links are detected between: an active combined view stands in for its own
    members, so the members themselves are left out.

    Why: half a dataset is worse than none. With the members linked instead, payroll gets a
    strong link to the sheet of current staff and a weak, off-by-default one to the leavers,
    and "net pay by region" quietly answers for the current staff alone. One link to the view
    is also one link in the prompt instead of one per file.
    """
    views = {u.view_name for u in unions if u.status == "active"}
    members = {name for u in unions if u.status == "active" for name in u.tables}
    return [t for t in tables
            if (t.name in views if t.is_view else t.name not in members)]


def detect_relationships(
    conn: duckdb.DuckDBPyConnection, tables: list[TableProfile], existing: list[Relationship],
    unions: list[UnionView] | None = None,
) -> list[Relationship]:
    """Return relationships for the current tables, preserving user decisions in `existing`.

    Candidates: column pairs across different tables with compatible types where both are
    identifier-like or share a role or a similar name. Overlap is measured in DuckDB on
    distinct non-null values, both directions. Keep pairs with
    max(match_left, match_right) >= 0.5. status is "active" when max(match) >= 0.8 and the
    headers agree, else "suggested"; a pair the user already set to active/rejected keeps
    that status. Cardinality comes from ColumnProfile.is_unique on each side. ids are stable:
    f"{left_table}.{left_column}->{right_table}.{right_column}" with tables sorted.

    `unions` are the combined views of these tables (active ones must already exist in the
    database): each one is linked in place of its members, so match rates and cardinality are
    measured over the whole stacked dataset. Without it, only base tables are considered.

    Narrower than "every overlapping pair" on purpose (see the module docstring): conflicting
    roles are never paired, a non-identifier pair needs a unique side, two tables with the
    same schema are left to the union view, and a many-to-many link is dropped when both
    tables already join through a master table, unless the user has decided on it.
    """
    previous = {r.id: r.status for r in existing if r.status in ("active", "rejected")}
    base = sorted(linkable_tables(tables, unions or []), key=lambda t: t.name)

    candidates = [
        (left, lc, right, rc)
        for left, right in combinations(base, 2)
        if schema_signature(left) != schema_signature(right)
        for lc in left.columns for rc in right.columns if _is_candidate(lc, rc)
    ]
    candidates.sort(key=lambda c: not (_is_key_like(c[1]) and _is_key_like(c[3])))  # identifiers first

    found: list[Relationship] = []
    user_decided: set[str] = set()
    for left, lc, right, rc in candidates[:MAX_CANDIDATES]:
        match_left, match_right = _overlap(conn, left, lc.name, right, rc.name)
        if max(match_left, match_right) < KEEP_AT:
            continue
        link_id = f"{left.name}.{lc.name}->{right.name}.{rc.name}"
        automatic = "active" if max(match_left, match_right) >= ACTIVE_AT and _headers_agree(lc, rc) else "suggested"
        status = previous.get(link_id, automatic)
        if status != automatic:  # `existing` cannot say who set a status; a status the detector
            user_decided.add(link_id)  # would not have chosen can only have come from the user
        found.append(Relationship(
            id=link_id, left_table=left.name, left_column=lc.name, right_table=right.name,
            right_column=rc.name, match_left=match_left, match_right=match_right,
            cardinality=_cardinality(lc, rc), status=status))

    kept = [r for r in found if r.id in user_decided or not _joins_through_a_master(r, found)]
    # The sidebar and the prompt list these in order: usable links first, fan-out risks last.
    return sorted(kept, key=lambda r: (r.status != "active", r.cardinality == "N:M", r.id))[:MAX_LINKS]
