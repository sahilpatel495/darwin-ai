"""Shared contracts: every API payload and every hand-off between modules.

Why one file: five agents build in parallel against these types. If a shape
changes here, it changes for everyone at once, and `frontend/src/types.ts`
mirrors it by hand. Only the Lead edits this file.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# Ingestion and profiling
# --------------------------------------------------------------------------

ColumnType = Literal["integer", "decimal", "currency", "percent", "date", "boolean", "text"]
PiiKind = Literal[
    "email", "phone", "pan", "aadhaar", "uan", "bank_account", "ifsc", "person_name"
]


class Coercion(BaseModel):
    """One line of the ingestion receipt: what we changed in a column and how much failed."""

    column: str
    to_type: ColumnType
    detail: str
    unparseable: int = 0
    examples: list[str] = Field(default_factory=list)  # max 3, never from PII columns


class DataHealth(BaseModel):
    """The per-table ingestion receipt shown on the file card."""

    rows: int
    columns: int
    skipped_title_rows: int = 0
    dropped_total_rows: int = 0
    duplicate_rows: int = 0
    duplicates_removed: bool = False
    date_format: str | None = None  # e.g. "DD/MM/YYYY"
    date_format_ambiguous: bool = False
    coercions: list[Coercion] = Field(default_factory=list)
    null_hotspots: dict[str, float] = Field(default_factory=dict)  # column -> null fraction
    pii_columns: list[str] = Field(default_factory=list)
    preserved_id_columns: list[str] = Field(default_factory=list)  # kept as text
    warnings: list[str] = Field(default_factory=list)


class ColumnProfile(BaseModel):
    name: str  # normalised snake_case; the DuckDB column name
    label: str  # original header text
    type: ColumnType
    role: str | None = None  # semantic role, see app.profile.roles.ROLES
    pii: PiiKind | None = None
    is_identifier: bool = False
    is_unique: bool = False
    null_fraction: float = 0.0
    distinct_count: int = 0
    min: str | None = None  # stringified; None for text and PII columns
    max: str | None = None
    # True distinct values. ONLY for non-PII columns with <= 30 distinct values.
    # This is the single field through which cell text can reach a prompt.
    values: list[str] | None = None


class TableProfile(BaseModel):
    name: str  # DuckDB table or view name
    source_file: str
    sheet: str | None = None
    row_count: int
    columns: list[ColumnProfile]
    health: DataHealth
    is_view: bool = False  # union views


# --------------------------------------------------------------------------
# Catalog
# --------------------------------------------------------------------------


class Relationship(BaseModel):
    id: str
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    match_left: float  # share of distinct left values found on the right, 0..1
    match_right: float
    cardinality: Literal["1:1", "1:N", "N:1", "N:M"]
    status: Literal["active", "suggested", "rejected"]


class UnionView(BaseModel):
    id: str
    view_name: str
    tables: list[str]
    status: Literal["active", "rejected"]


class Metric(BaseModel):
    """A vetted business definition. `sql_pattern` uses {role} placeholders."""

    key: str
    name: str
    synonyms: list[str]
    definition: str
    required_roles: list[str]
    sql_pattern: str


class ResolvedMetric(BaseModel):
    """A glossary metric bound to this session's actual columns."""

    metric: Metric
    bindings: dict[str, str] = Field(default_factory=dict)  # role -> "table.column"
    sql_hint: str = ""  # sql_pattern with placeholders filled; "" when roles are missing
    missing_roles: list[str] = Field(default_factory=list)


class Catalog(BaseModel):
    session_id: str
    version: int  # bumps on any change; part of every cache key
    fingerprint: str  # sha256 over uploaded file bytes; keys the process-level cache
    tables: list[TableProfile] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    unions: list[UnionView] = Field(default_factory=list)
    glossary: list[Metric] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


class LinkUpdate(BaseModel):
    status: Literal["active", "rejected"]


# --------------------------------------------------------------------------
# Asking and answering
# --------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    # Resolved ambiguities: term -> "table.column", e.g. {"salary": "salary_register.gross"}
    clarification: dict[str, str] | None = None


Stage = Literal[
    "understand", "generate", "guard", "execute", "repair", "verify", "chart", "narrate", "done"
]


class StepEvent(BaseModel):
    stage: Stage
    status: Literal["started", "ok", "warn", "failed"]
    detail: str = ""


class ClarifyOption(BaseModel):
    label: str  # "Gross pay (salary_register.gross)"
    value: str  # "salary_register.gross"


class Clarification(BaseModel):
    term: str
    question: str
    options: list[ClarifyOption]


class ChartSpec(BaseModel):
    """Data, never code. Chosen by rules in app.query.charts, rendered by the frontend."""

    type: Literal["kpi", "bar", "line", "area", "grouped_bar", "stacked_bar", "donut",
                  "histogram", "heatmap", "scatter", "table"]
    x: str | None = None
    y: list[str] = Field(default_factory=list)
    series: str | None = None
    title: str = ""
    note: str | None = None  # e.g. "Showing top 12 of 43 groups"
    value_format: Literal["number", "currency_inr", "percent"] = "number"


class ResultTable(BaseModel):
    columns: list[str]
    rows: list[list[Any]]  # JSON-safe scalars
    display: list[list[str]]  # pre-formatted strings, same shape as rows
    row_count: int
    truncated: bool = False


class Attempt(BaseModel):
    sql: str
    model: str
    reason: Literal["initial", "sql_error", "guard_rejected", "empty_result", "fan_out"]
    error: str | None = None


class ModelPayload(BaseModel):
    """Exactly what one LLM call was sent. Powers the "What the model saw" tab."""

    purpose: Literal["generate", "crosscheck", "repair", "narrate"]
    provider: str
    model: str
    messages: list[dict[str, str]]
    cached: bool = False
    latency_ms: int = 0


class CrossCheck(BaseModel):
    status: Literal["agreed", "disagreed", "unavailable", "skipped"] = "skipped"
    model: str | None = None
    detail: str = ""
    sql: str | None = None


class Confidence(BaseModel):
    level: Literal["high", "medium", "low"]
    score: float
    reasons: list[str]


class Work(BaseModel):
    """Everything behind "How I got this"."""

    interpretation: str = ""  # the model's restatement of the question
    reading: str = ""  # plain-English reading of the final SQL (back-translation)
    plan: list[str] = Field(default_factory=list)
    sql: str | None = None
    tables_used: list[str] = Field(default_factory=list)
    rows_scanned: int = 0
    assumptions: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    metrics_used: list[str] = Field(default_factory=list)  # glossary keys
    attempts: list[Attempt] = Field(default_factory=list)
    payloads: list[ModelPayload] = Field(default_factory=list)
    cross_check: CrossCheck = Field(default_factory=CrossCheck)
    cached: bool = False
    timings_ms: dict[str, int] = Field(default_factory=dict)


class Answer(BaseModel):
    id: str
    kind: Literal["answer", "clarify", "refusal", "meta", "error"]
    question: str
    text: str  # plain text only; the frontend never renders it as markdown or HTML
    clarification: Clarification | None = None
    missing: str | None = None  # refusal: what data would be needed
    retry_after_s: int | None = None  # error: the models are busy; the UI counts this down
    insights: list[str] = Field(default_factory=list)  # computed facts about the result, never model-written
    chart: ChartSpec | None = None
    table: ResultTable | None = None
    work: Work = Field(default_factory=Work)
    confidence: Confidence | None = None
    followups: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    message: str  # human sentence
    next_step: str  # what the user can do about it


# --------------------------------------------------------------------------
# Evaluation report (served at /api/eval/report, rendered as the Trust Report)
# --------------------------------------------------------------------------


class EvalCase(BaseModel):
    id: str
    category: str
    split: Literal["dev", "holdout"]
    question: str
    expected_kind: str
    got_kind: str
    passed: bool
    confidence: str | None = None
    latency_ms: int = 0
    repairs: int = 0
    note: str = ""


class CalibrationBucket(BaseModel):
    n: int
    accuracy: float


class ModelScore(BaseModel):
    model: str
    accuracy: float
    p50_ms: int


class EvalReport(BaseModel):
    generated_at: str
    model: str
    runs: int
    total: int
    accuracy: float
    accuracy_holdout: float
    trust_score: float  # mean of +1 correct, 0 abstain, -1 wrong
    by_category: dict[str, float]
    p50_ms: int
    p95_ms: int
    repair_rate: float
    crosscheck_agreement: float | None = None
    calibration: dict[str, CalibrationBucket] = Field(default_factory=dict)
    models: list[ModelScore] = Field(default_factory=list)
    cases: list[EvalCase] = Field(default_factory=list)
