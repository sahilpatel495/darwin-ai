// The ticked lines under an answer (§6.4). Generated from the answer, never hard-coded: a tick
// beside a sentence is a claim, so every line here has to be true of this particular answer.
//
// A cross-check disagreement is deliberately absent: it is a red banner above the chart, never
// a tick. Only a real answer gets proof lines — a clarifying question, a refusal or an error
// computed nothing, and "computed by a database from your files" would be a lie.
//
// Only `import type` here: the tests load this file directly with `node --test`.

import type { Answer } from '../../types'

export interface ProofLine {
  /** The component decides what a line carries beside its words: a "?" or the link to the working. */
  id: 'computed' | 'crosscheck' | 'definition' | 'privacy'
  text: string
}

/** "attrition rate", "attrition rate and headcount", "a, b and c". */
const sentenceList = (names: string[]): string =>
  names.length < 2 ? (names[0] ?? '') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`

export function proofLines(answer: Answer, metricName: (key: string) => string): ProofLine[] {
  if (answer.kind !== 'answer') return []
  const { cross_check, metrics_used } = answer.work
  const lines: ProofLine[] = [{ id: 'computed', text: 'Computed by a database from your files' }]
  if (cross_check.status === 'agreed') {
    lines.push({ id: 'crosscheck', text: 'A second AI model wrote its own query and got the same result' })
  }
  if (metrics_used.length > 0) {
    lines.push({ id: 'definition', text: `Used your agreed definition of ${sentenceList(metrics_used.map(metricName))}` })
  }
  // Always last: it is the promise the whole product rests on.
  lines.push({ id: 'privacy', text: 'No rows or personal data were sent to the AI' })
  return lines
}
