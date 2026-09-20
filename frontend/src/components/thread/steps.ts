// Pipeline steps as the analyst reads them (§11). The backend streams StepEvents while a question
// runs; this module names the stages in plain words, folds the stream into a list, and turns that
// list into the timeline the "Working on it" card draws.
//
// No runtime imports on purpose: the tests load this file directly with `node --test`.

import type { ProgressStep, StepState } from '../ui'
import type { Stage, StepEvent } from '../../types'

export const STAGE_LABELS: Record<Exclude<Stage, 'done'>, string> = {
  understand: 'Understanding the question',
  generate: 'Writing the query',
  guard: 'Checking the query is safe',
  execute: 'Running it on your data',
  repair: 'Fixing the query',
  verify: 'Double-checking with a second AI model',
  chart: 'Choosing a chart',
  narrate: 'Writing the answer',
}

/** The steps every run takes, in order, so the card shows what is still coming rather than
 *  growing a line at a time. Repair is spliced in only when one happens. */
const PLAN: Exclude<Stage, 'done' | 'repair'>[] = ['understand', 'generate', 'guard', 'execute', 'verify', 'chart', 'narrate']

/** The server's own sentence when every free model is rate limited. It is a wait, not a failure,
 *  so the step turns amber and counts down instead of going red (§11). */
const BUSY = 'All the free AI models are busy'

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

/** How long the models asked us to wait, from "…Retrying in 12 seconds." Null when it is not
 *  that kind of warning. */
export const waitSeconds = (detail: string): number | null => {
  if (!detail.startsWith(BUSY)) return null
  const match = /(\d+) second/.exec(detail)
  return match ? Number(match[1]) : null
}

/** The model that wrote the query, from "openai/gpt-oss-120b wrote a 3-step plan". Shown as a
 *  chip in the card header, so the analyst knows who is doing the writing while it happens. */
export function modelName(steps: StepEvent[]): string | null {
  const generate = steps.find((step) => step.stage === 'generate' && step.status === 'ok')
  return /^(\S+) wrote a/.exec(generate?.detail ?? '')?.[1] ?? null
}

function stateOf(event: StepEvent | undefined, running: boolean): StepState {
  if (!event) return 'pending'
  // A step still "started" after the run ended was cut short — stopped, or the connection closed.
  if (event.status === 'started') return running ? 'active' : 'pending'
  if (event.status === 'ok') return 'done'
  if (event.status === 'warn') return waitSeconds(event.detail) === null ? 'warn' : 'waiting'
  if (event.status === 'failed') return 'failed'
  return 'pending' // a status this build does not know (a newer server)
}

/**
 * The folded events as the timeline the card draws: one row per stage, showing that stage's
 * latest event. A guard that rejected a query and then passed is one row that ends green, with
 * the rejection told by the "Fixing the query" row between them.
 */
export function toProgress(steps: StepEvent[], running: boolean): ProgressStep[] {
  const latest = new Map<string, StepEvent>()
  for (const step of steps) if (step.stage !== 'done') latest.set(step.stage, step)

  const order: string[] = [...PLAN]
  if (latest.has('repair')) order.splice(order.indexOf('execute'), 0, 'repair')
  // A stage from a newer server is shown at the end rather than dropped.
  for (const stage of latest.keys()) if (!order.includes(stage)) order.push(stage)

  const rows = order.map((stage): ProgressStep => {
    const event = latest.get(stage)
    return {
      id: stage,
      label: STAGE_LABELS[stage as Exclude<Stage, 'done'>] ?? stage,
      detail: event?.detail ? tidyDetail(event.detail) : undefined,
      state: stateOf(event, running),
    }
  })

  // The server announces only some stages as they start, so between two events every row can be
  // done or pending — a card with nothing moving, while the thing it promises is that you can
  // watch each check happen (§11). Whatever comes next is what is happening now, so it breathes.
  // Not when a step is waiting on a busy model or has failed: then the run really is stopped
  // there, and that row is the one to look at.
  const held = rows.some((row) => row.state === 'active' || row.state === 'waiting' || row.state === 'failed')
  const next = rows.findIndex((row) => row.state === 'pending')
  if (running && !held && next >= 0) rows[next] = { ...rows[next], state: 'active' }
  return rows
}

const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? '' : 's'}`

/** The one line the card folds into once the answer has arrived (§11): "Answered in 3.2 s,
 *  7 checks", and what went wrong when something did. `ms` is null for a turn restored from
 *  history, which was timed in a session that has since been closed. */
export function summarizeRun(steps: StepEvent[], ms: number | null): string {
  const checks = steps.filter((step) => step.stage !== 'done').length
  const warnings = steps.filter((step) => step.status === 'warn').length
  const failed = steps.filter((step) => step.status === 'failed').length
  const head = ms !== null && ms >= 100 ? `Answered in ${(ms / 1000).toFixed(1)} s, ${plural(checks, 'check')}` : `Worked through ${plural(checks, 'check')}`
  return [head, warnings > 0 && plural(warnings, 'warning'), failed > 0 && `${failed} failed`].filter(Boolean).join(', ')
}
