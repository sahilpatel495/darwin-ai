"""Allow-list SQL guard. Deny-lists were bypassed twice in the wild; we list what is allowed.

The SQL is written by a model that read a stranger's question, so it is treated as hostile.
DuckDB's lock-down (app.sessions) already blocks files and the network, but it still permits
CREATE/INSERT, so this guard is a control in its own right, not a formality.

What is allowed: one SELECT (or UNION/INTERSECT/EXCEPT of SELECTs) over the tables and columns
in this session's catalog, using functions sqlglot recognises (except the few that report on
the engine, such as version(), and the few that build huge values or cannot be stopped, see
_reject_runaway_functions) plus the short list below.
Anything the guard cannot analyse is refused: a refusal costs one repair, a miss costs trust.

We execute the SQL re-rendered from the parsed tree, never the model's text, so DuckDB runs
exactly what was checked and a comment or odd token cannot mean one thing here and another
there. `GuardError.message` is shown to the user and sent to the model for repair.
"""

from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope

from app.contracts import Catalog

# When sqlglot cannot parse a statement it logs a warning that quotes the whole statement. SQL
# written for "what does Asha Rao earn" carries her name, and names do not belong in server logs.
logging.getLogger("sqlglot").setLevel(logging.ERROR)


class GuardError(ValueError):
    def __init__(self, code: str, message: str, suggestion: str | None = None):
        super().__init__(message)
        self.code = code  # parse | multi | not_select | write | table_function | qualified |
        self.message = message  # unknown_table | unknown_column | function
        self.suggestion = suggestion  # e.g. "Did you mean exit_reason?"


@dataclass
class JoinRef:
    left_table: str
    left_column: str
    right_table: str
    right_column: str


@dataclass
class GuardedQuery:
    sql: str  # re-rendered by sqlglot in the duckdb dialect
    tables: list[str] = field(default_factory=list)  # real catalog tables/views referenced
    columns: list[tuple[str, str]] = field(default_factory=list)  # (table, column) resolved
    joins: list[JoinRef] = field(default_factory=list)  # equality joins between real tables
    aggregated: list[tuple[str, str, str]] = field(default_factory=list)  # (func, table, column)


_WRITES = (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
           exp.TruncateTable, exp.Copy, exp.Into)
# What may sit inside brackets or WITH. `SELECT * FROM (SUMMARIZE employees)` is a SELECT on the
# outside and returns the min and max of every column, names and emails included, without
# naming one column, so nothing downstream would know to hide them from the narration model.
_QUERY_BODIES = (exp.Select, exp.SetOperation, exp.Subquery, exp.Table, exp.Values)
_ROW_SOURCES = (exp.GenerateSeries, exp.Unnest)  # the only functions allowed to produce rows
_FILE_READERS = (exp.ReadCSV, exp.ReadParquet)
_AGGREGATES = (exp.Sum, exp.Avg, exp.Count, exp.Min, exp.Max)
_UNTYPED_FUNCTIONS = (exp.Anonymous, exp.AnonymousAggFunc)
# The typed functions that describe the engine or the session instead of the data. A DuckDB
# version or user name is no use to an analyst and some use to an attacker. Found by running
# every name in duckdb_functions() through the guard; repeat that on a sqlglot or DuckDB upgrade.
_ENGINE_INFO = (exp.CurrentVersion, exp.CurrentUser, exp.CurrentRole, exp.SessionUser,
                exp.CurrentDatabase, exp.CurrentCatalog, exp.CurrentSchema, exp.CurrentSchemas)

# DuckDB's memory_limit covers its buffers, not the text a function builds: measured on 1.5.5
# with a 512 MB limit, repeat('x', 4000000000) took the process to 3.4 GB and range(30000000)
# to 2.8 GB once Python had copied the list. One question must not be able to do that, so a
# length argument has to be a small number written in the query. This stops the one-line
# bombs, not every route (nested replace() can still build large text): the container's memory
# limit is the backstop for the rest.
MAX_SQL_CHARS = 20_000  # the guard's own parsing is CPU we spend before any timeout applies
MAX_BUILT_CHARS = 1_000  # repeat(s, n), lpad(s, n, fill), rpad(s, n, fill): n at most this
_LENGTH_ARGUMENT = {exp.Repeat: "times", exp.Pad: "expression"}
# printf and format take a width from the pattern or from an argument ('%*d'), so they are
# bombs too, and the app formats every number itself (presentation.py). The edit distances are
# quadratic in the length of their inputs and DuckDB only looks at its interrupt flag between
# batches of 2,048 rows: damerau_levenshtein over 64 long strings ran past a 10 s timeout for
# more than 90 s, holding a CPU and the session's connection. sqlglot has no node for printf
# or damerau_levenshtein, so those two are refused by being absent from _ALLOWED_FUNCTIONS.
_RUNAWAY_FUNCTIONS = (exp.Format, exp.Levenshtein)

# sqlglot parses every function it knows into a typed node (sum, date_trunc, coalesce, ...);
# those are ordinary analytical functions and are allowed. Any other name arrives as
# exp.Anonymous and must be listed here. That is what keeps out sleep_ms, write_log,
# current_setting, getenv, read_text and whatever a future DuckDB release adds, without anyone
# remembering to deny them. To allow one more, check it reads no files, settings or
# environment and has no side effects, then add it.
_ALLOWED_FUNCTIONS = frozenset({
    # dates
    "age", "date_part", "datepart", "date_sub", "datesub", "weekday", "isoyear", "yearweek",
    "decade", "century", "now", "get_current_timestamp", "try_strptime",
    "to_years", "to_months", "to_weeks", "to_hours", "to_minutes", "to_seconds",
    # numbers
    "add", "subtract", "multiply", "divide", "fdiv", "fmod", "gcd", "lcm", "even",
    "round_even", "roundbankers", "isfinite",
    # aggregates
    "mean", "product", "fsum", "favg", "kahan_sum", "sumkahan", "arbitrary", "mad",
    "geomean", "geometric_mean", "wavg", "weighted_avg", "histogram", "entropy",
    # text
    "prefix", "suffix", "strlen", "ord", "strip_accents", "regexp_escape",
    "regexp_split_to_array", "jaro_similarity", "jaccard", "hamming",
    # lists (string_agg / list results)
    "list_aggr", "list_aggregate", "list_unique", "list_position", "list_extract",
    "list_slice", "list_sum", "list_avg", "list_count",
    # misc
    "constant_or_null", "equi_width_bins", "bar",
})


def validate_sql(sql: str, catalog: Catalog) -> GuardedQuery:
    """Parse as DuckDB; exactly one statement; Select or set operation only; no write/command
    nodes; no table functions (generate_series and unnest allowed); no catalog/schema-qualified
    names; only allow-listed functions, none of them able to build a huge value in one call
    or to outrun the timeout; every real table in the catalog (CTEs resolved via
    scopes); every column resolved against the catalog, unknown ones raise unknown_column with
    a difflib closest-match suggestion. Raises GuardError, and nothing else: an unexpected
    failure inside sqlglot is reported as a refusal, never as a pass.

    The structural checks run first so the message names the most basic problem.
    """
    tree = _parse_one_statement(sql)
    try:
        _reject_anything_but_a_read(tree)
        _reject_row_producing_functions_and_qualified_names(tree)
        _reject_unlisted_functions(tree)
        _reject_runaway_functions(tree)
        _reject_columns_selected_without_a_name(tree)
        tables = _real_tables(tree, catalog)
        _check_qualified_columns(tree, catalog)
        columns, joins, aggregated = _references(_qualify(tree, catalog), catalog)
        return GuardedQuery(
            sql=tree.sql(dialect="duckdb", pretty=True, comments=False),
            tables=tables, columns=columns, joins=joins, aggregated=aggregated,
        )
    except GuardError:
        raise
    except Exception as exc:  # fail closed: SQL we cannot analyse is not run
        raise GuardError("parse", "I could not check that query, so it was not run.") from exc


# ---- structure ----------------------------------------------------------------------------


def _parse_one_statement(sql: str) -> exp.Expression:
    if len(sql) > MAX_SQL_CHARS:
        raise GuardError("parse", f"The query is longer than {MAX_SQL_CHARS:,} characters, so it"
                         " was not run. Write a shorter query.")
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except (SqlglotError, RecursionError) as exc:
        raise GuardError("parse", "The query is not valid SQL, so it was not run.") from exc
    if not statements:
        raise GuardError("parse", "The query is empty, so there was nothing to run.")
    if len(statements) > 1:
        raise GuardError("multi", "Only one SELECT statement can run at a time.")
    return statements[0]


def _reject_anything_but_a_read(tree: exp.Expression) -> None:
    """Writes are searched for at any depth: `WITH x AS (DELETE ... RETURNING *) SELECT ...`
    is a SELECT at the top and a DELETE inside."""
    if tree.find(*_WRITES):
        raise GuardError("write", "Only queries that read data are allowed."
                                  " This one would change or export data.")
    if not isinstance(tree, (exp.Select, exp.SetOperation)):
        raise GuardError("not_select", "Only a single SELECT query is allowed.")
    bodies = [nested.this for nested in tree.find_all(exp.Subquery, exp.CTE)]
    only_queries = all(isinstance(body, _QUERY_BODIES) for body in bodies)
    if tree.find(exp.Summarize, exp.Describe) or not only_queries:
        raise GuardError("not_select", "Only SELECT is allowed inside brackets and WITH."
                         " SUMMARIZE and DESCRIBE are not: select the columns and aggregates"
                         " you need by name.")


def _reject_row_producing_functions_and_qualified_names(tree: exp.Expression) -> None:
    """`FROM read_csv(...)`, `FROM query('...')` and `information_schema.tables` are how a
    SELECT reaches files, arbitrary SQL and engine internals. LATERAL is checked too because
    sqlglot does not wrap a lateral function in a Table node."""
    for node in tree.find_all(exp.Table, exp.Lateral, *_FILE_READERS):
        source = node if isinstance(node, _FILE_READERS) else node.this
        if isinstance(source, exp.Func) and not isinstance(source, _ROW_SOURCES):
            raise GuardError("table_function", f"Reading from {_function_name(source)}() is not"
                             " allowed. Queries can only read the uploaded tables.")
        if isinstance(node, exp.Table) and (node.db or node.catalog):
            raise GuardError("qualified", f"{_dotted(node)} is not allowed. Use plain table"
                             " names from the uploaded files, without a schema prefix.")


def _reject_unlisted_functions(tree: exp.Expression) -> None:
    for node in tree.find_all(*_UNTYPED_FUNCTIONS, *_ENGINE_INFO):
        if isinstance(node, _ENGINE_INFO) or node.name.lower() not in _ALLOWED_FUNCTIONS:
            raise GuardError("function", f"The function {_function_name(node)}() is not on the"
                             " list of allowed functions. Rewrite the query with standard SQL"
                             " functions.")


def _reject_runaway_functions(tree: exp.Expression) -> None:
    """Functions that are fine for analysis at small sizes and a way to take the server down at
    large ones (see MAX_BUILT_CHARS and _RUNAWAY_FUNCTIONS for the measurements)."""
    if runaway := tree.find(*_RUNAWAY_FUNCTIONS):
        raise GuardError("function", f"The function {_function_name(runaway)}() is not allowed."
                         " Return plain numbers and text; the app formats them. Compare text"
                         " with =, LIKE or jaro_winkler_similarity().")
    for node in tree.find_all(*_LENGTH_ARGUMENT):
        length = node.args.get(_LENGTH_ARGUMENT[type(node)])
        written_number = isinstance(length, exp.Literal) and length.is_int
        if not (written_number and int(length.name) <= MAX_BUILT_CHARS):
            raise GuardError("function", f"The length given to {_function_name(node)}() has to be"
                             f" a plain number of at most {MAX_BUILT_CHARS:,}.")
    for series in tree.find_all(exp.GenerateSeries):
        if not isinstance(series.parent, (exp.Table, exp.Lateral)):
            # No quoted example here: the repair prompt hides quoted text it has not seen before.
            raise GuardError("function", "generate_series() and range() are only allowed in FROM,"
                             " where rows are produced one batch at a time. For example:"
                             " FROM generate_series(1, 12) AS months(n).")


def _reject_columns_selected_without_a_name(tree: exp.Expression) -> None:
    """Each of these puts a column in the result without writing its real name, so a PII
    column would reach the result without appearing in GuardedQuery.columns, which is the list
    the pipeline uses to decide what to hide from the narration model. `COLUMNS('na.*')` and
    `#2` pick by pattern or position. `FROM employees PIVOT (...)` passes every other column
    through. `FROM employees AS e(emp_id, department)` renames by position, so `department`
    would return names while we recorded the harmless department column."""
    if tree.find(exp.Columns, exp.PositionalColumn):
        raise GuardError("unknown_column", "Columns have to be written by name."
                         " COLUMNS(...) and positions such as #1 are not allowed.")
    if tree.find(exp.Pivot):
        raise GuardError("unknown_column", "PIVOT and UNPIVOT are not allowed because they"
                         " create columns the query does not name. Use GROUP BY with"
                         " CASE WHEN or FILTER instead.")
    for table in tree.find_all(exp.Table):
        alias = table.args.get("alias")
        if _is_real_table(table) and alias is not None and alias.columns:
            raise GuardError("unknown_column", f"The columns of {table.name} cannot be renamed"
                             " in FROM. Remove the list after the table alias and use the real"
                             " column names.")


def _function_name(node: exp.Expression) -> str:
    return (node.name if isinstance(node, _UNTYPED_FUNCTIONS) else node.sql_name()).lower()


def _dotted(table: exp.Table) -> str:
    return ".".join(part for part in (table.catalog, table.db, table.name) if part)


# ---- tables and columns -------------------------------------------------------------------


def _real_tables(tree: exp.Expression, catalog: Catalog) -> list[str]:
    """Scopes decide what is a CTE reference and what is a real table, so a CTE name cannot
    excuse the same name used where the CTE is not visible. A table that no scope lists (the
    right side of a SEMI or ANTI JOIN) gets no such benefit: it must be a catalog table."""
    known = {t.name.lower(): t.name for t in catalog.tables}
    accounted: set[int] = set()
    tables: list[str] = []
    for scope in traverse_scope(tree):
        for node, source in scope.selected_sources.values():
            accounted.add(id(node))
            if _is_real_table(source):
                tables.append(_catalog_table(source, known))
    for table in tree.find_all(exp.Table):
        if id(table) not in accounted and _is_real_table(table):
            tables.append(_catalog_table(table, known))
    return list(dict.fromkeys(tables))


def _is_real_table(source: object) -> bool:
    return isinstance(source, exp.Table) and not isinstance(source.this, exp.Func)


def _catalog_table(table: exp.Table, known: dict[str, str]) -> str:
    """DuckDB would also resolve an unknown name to a file path or a Python variable
    (replacement scans), so an unknown table is a security matter, not only a typo."""
    name = known.get(table.name.lower())
    if name is None:
        close = difflib.get_close_matches(table.name.lower(), known, n=1)
        raise GuardError("unknown_table", f"There is no table named {table.name} in your files.",
                         f"Did you mean {known[close[0]]}?" if close else None)
    return name


def _check_qualified_columns(tree: exp.Expression, catalog: Catalog) -> None:
    """Run before qualify() so `e.attrition_reason` gets our message and suggestion rather
    than sqlglot's exception text."""
    for scope in traverse_scope(tree):
        for column in scope.columns:
            if column.table:
                _resolve(column, scope, catalog)


def _qualify(tree: exp.Expression, catalog: Catalog) -> exp.Expression:
    """Works on a copy: qualify() rewrites the tree (aliases, USING, star expansion) and we
    want to execute what the model wrote, not sqlglot's rewrite. Only column names matter for
    resolution, so every column is declared as VARCHAR."""
    schema = {t.name: {c.name: "VARCHAR" for c in t.columns} for t in catalog.tables}
    try:
        return qualify(tree.copy(), schema=schema, dialect="duckdb",
                       validate_qualify_columns=False, quote_identifiers=False, identify=False)
    except SqlglotError as exc:
        raise GuardError("unknown_column", "I could not match the columns in that query to"
                         f" your files ({exc}).") from exc


def _references(
    qualified: exp.Expression, catalog: Catalog
) -> tuple[list[tuple[str, str]], list[JoinRef], list[tuple[str, str, str]]]:
    """Collect, scope by scope, the real columns the query touches, its equality joins and
    its aggregates. Aliases are resolved to catalog table names."""
    columns: list[tuple[str, str]] = []
    joins: list[JoinRef] = []
    aggregated: list[tuple[str, str, str]] = []
    for scope in traverse_scope(qualified):
        columns += [ref for column in scope.columns if (ref := _resolve(column, scope, catalog))]
        columns += _columns_behind_unexpanded_stars(scope, catalog)
        joins += _joins(scope, catalog)
        aggregated += _aggregates(scope, catalog)
    return list(dict.fromkeys(columns)), joins, list(dict.fromkeys(aggregated))


def _resolve(column: exp.Column, scope: Scope, catalog: Catalog) -> tuple[str, str] | None:
    """(table, column) as the catalog spells them, or None for a column of a CTE, subquery or
    generate_series (DuckDB checks those). Raises unknown_column otherwise."""
    if column.is_star:
        return None
    if not column.table:
        return _unresolved(column, scope, catalog)
    source = _source(scope, column.table)
    if not _is_real_table(source):
        return None
    table = _profile(source, catalog)
    for profile in table.columns:
        if profile.name.lower() == column.name.lower():
            return table.name, profile.name
    raise _unknown_column(column.name, [table.name], catalog)


def _chain(scope: Scope | None):
    """This scope, then the queries around it: a correlated subquery can name outer tables."""
    while scope is not None:
        yield scope
        scope = scope.parent


def _source(scope: Scope, alias: str) -> object:
    for level in _chain(scope):
        for name, source in level.sources.items():
            if name.lower() == alias.lower():
                return source
    return None


def _profile(table: exp.Table, catalog: Catalog):
    return next(t for t in catalog.tables if t.name.lower() == table.name.lower())


def _unresolved(column: exp.Column, scope: Scope, catalog: Catalog) -> tuple[str, str] | None:
    """qualify() left this column without a table. In order: a table alias used as a column
    (`SELECT e FROM employees e` returns whole rows, PII included, without naming a column)
    is refused; the ORDER BY of a UNION names an output column and is left to DuckDB; a name
    owned by exactly one visible table is resolved here, because qualify() gives up when a
    generate_series sits in the same FROM; a name with several owners must be written with its
    table. What remains is unknown, unless a function source could have produced it."""
    name = column.name.lower()
    if any(alias.lower() == name for level in _chain(scope) for alias in level.selected_sources):
        raise GuardError("unknown_column", f"{column.name} is a table in this query, not a"
                         " column. List the columns you need by name.")
    if not isinstance(scope.expression, exp.Select):
        return None
    visible = [source for level in _chain(scope) for source in level.sources.values()]
    tables = [_profile(source, catalog) for source in visible if _is_real_table(source)]
    owners = [(t.name, c.name) for t in tables for c in t.columns if c.name.lower() == name]
    if len(owners) == 1:
        return owners[0]
    if owners:
        names = list(dict.fromkeys(table for table, _ in owners))
        raise GuardError("unknown_column", f"The column {column.name} could come from more than"
                         f" one table in this query ({', '.join(names)}). Write it with its"
                         f" table, for example {names[0]}.{column.name}.")
    if any(not isinstance(source, Scope) and not _is_real_table(source) for source in visible):
        return None
    raise _unknown_column(column.name, [t.name for t in tables], catalog)


def _unknown_column(name: str, tables_in_query: list[str], catalog: Catalog) -> GuardError:
    """Suggest the closest column, looking first in the tables the query already uses."""
    in_query = [t for t in catalog.tables if t.name in tables_in_query]
    for tables in (in_query, catalog.tables):
        dotted = {c.name.lower(): f"{t.name}.{c.name}" for t in reversed(tables) for c in t.columns}
        if close := difflib.get_close_matches(name.lower(), dotted, n=1):
            return GuardError("unknown_column", f"There is no column named {name} in your files.",
                              f"Did you mean {dotted[close[0]]}?")
    return GuardError("unknown_column", f"There is no column named {name} in your files.")


def _columns_behind_unexpanded_stars(scope: Scope, catalog: Catalog) -> list[tuple[str, str]]:
    """qualify() expands `*` into named columns when it can. Where it cannot (a function
    source in the same FROM, `struct_pack(e.*)`), assume every column of the scope's tables is
    read. Over-reporting is the safe side: PII tokenisation downstream keys off this list."""
    if not any(not isinstance(star.parent, exp.Count) for star in scope.find_all(exp.Star)):
        return []
    tables = [_profile(s, catalog) for s in scope.sources.values() if _is_real_table(s)]
    return [(t.name, c.name) for t in tables for c in t.columns]


def _joins(scope: Scope, catalog: Catalog) -> list[JoinRef]:
    """Equalities between columns of two different real tables of this scope, in ON or WHERE.
    A cast or trim around a key is looked through. A correlated EXISTS is skipped on purpose:
    it filters rows and cannot multiply them."""
    joins = []
    for equality in scope.find_all(exp.EQ):
        sides = [_only_column(side) for side in (equality.left, equality.right)]
        if None in sides or sides[0].table == sides[1].table:
            continue
        if not all(_is_real_table(scope.sources.get(side.table)) for side in sides):
            continue
        (lt, lc), (rt, rc) = (_resolve(side, scope, catalog) for side in sides)
        joins.append(JoinRef(lt, lc, rt, rc))
    return joins


def _only_column(side: exp.Expression) -> exp.Column | None:
    found = list(side.find_all(exp.Column))
    return found[0] if len(found) == 1 else None


def _aggregates(scope: Scope, catalog: Catalog) -> list[tuple[str, str, str]]:
    """(func, table, column) for every real column inside SUM/AVG/COUNT/MIN/MAX, so
    `sum(e.ctc / 12)` still counts as summing ctc. DISTINCT aggregates are left out: repeated
    rows cannot change them, and the fan-out check reads this list."""
    found = []
    for aggregate in scope.find_all(*_AGGREGATES):
        if isinstance(aggregate.this, exp.Star):
            found.append((aggregate.key, "*", "*"))
        elif not isinstance(aggregate.this, exp.Distinct):
            found += [(aggregate.key, *ref) for column in aggregate.this.find_all(exp.Column)
                      if (ref := _resolve(column, scope, catalog))]
    return found
