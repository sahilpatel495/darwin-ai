// The briefing offers the server's suggested questions in four groups (§6.3). The server sends a
// flat list, so the grouping happens here, with a deliberately small classifier:
//
//   a question about time is a trend; one that names columns from two different files is across
//   files; one that names a measure from your glossary is an HR measure; everything else is a
//   total or a breakdown.
//
// That is the whole rule, and it is the rule the author can say out loud in a demo. It is pure and
// tested (questions.test.mjs); only `import type`, because Node runs those tests by stripping types.

import type { Catalog } from '../../types'

export type QuestionKind = 'totals' | 'trends' | 'across' | 'measures'

export const KIND_TITLE: Record<QuestionKind, string> = {
  totals: 'Totals and breakdowns',
  trends: 'Trends',
  across: 'Across files',
  measures: 'HR measures',
}

/** Lowercased, punctuation to spaces, padded — so a match is always on whole words. */
const normalize = (text: string): string => ` ${text.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()} `

const contains = (text: string, phrase: string): boolean => phrase !== '' && text.includes(` ${phrase} `)

/** A question about a period, a rate of change, or a series over time. */
const TIME = /\b(trend|trends|over time|month|months|monthly|quarter|quarters|quarterly|year|years|yearly|annual|annually|since|growth|grew|grown|changed|changing)\b/

export interface QuestionWords {
  /** Every metric name and other name from the glossary, normalized. */
  metrics: string[]
  /** Word to the one file it belongs to. A word two files share proves nothing, so it is left out. */
  byFile: Map<string, string>
}

/** The vocabulary of this catalog: what the analyst can say that points at one file, or at a measure. */
export function questionWords(catalog: Catalog): QuestionWords {
  const metrics = catalog.glossary.flatMap((metric) => [metric.name, ...metric.synonyms]).map((name) => normalize(name).trim())

  // Combined views repeat their sources' columns, so they would make every shared word ambiguous
  // twice over; only uploaded files vote.
  const owners = new Map<string, Set<string>>()
  for (const table of catalog.tables.filter((t) => !t.is_view)) {
    const phrases = [normalize(table.source_file), ...table.columns.map((column) => normalize(column.label))].flatMap((phrase) => {
      const words = phrase.trim().split(' ')
      return words.length > 1 ? [phrase.trim(), ...words] : words
    })
    for (const phrase of phrases) {
      // Three letters is the shortest real word here (ctc, lop); a bare number is a year, not a name.
      if (phrase.length < 3 || /^\d+$/.test(phrase)) continue
      const seen = owners.get(phrase) ?? new Set<string>()
      seen.add(table.name)
      owners.set(phrase, seen)
    }
  }

  const byFile = new Map<string, string>()
  for (const [phrase, tables] of owners) {
    const only = [...tables][0]
    if (tables.size === 1 && only) byFile.set(phrase, only)
  }
  return { metrics, byFile }
}

export function classifyQuestion(question: string, words: QuestionWords): QuestionKind {
  const text = normalize(question)
  if (TIME.test(text)) return 'trends'

  const files = new Set<string>()
  for (const [phrase, table] of words.byFile) if (contains(text, phrase)) files.add(table)
  if (files.size > 1) return 'across'

  if (words.metrics.some((metric) => contains(text, metric))) return 'measures'
  return 'totals'
}

export interface QuestionGroup {
  kind: QuestionKind
  title: string
  questions: string[]
}

/** The suggestions in reading order, with empty groups left out rather than shown as empty. */
export function groupQuestions(catalog: Catalog): QuestionGroup[] {
  const words = questionWords(catalog)
  const found = new Map<QuestionKind, string[]>()
  for (const question of catalog.suggested_questions) {
    const kind = classifyQuestion(question, words)
    found.set(kind, [...(found.get(kind) ?? []), question])
  }
  const order: QuestionKind[] = ['totals', 'trends', 'across', 'measures']
  return order.filter((kind) => found.has(kind)).map((kind) => ({ kind, title: KIND_TITLE[kind], questions: found.get(kind) ?? [] }))
}
