import type { ReactNode } from 'react'
import { cx } from './cx'

export interface TipProps {
  /** Stable name for this hint, e.g. `'data-button'`. It is what "seen" is remembered against. */
  id: string
  /** Every hint this reader has already dismissed. From the project record's `tipsSeen` (§10). */
  seen: readonly string[]
  /** Called with `id` when they dismiss it. The caller stores it; this component remembers nothing. */
  onDismiss: (id: string) => void
  /** One line. Not two, and never a paragraph — that is what `#/how` is for. */
  children: ReactNode
  className?: string
}

/**
 * The replacement for the tour (§7): one sentence, beside the thing it explains, gone for good the
 * moment it is dismissed. Three of them exist in the whole product.
 *
 * It owns no storage. The seen-list belongs to the project record, which is the only thing in this
 * app that knows which reader this is — so the hint takes it as a prop and hands the id back.
 */
export default function Tip({ id, seen, onDismiss, children, className }: TipProps) {
  if (seen.includes(id)) return null

  return (
    <div
      role="note"
      className={cx(
        'rise-in flex flex-wrap items-center gap-x-3 gap-y-1 rounded-full bg-primary-soft py-2 pr-2 pl-4',
        className,
      )}
    >
      <p className="min-w-0 flex-1 text-body-sm text-primary-deep">{children}</p>
      <button
        type="button"
        onClick={() => onDismiss(id)}
        className="press shrink-0 rounded-full px-3 py-1 text-button-md text-primary-deep hover:bg-[rgb(0_100_224_/_.14)]"
      >
        Got it
      </button>
    </div>
  )
}
