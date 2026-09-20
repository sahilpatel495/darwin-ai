"""Contracts for the no-AI half of the product: the automatic overview and guided analyses.

Why they exist: an analyst should get value the second a file lands, and should still get
it when every free model is rate limited. Everything here is computed by templates over the
catalog (roles, types, links) and run through the same guard, executor and presentation code
as a model-written query. No model call, no tokens, identical output every time.
Mirrored by hand in frontend/src/types.ts. Lead-owned.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.contracts import ChartSpec, ResultTable

TileKind = Literal["kpi", "breakdown", "trend", "distribution", "share", "comparison",
                   "relationship", "quality", "metric"]
ColumnKind = Literal["measure", "category", "date", "text"]


class InsightTile(BaseModel):
    """One computed finding: a sentence, a picture, the rows, and the SQL that produced them."""

    id: str
    title: str  # "Gross pay by department"
    kind: TileKind
    statement: str  # deterministic sentence built only from display strings
    insights: list[str] = Field(default_factory=list)  # short computed facts, e.g. "Top 3 make up 72%"
    chart: ChartSpec | None = None
    table: ResultTable | None = None
    sql: str = ""
    tables_used: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    ask: str | None = None  # a plain-English question that continues this finding in the thread


class DashboardSection(BaseModel):
    title: str  # "People", "Pay", "Attendance", "Data quality", or a table's name for generic data
    description: str = ""
    tiles: list[InsightTile] = Field(default_factory=list)


class Dashboard(BaseModel):
    session_id: str
    catalog_version: int
    generated_ms: int
    sections: list[DashboardSection] = Field(default_factory=list)


class AnalysisInput(BaseModel):
    key: str  # "measure", "by", "date", "measure_b", "group_a" ...
    label: str  # "What to measure"
    accepts: list[ColumnKind]
    optional: bool = False


class AnalysisOption(BaseModel):
    key: str  # "aggregate", "top_n", "grain"
    label: str
    choices: list[str]  # first is the default
 

class AnalysisKind(BaseModel):
    key: str  # breakdown | trend | top_n | distribution | share | compare | correlation | pivot | change | outliers
    name: str
    description: str  # one plain sentence: what question it answers
    example: str  # "Average CTC by department"
    inputs: list[AnalysisInput]
    options: list[AnalysisOption] = Field(default_factory=list)


class ColumnChoice(BaseModel):
    ref: str  # "table.column"
    label: str  # the file's own header text
    table_label: str  # the file (and sheet) the analyst recognises
    kind: ColumnKind
    # The column's own distinct values, for pickers such as "compare these two groups".
    # Only for non-PII category columns with at most 30 values; never row data.
    values: list[str] = Field(default_factory=list)


class AnalysisCatalog(BaseModel):
    kinds: list[AnalysisKind]
    columns: list[ColumnChoice]  # PII columns are never offered as a measure or category


class AnalysisRequest(BaseModel):
    kind: str
    inputs: dict[str, str]  # input key -> column ref; every ref is validated against the catalog
    options: dict[str, str] = Field(default_factory=dict)
