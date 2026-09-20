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

// A 3px left edge in the tone colour, and nothing else. No icon: the sentence already says what
// happened, and a glyph beside it would be a second thing to read that means the same.
const TONE = {
  info: 'border-blue bg-blue-soft',
  warn: 'border-amber bg-amber-soft',
  error: 'border-red bg-red-soft',
} as const

/** What happened, then what to do. Never a status code, never an apology. */
export default function Banner({ tone, children, nextStep, action, onDismiss, className }: BannerProps) {
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cx('flex flex-wrap items-start gap-x-3 gap-y-2 rounded-card border-l-[3px] px-4 py-3', TONE[tone], className)}
    >
      <p className="min-w-0 flex-1 type-body text-ink">
        <span className="font-semibold whitespace-pre-line">{children}</span>
        {nextStep && <span className="font-normal"> {nextStep}</span>}
      </p>
      {action}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="press shrink-0 rounded-input px-2 py-0.5 type-small font-semibold text-ink-2 hover:bg-fill hover:text-ink"
        >
          Dismiss
        </button>
      )}
    </div>
  )
}
