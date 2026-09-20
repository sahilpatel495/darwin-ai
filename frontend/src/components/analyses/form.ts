// The words and the shapes behind the guided analyses (§14).
//
// Why pure: the sentence under the pickers is the promise the analyst reads before they run
// anything ("Average Annual CTC by Department"). If it says something other than what the
// database is about to compute, the whole no-AI half is untrustworthy — so it is tested without
// a browser (form.test.mjs). Only `import type` here: Node runs those tests by stripping types.

import type { AnalysisInput, AnalysisKind, ColumnChoice, ColumnKind } from '../../types'

/** Shown where a required column has not been chosen yet. */
export const MISSING = '…'

/** The column choices for one input, grouped by the file they came from: one `<optgroup>` each. */
export interface ColumnGroup {
  table: string
  columns: ColumnChoice[]
}

/** Only the columns whose kind this input accepts, in catalog order, grouped by file. */
export function groupedColumns(input: AnalysisInput, columns: ColumnChoice[]): ColumnGroup[] {
  const groups: ColumnGroup[] = []
  for (const column of columns) {
    if (!input.accepts.includes(column.kind)) continue
    const group = groups.find((g) => g.table === column.table_label)
    if (group) group.columns.push(column)
    else groups.push({ table: column.table_label, columns: [column] })
  }
  return groups
}

// The analyst's word for each kind of column. They never see "measure" or "category".
const KIND_WORD: Record<ColumnKind, string> = { measure: 'number', category: 'text', date: 'date', text: 'text' }

/** "No date columns in your files" — said in the picker when nothing in the files fits. */
export function noColumnsLine(input: AnalysisInput): string {
  const words = [...new Set(input.accepts.map((kind) => KIND_WORD[kind]))]
  return `No ${words.join(' or ')} columns in your files`
}

/** §14: the first choice of every option is preselected, so Run works without touching them. */
export const defaultOptions = (kind: AnalysisKind): Record<string, string> =>
  Object.fromEntries(kind.options.map((option) => [option.key, option.choices[0] ?? '']))

/** Every required input has a column. Optional inputs may stay empty. */
export const isComplete = (kind: AnalysisKind, inputs: Record<string, string>): boolean =>
  kind.inputs.every((input) => input.optional || Boolean(inputs[input.key]))

// How each way of combining reads in a sentence. A sum is silent on purpose: "Gross by month",
// not "Total gross by month" — the column already is the total once it is added up, and the
// server's own examples read that way.
const AGGREGATE: Record<string, string> = {
  sum: '',
  average: 'Average',
  count: 'Number of',
  median: 'Median',
  min: 'Lowest',
  max: 'Highest',
}

const plural = (word: string): string => (word === MISSING || word.endsWith('s') ? word : `${word}s`)
const capitalise = (line: string): string => line.charAt(0).toUpperCase() + line.slice(1)

/**
 * What will run, as one line the analyst could have said out loud.
 *
 * `labels` maps a column ref to the words for it (the caller humanises them, because this file
 * cannot import a value). An unknown analysis kind — the server may add one before this screen
 * does — still gets a truthful line from its name and the chosen columns.
 */
export function previewSentence(
  kind: AnalysisKind,
  inputs: Record<string, string>,
  options: Record<string, string>,
  labels: Record<string, string>,
): string {
  const chosen = (key: string): string => {
    const ref = inputs[key]
    return ref ? (labels[ref] ?? ref) : ''
  }
  const need = (key: string): string => chosen(key) || MISSING

  const word = AGGREGATE[options.aggregate ?? ''] ?? ''
  const lead = word ? `${word} ` : '' // starts the sentence: "Average CTC by department"
  const inner = word ? `${word.toLowerCase()} ` : '' // sits inside it: "Share of average CTC"
  const measure = need('measure')
  const by = need('by')
  const grain = options.grain || 'month'
  const separate = chosen('by') // optional on a trend and on a change

  switch (kind.key) {
    case 'breakdown':
      return capitalise(`${lead}${measure} by ${by}`)
    case 'trend':
      return capitalise(`${lead}${measure} by ${grain}${separate ? `, with a line for each ${separate}` : ''}`)
    case 'top_n':
      return capitalise(`Top ${options.top_n || '5'} ${plural(by)} by ${inner}${measure}`)
    case 'distribution':
      return capitalise(`How ${measure} is spread`)
    case 'share':
      return capitalise(`Share of ${inner}${measure} by ${by}`)
    case 'pivot':
      return capitalise(`${lead}${measure} by ${by} and ${need('across')}`)
    case 'correlation':
      return capitalise(`${measure} against ${need('measure_b')}`)
    case 'change':
      return capitalise(`${lead}${measure}, this ${grain} against the one before${separate ? `, split by ${separate}` : ''}`)
    case 'outliers':
      return capitalise(`Unusual ${measure} values`)
    default: {
      const filled = kind.inputs.map((input) => chosen(input.key)).filter(Boolean)
      return filled.length > 0 ? `${kind.name}: ${filled.join(', ')}` : kind.name
    }
  }
}
