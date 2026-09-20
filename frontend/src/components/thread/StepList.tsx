// The live step list shown instead of a spinner: people trust a wait they can read. It stays
// open while the question runs, then folds into one line so the answer leads the turn.
import type { StepEvent } from '../../types'
import { STAGE_LABELS, summarizeSteps } from './steps'

const MARK: Record<StepEvent['status'], { glyph: string; tone: string; spoken: string }> = {
  started: { glyph: '•', tone: 'text-accent animate-pulse', spoken: 'In progress' },
  ok: { glyph: '✓', tone: 'text-good', spoken: 'Done' },
  warn: { glyph: '!', tone: 'text-warn', spoken: 'Warning' },
  failed: { glyph: '✕', tone: 'text-bad', spoken: 'Failed' },
}
const HALTED = { glyph: '–', tone: 'text-ink-faint', spoken: 'Not finished' }

export default function StepList({ steps, running }: { steps: StepEvent[]; running: boolean }) {
  if (!running && steps.length === 0) return null
  return (
    <details open={running} className="text-sm">
      <summary className="cursor-pointer text-ink-soft select-none">{running ? 'Working on it' : `How it went: ${summarizeSteps(steps)}`}</summary>
      <ol aria-live="polite" className="mt-2 space-y-1.5 border-l border-line pl-3">
        {steps.map((step, i) => {
          if (step.stage === 'done') return null
          // A step still "started" after the run ended was cut short (stopped or connection lost).
          // A status or stage this build does not know (a newer server) is shown plainly rather
          // than crashing the page: there is no error boundary above the thread.
          const cutShort = step.status === 'started' && !running
          const mark = cutShort ? HALTED : (MARK[step.status] ?? HALTED)
          return (
            <li key={i} className="flex gap-2">
              <span aria-hidden="true" className={`w-3 shrink-0 text-center font-semibold ${mark.tone}`}>
                {mark.glyph}
              </span>
              <span className="min-w-0 break-words">
                <span className="sr-only">{mark.spoken}: </span>
                <span className="text-ink">{STAGE_LABELS[step.stage] ?? step.stage}</span>
                {step.detail && <span className="text-ink-soft">: {step.detail}</span>}
              </span>
            </li>
          )
        })}
        {running && steps.length === 0 && <li className="animate-pulse text-ink-soft">Starting</li>}
      </ol>
    </details>
  )
}
