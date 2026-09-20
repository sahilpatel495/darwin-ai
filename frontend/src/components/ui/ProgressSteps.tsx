import type { ReactNode } from 'react'
import Check from './Check'
import { cx } from './cx'

export type StepState = 'pending' | 'active' | 'done' | 'warn' | 'failed' | 'waiting'

export interface ProgressStep {
  id: string
  /** What is happening, in the analyst's words: "Checking the query is safe". */
  label: string
  /** The live line under the label, e.g. "Read-only, 2 tables, 3 columns". */
  detail?: ReactNode
  state: StepState
  /** A model name, a timing — one short fact, shown as a chip on the right. */
  meta?: string
}

export interface ProgressStepsProps {
  steps: ProgressStep[]
  className?: string
}

// The rail below a step is coloured by that step's own outcome, so the eye can follow how far
// the run got and where it went wrong without reading a word.
const RAIL: Record<StepState, string> = {
  pending: 'bg-line-soft',
  active: 'bg-line-soft',
  done: 'bg-green',
  warn: 'bg-amber',
  failed: 'bg-red',
  waiting: 'bg-amber',
}

// Every state says itself in words as well as colour: the marker's aria-label is read aloud.
const SPOKEN: Record<StepState, string> = {
  pending: 'Not started',
  active: 'Running',
  done: 'Done',
  warn: 'Done with a caveat',
  failed: 'Failed',
  waiting: 'Waiting',
}

function Marker({ state }: { state: StepState }) {
  if (state === 'done') return <Check size={18} animate title={SPOKEN.done} />

  const dot = (className: string, inner?: ReactNode) => (
    <span role="img" aria-label={SPOKEN[state]} className={cx('inline-flex size-[18px] shrink-0 items-center justify-center rounded-pill', className)}>
      {inner}
    </span>
  )

  if (state === 'active') return dot('bg-blue-soft', <span aria-hidden className="size-2 rounded-pill bg-blue animate-breathe" />)
  if (state === 'waiting') return dot('bg-amber-soft', <span aria-hidden className="size-2 rounded-pill bg-amber" />)
  if (state === 'warn') return dot('bg-amber text-[11px] leading-none font-bold text-black', <span aria-hidden>!</span>)
  if (state === 'failed') return dot('bg-red text-[11px] leading-none font-bold text-white', <span aria-hidden>×</span>)
  return dot('border-2 border-line')
}

/**
 * The thinking, made visible (§11). One row per check, marked as it happens: a breathing dot
 * while it runs with a light sweeping across the row, a check that pops when it finishes, amber
 * when a model is busy and we are waiting.
 *
 * It is a list, not a status widget: every state is in words too, so the timeline reads correctly
 * aloud and with animation switched off.
 */
export default function ProgressSteps({ steps, className }: ProgressStepsProps) {
  return (
    <ol className={cx('relative', className)}>
      {steps.map((step, i) => (
        <li key={step.id} className="relative flex gap-3 pb-3 last:pb-0">
          {/* The rail between markers: drawn on every row but the last, so the eye follows down. */}
          {i < steps.length - 1 && <span aria-hidden className={cx('absolute top-[22px] bottom-0 left-[8px] w-0.5 rounded-pill', RAIL[step.state])} />}
          <span className="relative z-10 mt-0.5">
            <Marker state={step.state} />
          </span>
          <div
            className={cx(
              'relative min-w-0 flex-1 overflow-hidden rounded-input px-2 py-0.5',
              step.state === 'active' && 'shimmer bg-blue-soft/60',
              step.state === 'waiting' && 'bg-amber-soft',
            )}
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-3">
              <p className={cx('type-body', step.state === 'pending' ? 'text-ink-3' : 'font-medium text-ink')}>{step.label}</p>
              {step.meta && <span className="rounded-pill bg-fill px-2 py-0.5 type-micro text-ink-2">{step.meta}</span>}
            </div>
            {step.detail && <p className="mt-0.5 type-small text-ink-2">{step.detail}</p>}
          </div>
        </li>
      ))}
    </ol>
  )
}
