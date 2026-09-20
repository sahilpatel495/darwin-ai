// Mirror of backend/app/contracts.py. Hand-maintained by the Lead: if the Pydantic models
// change, this file changes in the same commit. Fixtures in ./fixtures are generated from the
// Pydantic models, so `pnpm typecheck` catches drift.

export type ColumnType = 'integer' | 'decimal' | 'currency' | 'percent' | 'date' | 'boolean' | 'text'
export type PiiKind = 'email' | 'phone' | 'pan' | 'aadhaar' | 'uan' | 'bank_account' | 'ifsc' | 'person_name'

export interface Coercion {
  column: string
  to_type: ColumnType
  detail: string
  unparseable: number
  examples: string[]
}

export interface DataHealth {
  rows: number
  columns: number
  skipped_title_rows: number
  dropped_total_rows: number
  duplicate_rows: number
  duplicates_removed: boolean
  date_format: string | null
  date_format_ambiguous: boolean
  coercions: Coercion[]
  null_hotspots: Record<string, number>
  pii_columns: string[]
  preserved_id_columns: string[]
  warnings: string[]
}

export interface ColumnProfile {
  name: string
  label: string
  type: ColumnType
  role: string | null
  pii: PiiKind | null
  is_identifier: boolean
  is_unique: boolean
  null_fraction: number
  distinct_count: number
  min: string | null
  max: string | null
  values: string[] | null
}

export interface TableProfile {
  name: string
  source_file: string
  sheet: string | null
  row_count: number
  columns: ColumnProfile[]
  health: DataHealth
  is_view: boolean
}

export interface Relationship {
  id: string
  left_table: string
  left_column: string
  right_table: string
  right_column: string
  match_left: number
  match_right: number
  cardinality: '1:1' | '1:N' | 'N:1' | 'N:M'
  status: 'active' | 'suggested' | 'rejected'
}

export interface UnionView {
  id: string
  view_name: string
  tables: string[]
  status: 'active' | 'rejected'
}

export interface Metric {
  key: string
  name: string
  synonyms: string[]
  definition: string
  required_roles: string[]
  sql_pattern: string
}

export interface Catalog {
  session_id: string
  version: number
  fingerprint: string
  tables: TableProfile[]
  relationships: Relationship[]
  unions: UnionView[]
  glossary: Metric[]
  suggested_questions: string[]
}

export interface AskRequest {
  question: string
  clarification?: Record<string, string> | null
}

export type Stage = 'understand' | 'generate' | 'guard' | 'execute' | 'repair' | 'verify' | 'chart' | 'narrate' | 'done'

export interface StepEvent {
  stage: Stage
  status: 'started' | 'ok' | 'warn' | 'failed'
  detail: string
}

export interface ClarifyOption {
  label: string
  value: string
}

export interface Clarification {
  term: string
  question: string
  options: ClarifyOption[]
}

export interface ChartSpec {
  type: 'kpi' | 'bar' | 'line' | 'grouped_bar' | 'scatter' | 'table'
  x: string | null
  y: string[]
  series: string | null
  title: string
  note: string | null
  value_format: 'number' | 'currency_inr' | 'percent'
}

export type Cell = string | number | boolean | null

export interface ResultTable {
  columns: string[]
  rows: Cell[][]
  display: string[][]
  row_count: number
  truncated: boolean
}

export interface Attempt {
  sql: string
  model: string
  reason: 'initial' | 'sql_error' | 'guard_rejected' | 'empty_result' | 'fan_out'
  error: string | null
}

export interface ModelPayload {
  purpose: 'generate' | 'crosscheck' | 'repair' | 'narrate'
  provider: string
  model: string
  messages: { role: string; content: string }[]
  cached: boolean
  latency_ms: number
}

export interface CrossCheck {
  status: 'agreed' | 'disagreed' | 'unavailable' | 'skipped'
  model: string | null
  detail: string
  sql: string | null
}

export interface Confidence {
  level: 'high' | 'medium' | 'low'
  score: number
  reasons: string[]
}

export interface Work {
  interpretation: string
  reading: string
  plan: string[]
  sql: string | null
  tables_used: string[]
  rows_scanned: number
  assumptions: string[]
  caveats: string[]
  metrics_used: string[]
  attempts: Attempt[]
  payloads: ModelPayload[]
  cross_check: CrossCheck
  cached: boolean
  timings_ms: Record<string, number>
}

export interface Answer {
  id: string
  kind: 'answer' | 'clarify' | 'refusal' | 'meta' | 'error'
  question: string
  text: string
  clarification: Clarification | null
  missing: string | null
  retry_after_s: number | null
  chart: ChartSpec | null
  table: ResultTable | null
  work: Work
  confidence: Confidence | null
  followups: string[]
}

export interface ErrorResponse {
  message: string
  next_step: string
}

export interface EvalCase {
  id: string
  category: string
  split: 'dev' | 'holdout'
  question: string
  expected_kind: string
  got_kind: string
  passed: boolean
  confidence: string | null
  latency_ms: number
  repairs: number
  note: string
}

export interface EvalReport {
  generated_at: string
  model: string
  runs: number
  total: number
  accuracy: number
  accuracy_holdout: number
  trust_score: number
  by_category: Record<string, number>
  p50_ms: number
  p95_ms: number
  repair_rate: number
  crosscheck_agreement: number | null
  calibration: Record<string, { n: number; accuracy: number }>
  models: { model: string; accuracy: number; p50_ms: number }[]
  cases: EvalCase[]
}

// Server-sent events on POST /api/sessions/{id}/ask
export type AskEvent =
  | { event: 'step'; data: StepEvent }
  | { event: 'answer'; data: Answer }
  | { event: 'error'; data: ErrorResponse }
