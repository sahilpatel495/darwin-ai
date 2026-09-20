import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode, Ref } from 'react'
import { cx } from './cx'

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** The chosen option, e.g. the clarify answer the analyst picked. */
  selected?: boolean
  /** A computed fact rather than something to click: same pill, no hover, not a button. */
  static?: boolean
  /** A glyph or a dot before the words. */
  leading?: ReactNode
  ref?: Ref<HTMLButtonElement>
}

/**
 * A pill. Three jobs, one shape: a question offered to the analyst (a suggestion, a follow-up, a
 * clarify option), a filter, and — with `static` — an insight the server computed. Always a whole
 * sentence in sentence case, so it can be clicked or read without anything around it.
 */
export default function Chip({ selected = false, static: isStatic = false, leading, className, children, type = 'button', ...rest }: ChipProps) {
  const shared = 'inline-flex max-w-full items-center gap-2 rounded-full px-4 py-2 text-left text-body-sm'
  const body = (
    <>
      {leading && (
        <span aria-hidden className="inline-flex shrink-0">
          {leading}
        </span>
      )}
      <span className="min-w-0">{children}</span>
    </>
  )

  if (isStatic) {
    // A fact is not a control: drop everything that only means something on a button, and let the
    // rest through as span attributes (the cast is what says the filtering above was the point).
    const { onClick: _onClick, disabled: _disabled, ref: _ref, ...spanProps } = rest
    return (
      <span className={cx(shared, 'bg-primary-soft font-medium text-primary-deep', className)} {...(spanProps as HTMLAttributes<HTMLSpanElement>)}>
        {body}
      </span>
    )
  }

  return (
    <button
      type={type}
      aria-pressed={selected || undefined}
      className={cx(
        shared,
        'press border font-medium',
        selected
          ? 'border-ink-deep bg-ink-deep text-white'
          : 'border-hairline-soft bg-canvas text-ink enabled:hover:border-hairline enabled:hover:bg-surface-soft',
        'disabled:cursor-not-allowed disabled:opacity-40',
        className,
      )}
      {...rest}
    >
      {body}
    </button>
  )
}
