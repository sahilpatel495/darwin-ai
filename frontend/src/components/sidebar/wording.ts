// Every sentence the workspace derives from catalog data lives here, as pure functions.
// Why: the analyst has to read these lines out in front of their CHRO, so the wording is tested
// (wording.test.mjs) without a browser. Only `import type` is allowed in this file: Node runs the
// tests by stripping types, and it cannot resolve the app's extensionless value imports.

import type { Catalog, ColumnType, DataHealth, Relationship, UnionView } from '../../types'

/**
 * One line of the Data Health receipt: what was done on the left, how much of it on the right.
 * `warn` marks a line the analyst should read before trusting a number from this file.
 */
export interface ReceiptItem {
  tone: 'ok' | 'warn'
  /** The left column. Sentence case, no full stop: it is a ledger line, not a sentence. */
  label: string
  /** The right column, right-aligned and tabular: a count, a percentage or a date format. */
  amount?: string
  /** A second line under the label: the examples, or the columns the line is about. */
  note?: string
}

/** "1 file", "7 files". Every counted noun in the workspace is written through this. */
export const count = (n: number, noun: string): string => `${n.toLocaleString('en-IN')} ${noun}${n === 1 ? '' : 's'}`

/** Caps long column lists: a 300-column export must not turn the receipt into a wall of names. */
function nameList(names: string[], max = 6): string {
  if (names.length <= max) return names.join(', ')
  return `${names.slice(0, max).join(', ')} and ${names.length - max} more`
}

/** Column types in the analyst's words; also used for the column list under each file. */
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
 * Turns the ingestion receipt into itemised lines, in the order the cleaning happened.
 * Always returns at least one line, so an empty receipt never looks like a check that was skipped.
 * `label` turns a cleaned column name (pay_month) back into the header the analyst wrote (Pay Month).
 */
export function receiptLines(health: DataHealth, label: (column: string) => string = (column) => column): ReceiptItem[] {
  const lines: ReceiptItem[] = []
  const ok = (item: Omit<ReceiptItem, 'tone'>) => lines.push({ tone: 'ok', ...item })
  const warn = (item: Omit<ReceiptItem, 'tone'>) => lines.push({ tone: 'warn', ...item })
  const figure = (n: number) => n.toLocaleString('en-IN')

  if (health.skipped_title_rows > 0) ok({ label: 'Title rows skipped above the column names', amount: figure(health.skipped_title_rows) })
  if (health.dropped_total_rows > 0) ok({ label: 'Total rows dropped, so sums are not counted twice', amount: figure(health.dropped_total_rows) })

  if (health.duplicate_rows > 0) {
    if (health.duplicates_removed) ok({ label: 'Exact duplicate rows removed', amount: figure(health.duplicate_rows) })
    else warn({ label: 'Exact duplicate rows kept', amount: figure(health.duplicate_rows), note: 'This file has no ID column to prove they are mistakes.' })
  }

  // Columns with unreadable values get their own line; clean conversions are grouped by type, so a
  // wide file produces at most one line per type instead of one per column.
  const cleanByType = new Map<ColumnType, string[]>()
  for (const c of health.coercions) {
    if (c.unparseable > 0) {
      warn({
        label: `Unreadable ${TYPE_NOUN[c.to_type]} in ${label(c.column)} left empty`,
        amount: figure(c.unparseable),
        note: c.examples.length ? `For example ${c.examples.join(', ')}.` : undefined,
      })
    } else {
      cleanByType.set(c.to_type, [...(cleanByType.get(c.to_type) ?? []), label(c.column)])
    }
  }
  for (const [type, columns] of cleanByType) ok({ label: `Read as ${TYPE_NOUN[type]}`, amount: figure(columns.length), note: nameList(columns) })

  if (health.date_format) {
    if (health.date_format_ambiguous) warn({ label: 'Dates read as', amount: health.date_format, note: 'Some could be read either way, so day first was assumed.' })
    else ok({ label: 'Dates read as', amount: health.date_format })
  }

  if (health.preserved_id_columns.length) {
    ok({ label: 'Kept as text to preserve leading zeros', amount: figure(health.preserved_id_columns.length), note: nameList(health.preserved_id_columns.map(label)) })
  }
  if (health.pii_columns.length) {
    ok({ label: 'Personal-data columns hidden from the AI', amount: figure(health.pii_columns.length), note: nameList(health.pii_columns.map(label)) })
  }

  for (const [column, fraction] of Object.entries(health.null_hotspots)) {
    warn({ label: `Values left empty in ${label(column)}`, amount: `${Math.round(fraction * 100)}%` })
  }
  for (const warning of health.warnings) warn({ label: warning })

  if (lines.length === 0) ok({ label: 'No cleaning was needed', note: 'Every value was read as it appears in the file.' })
  return lines
}

/**
 * The one sentence beside the amber mark on a file that needs a look: the first thing to check,
 * and how many others are waiting in the receipt. Null when nothing was flagged.
 */
export function needsALook(lines: ReceiptItem[]): string | null {
  const warnings = lines.filter((line) => line.tone === 'warn')
  const first = warnings[0]
  if (!first) return null
  // Backend warnings arrive as whole sentences; receipt labels do not. Strip the stop either way
  // so the joined sentence never reads "…left empty., and 2 more".
  const head = (first.amount ? `${first.label}: ${first.amount}` : first.label).replace(/\.$/, '')
  return warnings.length === 1 ? `${head}.` : `${head}, and ${warnings.length - 1} more to check.`
}

/** The line above the tabs: what is loaded, in four counts. Zero counts are left out, not written as "0". */
export function overviewLine(catalog: Catalog): string {
  const tables = catalog.tables.filter((table) => !table.is_view)
  const links = catalog.relationships.filter((link) => link.status !== 'rejected').length
  const views = catalog.unions.filter((union) => union.status !== 'rejected').length
  const hidden = tables.reduce((total, table) => total + table.health.pii_columns.length, 0)
  const parts = [count(tables.length, 'table')]
  if (links) parts.push(count(links, 'link'))
  if (views) parts.push(count(views, 'combined view'))
  if (hidden) parts.push(`${count(hidden, 'personal-data column')} hidden`)
  return parts.join(', ')
}

/** Whole percent, rounded down. The epsilon undoes float noise: 0.29 * 100 is 28.999999999999996. */
const wholePercent = (fraction: number): number => Math.floor(fraction * 100 + 1e-9)

/** Turns a SQL table name into what the analyst calls it (the file). Supplied by the caller so this file stays import-free. */
type TableNamer = (table: string) => string

/** A link the analyst can read: the two files for a button's name, and the sentence itself. */
export interface LinkLine {
  /** "employees.csv and Salary_Register_2025.xlsx" — for "Remove the link between …". */
  pair: string
  sentence: string
}

/**
 * A detected link as one sentence: which files, which column, and how well they match.
 *
 * The match quoted is the better of the two directions, because that is the side the backend uses
 * to switch a link on, and because in a healthy link every child row finds its parent while many
 * parents have no child: a bonus sheet that covers a quarter of the staff is a sound link, and
 * "25% match" would read as a broken one. Rounded down, so 99.6% never shows as 100%.
 */
export function linkLine(link: Relationship, name: TableNamer): LinkLine {
  const [left, right] = [name(link.left_table), name(link.right_table)]
  const on = link.left_column === link.right_column ? link.left_column : `${link.left_column} and ${link.right_column}`
  const leftIsBetter = link.match_left >= link.match_right
  const [from, to] = leftIsBetter ? [left, right] : [right, left]
  const matched = wholePercent(leftIsBetter ? link.match_left : link.match_right)
  // Many-to-many is the one shape that can silently double a total, so it is said out loud.
  const repeats = link.cardinality === 'N:M' ? ' Rows repeat on both sides, so totals across this link can be counted more than once.' : ''
  return {
    pair: `${left} and ${right}`,
    sentence: `${left} and ${right} are linked on ${on}. ${matched}% of rows in ${from} have a match in ${to}.${repeats}`,
  }
}

/** A combined view as one sentence: nobody uploaded it, so it says where it came from. */
export function unionLine(union: UnionView, name: TableNamer): LinkLine {
  const files = union.tables.map(name)
  const pair = files.length < 2 ? files.join('') : `${files.slice(0, -1).join(', ')} and ${files[files.length - 1]}`
  return { pair, sentence: `${pair} have the same columns, so a question that spans them reads one combined view.` }
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
