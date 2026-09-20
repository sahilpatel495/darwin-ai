import type { ButtonHTMLAttributes, Ref } from 'react'
import { cx } from './cx'

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** The chosen option, e.g. the clarify answer the analyst picked. */
  selected?: boolean
  ref?: Ref<HTMLButtonElement>
}

/**
 * A question offered to the analyst: a suggestion to start with, a follow-up, a clarify
 * option. Always a whole question in sentence case, so it can be clicked without reading
 * anything else. 2px corners — a chip is a clipped slip of paper, not a pill.
 */
export default function Chip({ selected = false, className, type = 'button', ...rest }: ChipProps) {
  return (
    <button
      type={type}
      aria-pressed={selected || undefined}
      className={cx(
        'rounded-chip border px-3 py-1.5 text-left type-small transition-colors duration-100',
        selected
          ? 'border-indigo bg-indigo-soft text-indigo-ink'
          : 'border-rule bg-sheet text-ink enabled:hover:border-rule-strong enabled:hover:bg-wash',
        'disabled:cursor-not-allowed disabled:opacity-55',
        className,
      )}
      {...rest}
    />
  )
}
