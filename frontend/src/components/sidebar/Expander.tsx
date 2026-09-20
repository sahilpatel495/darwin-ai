// A native <details> shaped like a row. Native because it is keyboard accessible and announces
// expanded/collapsed by itself. The chevron is ours because a flex <summary> loses the browser's
// marker, and without a marker nobody knows the row opens.
//
// The chevron turns from React state rather than from a `group-open` class: these rows nest — a
// Columns list inside a file row, the receipt inside "What I found" — and a CSS group matches
// every open ancestor, which pointed an inner chevron down while it was still shut.

import { useState } from 'react'
import type { ReactNode } from 'react'
import { ChevronIcon, cx } from '../ui'

interface ExpanderProps {
  label: ReactNode
  children: ReactNode
  /** Classes on the <details>; a divided row passes `border-b border-hairline-soft`. */
  className?: string
  /** Classes on the <summary>, for the row's own padding. */
  summaryClassName?: string
  /** Chevron at the end of the row instead of the start: for a row that opens with something else. */
  chevronAtEnd?: boolean
}

export default function Expander({ label, children, className, summaryClassName, chevronAtEnd = false }: ExpanderProps) {
  const [open, setOpen] = useState(false)
  const chevron = (
    <ChevronIcon
      size={16}
      className={cx(
        // The global reduced-motion rule flattens the duration; nothing extra is needed here.
        'mt-1 shrink-0 text-charcoal transition-transform duration-[var(--dur-fast)] ease-[var(--ease-spring)]',
        open && 'rotate-90',
        chevronAtEnd && 'ml-auto',
      )}
    />
  )
  return (
    // `toggle` does not bubble, so a nested row never turns the chevron of the row it sits in.
    <details className={className} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary
        className={cx(
          'flex cursor-pointer list-none items-start gap-3 rounded-xl px-3 py-3',
          'hover:bg-surface-soft [&::-webkit-details-marker]:hidden',
          summaryClassName,
        )}
      >
        {!chevronAtEnd && chevron}
        <span className="min-w-0 flex-1">{label}</span>
        {chevronAtEnd && chevron}
      </summary>
      {children}
    </details>
  )
}
