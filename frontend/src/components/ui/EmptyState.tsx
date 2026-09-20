import type { ReactNode } from 'react'
import { cx } from './cx'

export interface EmptyStateProps {
  /** One sentence that invites the action, e.g. "Save an answer to build a report you can print." */
  children: ReactNode
  /** A short heading above it. Optional: often the sentence alone is enough. */
  title?: string
  /** One control. Two is a menu, not an empty state. */
  action?: ReactNode
  className?: string
}

/** An empty screen is an invitation, not an apology. */
export default function EmptyState({ children, title, action, className }: EmptyStateProps) {
  return (
    <div className={cx('flex flex-col items-center rounded-card bg-surface px-6 py-12 text-center shadow-1', className)}>
      {title && <h2 className="type-section text-ink">{title}</h2>}
      <p className={cx('measure type-body text-ink-2', title && 'mt-1')}>{children}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
