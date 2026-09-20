import type { ReactNode } from 'react'
import { cx } from './cx'

export interface EmptyStateProps {
  /** One sentence that invites the action, e.g. "Save an answer to build a report you can print." */
  children: ReactNode
  /** One control. Two is a menu, not an empty state. */
  action?: ReactNode
  className?: string
}

/** An empty screen is an invitation, not an apology. */
export default function EmptyState({ children, action, className }: EmptyStateProps) {
  return (
    <div className={cx('border-t border-rule py-8', className)}>
      <p className="measure type-body text-ink-soft">{children}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
