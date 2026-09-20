// A native <details> with a visible chevron. Native because it is keyboard accessible and
// announces expanded/collapsed by itself. The chevron is ours because a flex <summary> loses the
// browser's marker, and without a marker nobody knows the row opens.
// Do not nest one Expander inside another: `group-open` would rotate the inner chevron too.

import type { ReactNode } from 'react'

interface ExpanderProps {
  label: ReactNode
  /** Right-aligned note that stays visible while collapsed, such as "2 to check". */
  aside?: ReactNode
  children: ReactNode
}

export default function Expander({ label, aside, children }: ExpanderProps) {
  return (
    <details className="group border-t border-dashed border-line pt-1">
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded py-1 text-sm font-medium text-ink [&::-webkit-details-marker]:hidden">
        <span aria-hidden className="w-2 text-ink-faint transition-transform group-open:rotate-90">
          ›
        </span>
        <span className="min-w-0 flex-1 truncate">{label}</span>
        {aside}
      </summary>
      {children}
    </details>
  )
}
