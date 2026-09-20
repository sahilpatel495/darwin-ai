import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'
import Tooltip from './Tooltip'
import { cx } from './cx'

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  /** What the button does, in words. Becomes the accessible name and the tooltip. Required. */
  label: string
  /** The glyph. 18 or 20px; it is decorative, because `label` already says everything. */
  children: ReactNode
  /** `md` 40px (§5) · `sm` 32px, for a toolbar inside a card. */
  size?: 'md' | 'sm'
  /** `soft` a filled circle · `ghost` nothing until hover · `outline` a hairline ring. */
  variant?: 'soft' | 'ghost' | 'outline' | 'fill'
  /** Where the label sits. `bottom` for a button along the top edge of a dialog or a bar. */
  tooltipSide?: 'top' | 'bottom'
  ref?: Ref<HTMLButtonElement>
}

const SIZE = { md: 'size-10', sm: 'size-8' } as const
const VARIANT = {
  soft: 'bg-surface-soft text-ink-deep enabled:hover:bg-[#e3e9ef]',
  fill: 'bg-surface-soft text-ink-deep enabled:hover:bg-[#e3e9ef]', // TEMPORARY alias for `soft`
  ghost: 'text-charcoal enabled:hover:bg-surface-soft enabled:hover:text-ink-deep',
  outline: 'border border-hairline-soft text-ink-deep enabled:hover:border-hairline',
} as const

/** A round icon button. It always has words: `label` names it and shows on hover and focus. */
export default function IconButton({
  label,
  children,
  size = 'md',
  variant = 'soft',
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
          'press inline-flex shrink-0 items-center justify-center rounded-circle',
          'disabled:cursor-not-allowed disabled:opacity-40',
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
