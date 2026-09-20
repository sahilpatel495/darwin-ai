import type { ReactNode } from 'react'
import { cx } from './cx'

export type BadgeTone = 'success' | 'attention' | 'critical' | 'neutral' | 'promo'

export interface BadgeProps {
  /** The meaning. `promo` is the yellow strip's badge and belongs nowhere else. */
  tone?: BadgeTone
  /** Confidence, the one place a badge names a level. Sets the tone and the words. */
  level?: 'high' | 'medium' | 'low'
  /** A coloured dot before the words. On by default for a level, off otherwise. */
  dot?: boolean
  /** Overrides the words. Required for every tone except `level`. */
  children?: ReactNode
  className?: string
}

// The colour is never the only signal: the words say it too, for anyone who cannot tell green
// from amber and for anyone reading the page aloud.
const WORDS = { high: 'High confidence', medium: 'Medium confidence', low: 'Low confidence' } as const
const LEVEL_TONE = { high: 'success', medium: 'attention', low: 'critical' } as const

const TONE: Record<BadgeTone, string> = {
  success: 'bg-success-soft text-success',
  attention: 'bg-attention-soft text-attention-ink',
  critical: 'bg-critical-soft text-critical',
  neutral: 'bg-surface-soft text-charcoal',
  promo: 'bg-warning text-ink-deep',
}
const DOT: Record<BadgeTone, string> = {
  success: 'bg-success',
  attention: 'bg-attention',
  critical: 'bg-critical',
  neutral: 'bg-stone',
  promo: 'bg-ink-deep',
}

/**
 * A small pill that states a fact about the thing beside it: confidence, "No AI involved",
 * "Sample company". The reasons behind it belong in a Popover next to this, not inside it.
 */
export default function Badge({ tone, level, dot, children, className }: BadgeProps) {
  const resolved: BadgeTone = tone ?? (level ? LEVEL_TONE[level] : 'neutral')
  const showDot = dot ?? level !== undefined

  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-caption font-bold', TONE[resolved], className)}>
      {showDot && <span aria-hidden className={cx('size-1.5 shrink-0 rounded-full', DOT[resolved])} />}
      {children ?? (level && WORDS[level])}
    </span>
  )
}
