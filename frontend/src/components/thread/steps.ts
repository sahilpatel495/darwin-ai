// Pipeline steps as the user reads them. The backend streams StepEvents while a question runs;
// this module names the stages in plain words and folds the stream into a list.
//
// No runtime imports on purpose: the tests load this file directly with `node --test`.

import type { Stage, StepEvent } from '../../types'

export const STAGE_LABELS: Record<Exclude<Stage, 'done'>, string> = {
  understand: 'Understanding the question',
  generate: 'Writing SQL',
  guard: 'Checking the SQL is safe',
  execute: 'Running the query',
  repair: 'Repairing',
  verify: 'Verifying the result',
  chart: 'Choosing a chart',
  narrate: 'Writing the answer',
}

/** Adds one event to the list. A "started" step is replaced by its own result so a stage shows
 *  once per run of it; a stage that runs again later (guard after a repair) is listed again,
 *  because that second check is exactly what the user should see. Returns a new array.
 *
 *  The open step is looked for anywhere in the list, not only at the end: verification starts,
 *  the chart and the wording finish while the second model is still working, and only then does
 *  verification report. Matching just the last step left a "Verifying: not finished" line on
 *  every successful answer. */
export function foldStep(steps: StepEvent[], event: StepEvent): StepEvent[] {
  if (event.stage === 'done') return steps
  const open = steps.map((s) => s.stage === event.stage && s.status === 'started').lastIndexOf(true)
  return open < 0 ? [...steps, event] : steps.map((s, i) => (i === open ? event : s))
}

/** The server writes counts it has not pluralised as "2 table(s)"; people read "2 tables". */
export const tidyDetail = (detail: string): string =>
  detail.replace(/\b(\d[\d,]*) (\w+)\(s\)/g, (_, n: string, noun: string) => `${n} ${noun}${n === '1' ? '' : 's'}`)

const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? '' : 's'}`

/** The one line the step list folds into once the answer has arrived (§6.4):
 *  "Worked through 9 steps", and what went wrong when something did. */
export function summarizeSteps(steps: StepEvent[]): string {
  const warnings = steps.filter((s) => s.status === 'warn').length
  const failed = steps.filter((s) => s.status === 'failed').length
  return [`Worked through ${plural(steps.length, 'step')}`, warnings > 0 && plural(warnings, 'warning'), failed > 0 && `${failed} failed`].filter(Boolean).join(', ')
}
