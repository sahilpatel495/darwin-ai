import type { ReactNode } from 'react'
import Check from './Check'
import { cx } from './cx'

export interface VerifiedListProps {
  /**
   * One plain sentence per line — not pills, not badges. The answer statement generates these
   * from the answer itself (§6.4), never from a hard-coded list.
   */
  items: ReactNode[]
  /** Pop the checks in, one after another, 90 ms apart (§4). */
  animate?: boolean
  className?: string
}

/** Checked statements under an answer: what was verified, in the analyst's words. */
export default function VerifiedList({ items, animate = false, className }: VerifiedListProps) {
  return (
    <ul className={cx('space-y-2', className)}>
      {items.map((item, i) => (
        // Index keys: the list is rebuilt whole for each answer and never reordered.
        <li key={i} className="flex gap-2.5 text-body-md text-ink">
          <Check animate={animate} delay={i * 90} className="mt-0.5" />
          <span className="min-w-0">{item}</span>
        </li>
      ))}
    </ul>
  )
}
