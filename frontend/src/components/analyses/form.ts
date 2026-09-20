// The words and the shapes behind the sentence builder (§8).
//
// Why pure: the sentence is the promise the analyst reads before they run anything ("Average
// Annual CTC by Department"). If it says something other than what the database is about to
// compute, the whole no-AI half is untrustworthy — so it is tested without a browser
// (form.test.mjs). Only `import type` here: Node runs those tests by stripping types.
//
// One template per kind, in `sentenceParts`. The builder renders those parts with a picker in
// each gap; `previewSentence` renders the same parts as a line of words, and that line is the
// title of the run. One source, so the promise and the title can never drift apart.

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

/** §8: the first choice of every option is preselected, so Run works without touching them. */
export const defaultOptions = (kind: AnalysisKind): Record<string, string> =>
  Object.fromEntries(kind.options.map((option) => [option.key, option.choices[0] ?? '']))

/**
 * Every required input has a column, and every option that has no fixed choices — the two groups
 * of "Compare two groups" — has a value. Optional inputs may stay empty.
 */
export const isComplete = (kind: AnalysisKind, inputs: Record<string, string>, options: Record<string, string> = {}): boolean =>
  kind.inputs.every((input) => input.optional || Boolean(inputs[input.key])) &&
  kind.options.every((option) => option.choices.length > 0 || Boolean(options[option.key]))

/**
 * The values the two group pickers offer: the distinct values of the first chosen column that
 * holds groups. The server fills `ColumnChoice.values` for exactly those columns and checks the
 * answer again on the way in, so the picker can only offer what the column really contains.
 */
export function groupValues(kind: AnalysisKind, inputs: Record<string, string>, columns: ColumnChoice[]): string[] {
  for (const input of kind.inputs) {
    const column = columns.find((choice) => choice.ref === inputs[input.key])
    if (column?.kind === 'category') return column.values
  }
  return []
}

/** "First group (one of the chosen column's values)" is a sentence, not a label. */
export const shortLabel = (label: string): string => label.split(' (')[0]

/**
 * Which gap a refusal from the server (422) is about, found by the label it names: "Break down
 * needs a column for “Split by”." The server writes those sentences for the person looking at
 * this screen, so they quote the labels this screen shows. Null when it names none of them, and
 * then the message belongs beside Run, where it is still the answer to what was just pressed.
 */
export function slotForMessage(message: string, kind: AnalysisKind): { of: 'input' | 'option'; key: string } | null {
  const said = message.toLowerCase()
  const input = kind.inputs.find((slot) => said.includes(slot.label.toLowerCase()))
  if (input) return { of: 'input', key: input.key }
  const option = kind.options.find((slot) => said.includes(shortLabel(slot.label).toLowerCase()))
  return option ? { of: 'option', key: option.key } : null
}

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

/** A gap in the sentence: a column picker, or one of the chosen column's own values. */
export interface SentenceSlot {
  /** `input` is a column; `values` is a value of the column already chosen (compare's groups). */
  of: 'input' | 'values'
  key: string
  /** Words that belong to this gap and disappear with it when it is optional and empty. */
  lead?: string
  optional?: boolean
  /** "Locations", not "Location": top and bottom ranks a group. */
  plural?: boolean
}

export type SentencePart = string | SentenceSlot

/**
 * The shape of one analysis as a sentence: plain words and the gaps in between.
 *
 * The ways of combining (`aggregate`, `grain`, `top_n`) are already words here rather than gaps —
 * they are chosen on the pill tabs under the sentence, and reading them back inside it is what
 * makes those pills feel connected to what will run.
 *
 * A kind this screen has never seen — the server may add one before this file does — still gets
 * a truthful sentence from its name and its own inputs.
 */
export function sentenceParts(kind: AnalysisKind, options: Record<string, string>): SentencePart[] {
  const word = AGGREGATE[options.aggregate ?? ''] ?? ''
  const lead = word ? `${word} ` : '' // starts the sentence: "Average CTC by department"
  const inner = word ? `${word.toLowerCase()} ` : '' // sits inside it: "Share of average CTC"
  const grain = options.grain || 'month'
  const measure: SentenceSlot = { of: 'input', key: 'measure' }
  const by: SentenceSlot = { of: 'input', key: 'by' }

  switch (kind.key) {
    case 'breakdown':
      return [lead, measure, ' by ', by]
    case 'trend':
      return [lead, measure, ` by ${grain}`, { ...by, optional: true, lead: ', with a line for each ' }]
    case 'top_n':
      return [`Top ${options.top_n || '5'} `, { ...by, plural: true }, ` by ${inner}`, measure]
    case 'distribution':
      return ['How ', measure, ' is spread']
    case 'share':
      return [`Share of ${inner}`, measure, ' by ', by]
    case 'pivot':
      return [lead, measure, ' by ', by, ' and ', { of: 'input', key: 'across' }]
    case 'correlation':
      return [measure, ' against ', { of: 'input', key: 'measure_b' }]
    case 'change':
      return [lead, measure, `, this ${grain} against the one before`, { ...by, optional: true, lead: ', split by ' }]
    case 'outliers':
      return ['Unusual ', measure, ' values']
    case 'compare':
      return [lead, measure, ': ', { of: 'values', key: 'group_a' }, ' against ', { of: 'values', key: 'group_b' }, ' in ', by]
    default:
      return [
        kind.name,
        ...kind.inputs.map((input, i): SentenceSlot => ({ of: 'input', key: input.key, optional: true, lead: i === 0 ? ': ' : ', ' })),
      ]
  }
}

/**
 * The columns the sentence has no gap for — a trend's and a change's date column, which the
 * sentence names by its grain ("by month") rather than by its column. The builder puts a picker
 * for each of these under the sentence, beside the option pills, so nothing an analysis needs is
 * out of reach; an analysis this screen has never seen gets its pickers the same way.
 */
export function unmentionedInputs(kind: AnalysisKind, options: Record<string, string>): AnalysisInput[] {
  const named = new Set(
    sentenceParts(kind, options).flatMap((part) => (typeof part === 'string' || part.of !== 'input' ? [] : [part.key])),
  )
  return kind.inputs.filter((input) => !named.has(input.key))
}

/** What one gap reads as right now: the chosen words, or a mark where a choice is still owed. */
export function fillSlot(slot: SentenceSlot, inputs: Record<string, string>, options: Record<string, string>, labels: Record<string, string>): string {
  const chosen = slot.of === 'values' ? (options[slot.key] ?? '') : (inputs[slot.key] ? (labels[inputs[slot.key]] ?? inputs[slot.key]) : '')
  if (!chosen) return slot.optional ? '' : MISSING
  return slot.plural ? plural(chosen) : chosen
}

/**
 * What will run, as one line the analyst could have said out loud — the title of the result and
 * the label of the chip that puts it back.
 *
 * `labels` maps a column ref to the words for it (the caller humanises them, because this file
 * cannot import a value).
 */
export function previewSentence(
  kind: AnalysisKind,
  inputs: Record<string, string>,
  options: Record<string, string>,
  labels: Record<string, string>,
): string {
  const line = sentenceParts(kind, options)
    .map((part) => {
      if (typeof part === 'string') return part
      const filled = fillSlot(part, inputs, options, labels)
      return filled ? `${part.lead ?? ''}${filled}` : ''
    })
    .join('')
  return capitalise(line)
}
