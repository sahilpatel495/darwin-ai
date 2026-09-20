import type { ButtonHTMLAttributes, HTMLAttributes, Ref } from 'react'
import { cx } from './cx'

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** The chosen option, e.g. the clarify answer the analyst picked. */
  selected?: boolean
  /** A computed fact rather than something to click: same pill, no hover, not a button. */
  static?: boolean
  ref?: Ref<HTMLButtonElement>
}

/**
 * A pill. Three jobs, one shape: a question offered to the analyst (a suggestion, a follow-up,
 * a clarify option), and — with `static` — an insight the server computed. Always a whole
 * sentence in sentence case, so it can be clicked or read without anything around it.
 */
export default function Chip({ selected = false, static: isStatic = false, className, type = 'button', ...rest }: ChipProps) {
  const shared = 'inline-flex max-w-full items-center gap-1.5 rounded-pill px-3 py-1.5 text-left type-small'

  if (isStatic) {
    // A fact is not a control: drop everything that only means something on a button, and let the
    // rest through as span attributes (the cast is what says the filtering above was the point).
    const { onClick: _onClick, disabled: _disabled, ref: _ref, ...spanProps } = rest
    return <span className={cx(shared, 'bg-blue-soft font-medium text-blue-ink', className)} {...(spanProps as HTMLAttributes<HTMLSpanElement>)} />
  }

  return (
    <button
      type={type}
      aria-pressed={selected || undefined}
      className={cx(
        shared,
        'press font-medium',
        selected ? 'bg-blue text-white' : 'bg-fill text-ink enabled:hover:bg-fill-hover',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...rest}
    />
  )
}
