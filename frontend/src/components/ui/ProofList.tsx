import type { ReactNode } from 'react'
import Tick from './Tick'
import { cx } from './cx'

export interface ProofListProps {
  /**
   * One plain sentence per line — not pills, not badges. The answer statement
   * generates these from the answer itself (§6.4), never from a hard-coded list.
   */
  items: ReactNode[]
  /** Draw the ticks in, one after another, 90 ms apart (§4). */
  animate?: boolean
  className?: string
}

/** Ticked statements under an answer: what was checked, in the analyst's words. */
export default function ProofList({ items, animate = false, className }: ProofListProps) {
  return (
    <ul className={cx('space-y-1.5', className)}>
      {items.map((item, i) => (
        // Index keys: the list is rebuilt whole for each answer and never reordered.
        <li key={i} className="flex gap-2.5 type-body text-ink">
          <Tick animate={animate} delay={i * 90} className="mt-1" />
          <span className="min-w-0">{item}</span>
        </li>
      ))}
    </ul>
  )
}
