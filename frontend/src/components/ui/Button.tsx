import type { ButtonHTMLAttributes, Ref } from 'react'
import { cx } from './cx'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** `primary` indigo fill · `secondary` rule border on a sheet · `quiet` text only. */
  variant?: 'primary' | 'secondary' | 'quiet'
  size?: 'md' | 'sm'
  /** Swaps the label for a spinner and disables the button. The width does not change. */
  loading?: boolean
  /** React 19: pass `ref` straight through, no forwardRef wrapper needed. */
  ref?: Ref<HTMLButtonElement>
}

const VARIANT = {
  primary: 'bg-indigo text-white enabled:hover:bg-indigo-ink',
  secondary: 'border border-rule bg-sheet text-ink enabled:hover:bg-wash',
  quiet: 'text-indigo enabled:hover:bg-indigo-soft',
} as const

const SIZE = {
  md: 'h-9 text-[15px]',
  sm: 'h-8 text-[13px]',
} as const

// `quiet` sits in running text and needs less air around it than a filled button.
const PAD = { primary: 'px-4', secondary: 'px-4', quiet: 'px-2' } as const

/**
 * The only button in the product. Buttons say what happens: "Save to board", not "Submit".
 */
export default function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  className,
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        'relative inline-flex shrink-0 items-center justify-center gap-2 rounded-control font-medium whitespace-nowrap',
        'transition-colors duration-100 disabled:cursor-not-allowed disabled:opacity-55',
        VARIANT[variant],
        SIZE[size],
        PAD[variant],
        className,
      )}
      {...rest}
    >
      {/* The label keeps its space while loading, so nothing on the page moves. */}
      <span className={cx('inline-flex items-center gap-2', loading && 'invisible')}>{children}</span>
      {loading && (
        <svg aria-hidden className="absolute size-4 animate-spin" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2" />
          <path d="M14.5 8A6.5 6.5 0 0 0 8 1.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      )}
    </button>
  )
}
