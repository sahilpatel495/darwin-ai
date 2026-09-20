import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'
import Tooltip from './Tooltip'
import { cx } from './cx'

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  /** What the button does, in words. Becomes the accessible name and the tooltip. Required. */
  label: string
  /** The glyph. 16 or 18px; it is decorative, because `label` already says everything. */
  children: ReactNode
  /** `md` 36px · `sm` 28px. */
  size?: 'md' | 'sm'
  /** `fill` a round grey button · `ghost` no background until hover. */
  variant?: 'fill' | 'ghost'
  /** Where the label sits. `bottom` for a button along the top edge of a dialog or a bar. */
  tooltipSide?: 'top' | 'bottom'
  ref?: Ref<HTMLButtonElement>
}

const SIZE = { md: 'size-9', sm: 'size-7' } as const
const VARIANT = {
  fill: 'bg-fill text-ink enabled:hover:bg-fill-hover',
  ghost: 'text-ink-2 enabled:hover:bg-fill enabled:hover:text-ink',
} as const

/** A round icon button. It always has words: `label` names it and shows on hover and focus. */
export default function IconButton({
  label,
  children,
  size = 'md',
  variant = 'fill',
  tooltipSide = 'top',
  className,
  type = 'button',
  ...rest
}: IconButtonProps) {
  return (
    <Tooltip label={label} side={tooltipSide}>
      <button
        type={type}
        aria-label={label}
        className={cx(
          'press inline-flex shrink-0 items-center justify-center rounded-pill',
          'disabled:cursor-not-allowed disabled:opacity-50',
          SIZE[size],
          VARIANT[variant],
          className,
        )}
        {...rest}
      >
        <span aria-hidden className="inline-flex">
          {children}
        </span>
      </button>
    </Tooltip>
  )
}
