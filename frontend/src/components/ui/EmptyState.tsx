import type { ReactNode } from 'react'
import Glyph from '../graphics/Glyph'
import type { GlyphName } from '../graphics/Glyph'
import { cx } from './cx'

export interface EmptyStateProps {
  /** The drawing. Pick the one that names the thing that is missing, not a generic box. */
  glyph?: GlyphName
  /** A short heading above the sentence. Optional: often the sentence alone is enough. */
  title?: string
  /** One sentence that invites the action, e.g. "Save an answer to build a report you can print." */
  children: ReactNode
  /** One control. Two is a menu, not an empty state. */
  action?: ReactNode
  className?: string
}

/** An empty screen is an invitation, not an apology: a glyph, one sentence, one action (§5). */
export default function EmptyState({ glyph = 'sparkles', title, children, action, className }: EmptyStateProps) {
  return (
    <div className={cx('flex flex-col items-center rounded-xxl border border-hairline-soft bg-canvas px-6 py-14 text-center', className)}>
      <Glyph name={glyph} size={56} className="text-charcoal" />
      {title && <h2 className="mt-5 text-heading-sm text-ink-deep">{title}</h2>}
      <p className={cx('measure text-body-md text-slate', title ? 'mt-2' : 'mt-5')}>{children}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
