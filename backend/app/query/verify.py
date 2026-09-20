"""Catch answers that run fine and are still wrong."""

from __future__ import annotations

from app.contracts import Catalog
from app.query.executor import ExecResult
from app.query.guard import GuardedQuery


def fan_out_risks(query: GuardedQuery, catalog: Catalog) -> list[str]:
    """For each equality join use ColumnProfile.is_unique on both keys. Report (a) N:M joins
    and (b) SUM/AVG/COUNT over a column of the unique-key ("one") side of a 1:N join, which
    multiplies rows. Returns human sentences; empty when safe."""
    raise NotImplementedError


def null_caveats(query: GuardedQuery, catalog: Catalog, threshold: float = 0.05) -> list[str]:
    """Sentences for referenced columns whose null_fraction >= threshold, plus tables whose
    health reports duplicates (removed or kept)."""
    raise NotImplementedError


def results_equivalent(a: ExecResult, b: ExecResult, rel_tol: float = 1e-6) -> bool:
    """Rows compared as multisets, ignoring column names and order; the smaller column set
    must be a subset of the larger; numbers compared with rel_tol; row order ignored."""
    raise NotImplementedError
