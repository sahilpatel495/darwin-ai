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

// A tinted pill with a 3px left edge in the tone colour, and nothing else. No icon: the sentence
// already says what happened, and a glyph beside it would be a second thing to read that means
// the same.
const TONE = {
  info: 'border-primary bg-primary-soft',
  warn: 'border-attention bg-attention-soft',
  error: 'border-critical bg-critical-soft',
} as const

/** What happened, then what to do. Never a status code, never an apology. */
export default function Banner({ tone, children, nextStep, action, onDismiss, className }: BannerProps) {
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cx('flex flex-wrap items-start gap-x-4 gap-y-2 rounded-xl border-l-[3px] px-5 py-4', TONE[tone], className)}
    >
      <p className="min-w-0 flex-1 text-body-md text-ink-deep">
        <span className="font-bold whitespace-pre-line">{children}</span>
        {nextStep && <span className="font-normal text-ink"> {nextStep}</span>}
      </p>
      {action}
      {onDismiss && (
        <button type="button" onClick={onDismiss} className="press shrink-0 rounded-full px-3 py-1 text-button-md text-charcoal hover:bg-canvas">
          Dismiss
        </button>
      )}
    </div>
  )
}
