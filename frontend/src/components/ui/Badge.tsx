import type { ReactNode } from 'react'
import { cx } from './cx'

export interface BadgeProps {
  level: 'high' | 'medium' | 'low'
  /** Overrides the words. Only for a wording the design system adds later. */
  children?: ReactNode
  className?: string
}

// The colour is never the only signal: the words say it too, for anyone who cannot tell green
// from amber and for anyone reading the page aloud.
const WORDS = { high: 'High confidence', medium: 'Medium confidence', low: 'Low confidence' } as const
const TONE = {
  high: 'bg-green-soft text-green-ink',
  medium: 'bg-amber-soft text-amber-ink',
  low: 'bg-red-soft text-red-ink',
} as const
const DOT = { high: 'bg-green', medium: 'bg-amber', low: 'bg-red' } as const

/**
 * Confidence, and nothing else. A coloured dot and the words beside it; the reasons behind it
 * belong in a Popover next to this, not inside it.
 */
export default function Badge({ level, children, className }: BadgeProps) {
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-pill px-2.5 py-1 type-micro font-semibold', TONE[level], className)}>
      <span aria-hidden className={cx('size-2 shrink-0 rounded-pill', DOT[level])} />
      {children ?? WORDS[level]}
    </span>
  )
}
