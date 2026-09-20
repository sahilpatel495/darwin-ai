// The route an answer took, as six nodes (§12). It opens "How I got this" because the shape of
// the pipeline is the argument: the model writes a query, the database computes, a second model
// checks. Reading it should take two seconds; the sections below it are for the doubting reader.
//
// Every node's state is read from the answer's own `work`, never assumed: a run where the safety
// check rejected a query says so, and one where the second model was never reached does not
// claim it agreed.
//
// Only `import type` here: the tests load this file directly with `node --test`.

import type { Work } from '../../types'

export type FlowTone = 'done' | 'warn' | 'failed' | 'idle'

export interface FlowNode {
  id: 'question' | 'query' | 'safety' | 'data' | 'crosscheck' | 'answer'
  label: string
  /** One short fact under the label: the model's name, how many rows were read. */
  note: string | null
  tone: FlowTone
  /** Times the query came back to be rewritten. Drawn as a loop on the node. */
  loops: number
}

const CROSS_CHECK: Record<Work['cross_check']['status'], { tone: FlowTone; note: string }> = {
  agreed: { tone: 'done', note: 'Agreed' },
  disagreed: { tone: 'failed', note: 'Disagreed' },
  unavailable: { tone: 'idle', note: 'Could not be reached' },
  skipped: { tone: 'idle', note: 'Not run' },
}

const plural = (n: number, word: string): string => `${n.toLocaleString('en-IN')} ${word}${n === 1 ? '' : 's'}`

export function flowNodes(work: Work): FlowNode[] {
  const model = work.payloads.find((payload) => payload.purpose === 'generate')?.model ?? work.attempts[0]?.model ?? null
  // The first attempt is the query itself; every attempt after it is a rewrite.
  const loops = Math.max(0, work.attempts.length - 1)
  const rejected = work.attempts.some((attempt) => attempt.reason === 'guard_rejected')
  const cross = CROSS_CHECK[work.cross_check.status] ?? CROSS_CHECK.skipped
  return [
    { id: 'question', label: 'Your question', note: null, tone: 'done', loops: 0 },
    { id: 'query', label: 'Query written', note: model, tone: 'done', loops },
    {
      id: 'safety',
      label: 'Safety check',
      note: rejected ? 'Rejected once, then rewritten' : 'Read-only',
      tone: rejected ? 'warn' : 'done',
      loops: 0,
    },
    {
      id: 'data',
      label: 'Your data',
      note: work.rows_scanned > 0 ? `${plural(work.rows_scanned, 'row')} read` : 'Computed by the database',
      tone: 'done',
      loops: 0,
    },
    { id: 'crosscheck', label: 'Second model', note: cross.note, tone: cross.tone, loops: 0 },
    { id: 'answer', label: 'Answer', note: work.cached ? 'From memory' : null, tone: 'done', loops: 0 },
  ]
}
