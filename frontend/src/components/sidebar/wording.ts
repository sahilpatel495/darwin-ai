// Every sentence the sidebar derives from catalog data lives here, as pure functions.
// Why: the analyst has to trust these lines in front of their CHRO, so the wording is tested
// (wording.test.mjs) without a browser. Only `import type` is allowed in this file: Node runs the
// tests by stripping types, and it cannot resolve the app's extensionless value imports.

import type { ColumnType, DataHealth, Relationship, UnionView } from '../../types'

/** `warn` marks lines the analyst should read before trusting a number from this file. */
export interface ReceiptLine {
  tone: 'ok' | 'warn'
  text: string
}

const count = (n: number, noun: string): string => `${n.toLocaleString('en-IN')} ${noun}${n === 1 ? '' : 's'}`

/** Caps long column lists: a 300-column export must not turn the receipt into a wall of names. */
function nameList(names: string[], max = 6): string {
  if (names.length <= max) return names.join(', ')
  return `${names.slice(0, max).join(', ')} and ${names.length - max} more`
}

/** Column types in the analyst's words; also used for the column list on the file card. */
export const TYPE_NOUN: Record<ColumnType, string> = {
  currency: '₹ amounts',
  date: 'dates',
  percent: 'percentages',
  integer: 'whole numbers',
  decimal: 'decimal numbers',
  boolean: 'yes/no values',
  text: 'text',
}

/**
 * Turns the ingestion receipt into sentences, in the order the cleaning happened.
 * Always returns at least one line, so an empty receipt never looks like a check that was skipped.
 * `label` turns a cleaned column name (pay_month) back into the header the analyst wrote (Pay Month).
 */
export function receiptLines(health: DataHealth, label: (column: string) => string = (column) => column): ReceiptLine[] {
  const lines: ReceiptLine[] = []
  const ok = (text: string) => lines.push({ tone: 'ok', text })
  const warn = (text: string) => lines.push({ tone: 'warn', text })

  if (health.skipped_title_rows > 0) ok(`Skipped ${count(health.skipped_title_rows, 'title row')} above the column names.`)
  if (health.dropped_total_rows > 0) ok(`Dropped ${count(health.dropped_total_rows, 'total row')} so sums are not counted twice.`)

  if (health.duplicate_rows > 0) {
    const duplicates = count(health.duplicate_rows, 'exact duplicate row')
    if (health.duplicates_removed) ok(`Removed ${duplicates}.`)
    else warn(`Found ${duplicates} and kept them, because this file has no ID column to prove they are mistakes.`)
  }

  // Columns with unreadable values get their own warning; clean conversions are grouped by type
  // so a wide file produces at most one line per type.
  const cleanByType = new Map<ColumnType, string[]>()
  for (const c of health.coercions) {
    if (c.unparseable > 0) {
      const examples = c.examples.length ? ` (${c.examples.join(', ')})` : ''
      warn(`${label(c.column)}: parsed ${TYPE_NOUN[c.to_type]}, ${count(c.unparseable, 'unreadable value')} left empty${examples}.`)
    } else {
      cleanByType.set(c.to_type, [...(cleanByType.get(c.to_type) ?? []), label(c.column)])
    }
  }
  for (const [type, columns] of cleanByType) ok(`Read as ${TYPE_NOUN[type]}: ${nameList(columns)}.`)

  if (health.date_format) {
    if (health.date_format_ambiguous) warn(`Dates read as ${health.date_format}. Some could be read either way, so day first was assumed.`)
    else ok(`Dates read as ${health.date_format}.`)
  }

  if (health.pii_columns.length) ok(`PII columns hidden from the model: ${nameList(health.pii_columns.map(label))}.`)
  if (health.preserved_id_columns.length) ok(`Kept as text to preserve leading zeros: ${nameList(health.preserved_id_columns.map(label))}.`)

  for (const [column, fraction] of Object.entries(health.null_hotspots)) {
    warn(`${label(column)}: ${Math.round(fraction * 100)}% of values are empty.`)
  }
  for (const warning of health.warnings) warn(warning)

  if (lines.length === 0) ok('No cleaning was needed. Every value was read as it appears in the file.')
  return lines
}

/** Whole percent, rounded down. The epsilon undoes float noise: 0.29 * 100 is 28.999999999999996. */
const wholePercent = (fraction: number): number => Math.floor(fraction * 100 + 1e-9)

/**
 * The headline match: the better of the two directions, rounded down (showing 100% for 99.6%
 * would overstate the join). Better, not weaker, because that is the side the backend uses to
 * switch a link on, and because in a healthy link every child row finds its parent while many
 * parents have no child: a bonus sheet that covers a quarter of the staff is a sound link, and
 * "25%" beside "In use" reads as a broken one. The explanation still gives both directions.
 */
export function matchPercent(link: Relationship): number {
  return wholePercent(Math.max(link.match_left, link.match_right))
}

/** Turns a SQL table name into what the analyst calls it (the file). Supplied by the caller so this file stays import-free. */
type TableNamer = (table: string) => string

/** Files, not SQL identifiers: "employees.csv ↔ Salary_Register_2025.xlsx (sheet Register)". */
export function linkLabel(link: Relationship, name: TableNamer): string {
  return `${name(link.left_table)} ↔ ${name(link.right_table)}`
}

/** Says the matching column, the match and the cardinality in words, for readers who have never seen "1:N". */
export function linkExplanation(link: Relationship, name: TableNamer): string {
  const [left, right] = [name(link.left_table), name(link.right_table)]
  const percent = (fraction: number) => `${wholePercent(fraction)}%`
  const on = link.left_column === link.right_column ? link.left_column : `${link.left_column} = ${link.right_column}`
  const match =
    link.match_left === link.match_right
      ? `${percent(link.match_left)} of the values match in both directions.`
      : `${percent(link.match_left)} of the ${link.left_column} values in ${left} are found in ${right}, and ${percent(link.match_right)} the other way.`
  const shape: Record<Relationship['cardinality'], string> = {
    '1:1': `Each row in ${left} matches at most one row in ${right}.`,
    '1:N': `One row in ${left} can match many rows in ${right}.`,
    'N:1': `Many rows in ${left} can match one row in ${right}.`,
    'N:M': `Rows repeat on both sides, so totals across this link can be counted more than once.`,
  }
  return `Matched on ${on}. ${match} ${shape[link.cardinality]}`
}

export function unionLabel(union: UnionView, name: TableNamer): string {
  return union.tables.map(name).join(' + ')
}

// ponytail: mirrors _MAX_SYNONYMS and _MAX_SYNONYM_CHARS in backend/app/sessions.py. The server is
// the authority, but it answers a breach with a general error, so this is where the analyst
// learns what to change. Serve the limits from the API if they ever become configurable.
const MAX_SYNONYMS = 20
const MAX_SYNONYM_CHARS = 80

/** Why a glossary edit cannot be saved yet, as one sentence for the analyst; null when it can be. */
export function metricProblem(definition: string, synonyms: string[]): string | null {
  // The text box's own "required" check accepts spaces, and an empty definition would reach the model.
  if (definition.trim() === '') return 'Write a definition before saving, so the model is told what this metric means.'
  if (synonyms.length > MAX_SYNONYMS) return `Keep to ${MAX_SYNONYMS} other names or fewer. There are ${synonyms.length} now.`
  const long = synonyms.find((name) => name.length > MAX_SYNONYM_CHARS)
  if (long) return `"${long.slice(0, 30)}…" is longer than ${MAX_SYNONYM_CHARS} characters. Shorten it, or separate the names with commas.`
  return null
}

/** Comma-separated text to a clean synonym list; the first spelling of a repeated word wins. */
export function parseSynonyms(text: string): string[] {
  const seen = new Set<string>()
  const synonyms: string[] = []
  for (const word of text.split(',').map((w) => w.trim())) {
    const key = word.toLowerCase()
    if (word === '' || seen.has(key)) continue
    seen.add(key)
    synonyms.push(word)
  }
  return synonyms
}
