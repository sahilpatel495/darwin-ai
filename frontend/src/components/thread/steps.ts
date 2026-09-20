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
 *  because that second check is exactly what the user should see. Returns a new array. */
export function foldStep(steps: StepEvent[], event: StepEvent): StepEvent[] {
  if (event.stage === 'done') return steps
  const last = steps[steps.length - 1]
  const finishesLast = last !== undefined && last.stage === event.stage && last.status === 'started'
  return finishesLast ? [...steps.slice(0, -1), event] : [...steps, event]
}

const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? '' : 's'}`

/** One line for the collapsed step list: "9 steps, 1 warning". */
export function summarizeSteps(steps: StepEvent[]): string {
  const warnings = steps.filter((s) => s.status === 'warn').length
  const failed = steps.filter((s) => s.status === 'failed').length
  return [plural(steps.length, 'step'), warnings > 0 && plural(warnings, 'warning'), failed > 0 && `${failed} failed`].filter(Boolean).join(', ')
}
