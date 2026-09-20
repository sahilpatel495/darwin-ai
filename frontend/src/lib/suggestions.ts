// The four questions on an empty Ask screen (§8), and the sheet of "more ideas" behind them.
//
// The server already suggests questions it knows the files can answer — those are the only ones
// certain not to end in "I could not find that column", so they come first and always. The role
// the analyst told us about decides the ORDER, because a payroll officer and a founder open the
// same workspace wanting different things. Role templates only fill a gap when the catalog gave
// us fewer than four.
//
// Pure and import-free, so suggestions.test.mjs runs it in Node.

export interface Suggestion {
  /** One or two words naming what the question is about: "Pay", "Attrition". */
  kind: string
  /** A `GlyphName` from components/graphics/Glyph. A string, so this file stays import-free. */
  glyph: string
  question: string
}

/** The role chips (§7). Settings and onboarding both offer exactly these. */
export const ROLES = ['HR analyst', 'HR business partner', 'Payroll', 'Finance', 'Founder', 'Other'] as const
export type Role = (typeof ROLES)[number]

/** What a question is about, decided by the words in it. First match wins, so the order matters:
 *  "how has headcount changed month by month" is about people, not about months. */
const KINDS: { key: string; kind: string; glyph: string; match: RegExp }[] = [
  { key: 'attrition', kind: 'Attrition', glyph: 'trend', match: /attrition|leaver|resign|exit|left the|turnover/i },
  { key: 'attendance', kind: 'Attendance', glyph: 'calendar', match: /attendance|absent|present|leave|late|overtime/i },
  { key: 'performance', kind: 'Performance', glyph: 'compare', match: /rating|review|performance|appraisal|score/i },
  { key: 'pay', kind: 'Pay', glyph: 'rupee', match: /pay|salary|ctc|compensation|payroll|bonus|cost|₹/i },
  { key: 'people', kind: 'People', glyph: 'people', match: /headcount|employee|people|joiner|hire|hiring|tenure|gender|diversity/i },
  { key: 'time', kind: 'Over time', glyph: 'trend', match: /month|quarter|year|trend|over time/i },
]

const OTHER = { key: 'other', kind: 'Breakdown', glyph: 'bars' }

/** What the question is about. Exported because the "more ideas" sheet groups by it. */
export function kindOf(question: string): { key: string; kind: string; glyph: string } {
  return KINDS.find((entry) => entry.match.test(question)) ?? OTHER
}

/** Which subjects each role reaches for first. Anything not listed sorts after the ones that are. */
const PREFERENCE: Record<string, string[]> = {
  'HR analyst': ['attrition', 'people', 'pay', 'performance'],
  'HR business partner': ['people', 'attrition', 'performance', 'attendance'],
  Payroll: ['pay', 'attendance', 'people'],
  Finance: ['pay', 'people', 'time'],
  Founder: ['people', 'pay', 'attrition'],
}
const DEFAULT_PREFERENCE = ['pay', 'people', 'attrition', 'time']

/**
 * Used only to top up a short list. They name the commonest HR columns rather than anything
 * clever, so the worst case is a clarifying question rather than a refusal.
 */
const TEMPLATES: Record<string, string[]> = {
  'HR analyst': ['What is the attrition rate this year?', 'How does average pay compare across departments?'],
  'HR business partner': ['How many people are in each department?', 'Which teams have grown the most this year?'],
  Payroll: ['What is the total gross pay this year?', 'How has monthly gross pay changed this year?'],
  Finance: ['What is the total gross pay by department?', 'What is the average cost per employee?'],
  Founder: ['How many people work here now?', 'How has headcount changed month by month?'],
  Other: ['How many people are in each department?', 'What is the total gross pay by department?'],
}

const rank = (key: string, order: string[]): number => {
  const at = order.indexOf(key)
  return at < 0 ? order.length : at
}

const normalise = (question: string) => question.trim().toLowerCase().replace(/\s+/g, ' ')

/**
 * The questions to offer, best first. `questions` is `catalog.suggested_questions`; `role` is what
 * the analyst chose about themselves, or null before they have said.
 */
export function suggestionsFor(questions: readonly string[], role: string | null, limit = 4): Suggestion[] {
  const order = PREFERENCE[role ?? ''] ?? DEFAULT_PREFERENCE
  const seen = new Set<string>()
  const pick = (question: string): Suggestion | null => {
    const text = question.trim()
    const key = normalise(text)
    if (!text || seen.has(key)) return null
    seen.add(key)
    const { kind, glyph } = kindOf(text)
    return { kind, glyph, question: text }
  }

  // How many questions about this subject have already been taken. Filled by the first sort and
  // read by the second, which is what turns a sorted list into a round-robin.
  const taken = new Map<string, number>()

  const fromCatalog = questions
    .map(pick)
    .filter((item): item is Suggestion => item !== null)
    .map((item, index) => ({ item, index, at: rank(kindOf(item.question).key, order), key: kindOf(item.question).key, round: 0 }))
    // First: by how much this role cares about the subject. The catalog's own order is kept inside
    // each subject, because the server put its best question for that subject first.
    .sort((a, b) => a.at - b.at || a.index - b.index)
    .map((entry) => {
      const round = taken.get(entry.key) ?? 0
      taken.set(entry.key, round + 1)
      return { ...entry, round }
    })
    // Then: one question from every subject before a second from any of them. Four cards that all
    // said "Pay" told the analyst this product answers one kind of question — and the sample's
    // catalog leads with five pay questions, so that is exactly what they got. The role still
    // decides which subject is offered first; it no longer decides all four.
    .sort((a, b) => a.round - b.round || a.at - b.at || a.index - b.index)
    .map((entry) => entry.item)

  if (fromCatalog.length >= limit) return fromCatalog.slice(0, limit)

  const filler = (TEMPLATES[role ?? ''] ?? TEMPLATES.Other).map(pick).filter((item): item is Suggestion => item !== null)
  return [...fromCatalog, ...filler].slice(0, limit)
}

/** The "More ideas" sheet: every question there is, under the subject it is about. */
export function groupSuggestions(questions: readonly string[], role: string | null): { kind: string; items: Suggestion[] }[] {
  // Every question the files can answer, in this role's order. The limit is the list itself, so
  // the sheet never pads with a template the catalog did not vouch for.
  const all = suggestionsFor(questions, role, questions.length || 4)
  const groups: { kind: string; items: Suggestion[] }[] = []
  for (const item of all) {
    const group = groups.find((entry) => entry.kind === item.kind)
    if (group) group.items.push(item)
    else groups.push({ kind: item.kind, items: [item] })
  }
  return groups
}
