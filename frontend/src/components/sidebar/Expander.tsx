// A native <details> shaped like a ListRow. Native because it is keyboard accessible and
// announces expanded/collapsed by itself. The chevron is ours because a flex <summary> loses the
// browser's marker, and without a marker nobody knows the row opens.
//
// The group is named (`group/row`), so a Columns list can open inside an already-open file row
// without the outer chevron turning too.

import type { ReactNode } from 'react'
import { ChevronIcon, cx } from '../ui'

interface ExpanderProps {
  label: ReactNode
  /** Stays visible while collapsed, at the end of the summary line: a count, a mark. */
  aside?: ReactNode
  children: ReactNode
  /** Classes on the <details>; a divided row passes `border-b border-line-soft`. */
  className?: string
  /** Classes on the <summary>, for the row's own padding. */
  summaryClassName?: string
  /** Chevron at the end of the row instead of the start: for a row that already opens with a mark. */
  chevronAtEnd?: boolean
}

export default function Expander({ label, aside, children, className, summaryClassName, chevronAtEnd = false }: ExpanderProps) {
  const chevron = (
    <ChevronIcon
      size={16}
      className={cx('mt-[3px] shrink-0 text-ink-3 transition-transform duration-100 group-open/row:rotate-90', chevronAtEnd && 'ml-auto')}
    />
  )
  return (
    <details className={cx('group/row', className)}>
      <summary
        className={cx(
          'flex cursor-pointer list-none items-start gap-2 rounded-input px-2 py-2.5',
          'hover:bg-fill [&::-webkit-details-marker]:hidden',
          summaryClassName,
        )}
      >
        {!chevronAtEnd && chevron}
        <span className="min-w-0 flex-1">{label}</span>
        {aside}
        {chevronAtEnd && chevron}
      </summary>
      {children}
    </details>
  )
}
