import type { ReactNode } from 'react'
import { cx } from './cx'

export interface BadgeProps {
  level: 'high' | 'medium' | 'low'
  /** Overrides the words. Only for a wording the design system adds later. */
  children?: ReactNode
  className?: string
}

// The colour is never the only signal: the words say it too, for anyone who cannot
// tell green from amber and for anyone reading the page aloud.
const WORDS = { high: 'High confidence', medium: 'Medium confidence', low: 'Low confidence' } as const
const SQUARE = { high: 'bg-audit', medium: 'bg-amber', low: 'bg-red' } as const

/**
 * Confidence, and nothing else. A small square of colour and the words beside it; the
 * reasons behind it belong in a Popover next to this, not inside it.
 */
export default function Badge({ level, children, className }: BadgeProps) {
  return (
    <span className={cx('inline-flex items-center gap-1.5 type-small text-ink-soft', className)}>
      <span aria-hidden className={cx('size-2.5 rounded-[1px]', SQUARE[level])} />
      {children ?? WORDS[level]}
    </span>
  )
}
