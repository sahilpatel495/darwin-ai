// A native <details> with a visible chevron. Native because it is keyboard accessible and
// announces expanded/collapsed by itself. The chevron is ours because a flex <summary> loses the
// browser's marker, and without a marker nobody knows the row opens.
//
// The group is named (`group/row`), so a Columns list can open inside an already-open file row
// without the outer chevron turning too.

import type { ReactNode } from 'react'
import { cx } from '../ui'

interface ExpanderProps {
  label: ReactNode
  /** Stays visible while collapsed, at the end of the summary line: a count, a mark. */
  aside?: ReactNode
  children: ReactNode
  /** Classes on the <details>; a ruled row passes `border-b border-rule`. */
  className?: string
  /** Classes on the <summary>, for the row's own padding. */
  summaryClassName?: string
}

export default function Expander({ label, aside, children, className, summaryClassName }: ExpanderProps) {
  return (
    <details className={cx('group/row', className)}>
      <summary className={cx('flex cursor-pointer list-none items-start gap-2 py-3 [&::-webkit-details-marker]:hidden', summaryClassName)}>
        <svg aria-hidden width="10" height="10" viewBox="0 0 10 10" fill="none" className="mt-[7px] shrink-0 text-ink-soft transition-transform duration-100 group-open/row:rotate-90">
          <path d="M3 1.5 6.5 5 3 8.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="min-w-0 flex-1">{label}</span>
        {aside}
      </summary>
      {children}
    </details>
  )
}
