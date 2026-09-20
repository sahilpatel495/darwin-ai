import type { ReactNode } from 'react'
import { cx } from './cx'

export interface BannerProps {
  /** `info` a quiet note · `warn` the app carried on · `error` the action failed. */
  tone: 'info' | 'warn' | 'error'
  /** What happened, in one sentence. */
  children: ReactNode
  /** What to do next. Leave it out when the sentence above already says. */
  nextStep?: ReactNode
  /** One control, usually the next step made clickable. */
  action?: ReactNode
  onDismiss?: () => void
  className?: string
}

// A 2px left rule in the tone colour, the way a ledger marks a queried line.
const TONE = {
  info: 'border-l-indigo bg-indigo-soft',
  warn: 'border-l-amber bg-amber-soft',
  error: 'border-l-red bg-red-soft',
} as const

/** What happened, then what to do. Never a status code, never an apology. */
export default function Banner({ tone, children, nextStep, action, onDismiss, className }: BannerProps) {
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cx(
        'flex flex-wrap items-start gap-x-4 gap-y-2 rounded-control rounded-l-none border-l-2 px-4 py-3',
        TONE[tone],
        className,
      )}
    >
      <p className="min-w-0 flex-1 type-body text-ink">
        <span className="font-medium whitespace-pre-line">{children}</span>
        {nextStep && <span className="text-ink-soft"> {nextStep}</span>}
      </p>
      {action}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded-control px-1 type-small font-medium text-ink-soft underline underline-offset-2 hover:text-ink"
        >
          Dismiss
        </button>
      )}
    </div>
  )
}
