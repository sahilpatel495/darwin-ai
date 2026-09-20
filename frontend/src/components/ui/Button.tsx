import type { ButtonHTMLAttributes, Ref } from 'react'
import { cx } from './cx'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** `primary` blue fill · `secondary` on `fill` · `ghost` text only. (`quiet` = `ghost`.) */
  variant?: 'primary' | 'secondary' | 'ghost' | 'quiet'
  /** `md` 36px · `sm` 28px. */
  size?: 'md' | 'sm'
  /** Fully rounded. For a button that sits among chips. */
  pill?: boolean
  /** Swaps the label for a spinner and disables the button. The width does not change. */
  loading?: boolean
  /** React 19: pass `ref` straight through, no forwardRef wrapper needed. */
  ref?: Ref<HTMLButtonElement>
}

const VARIANT = {
  primary: 'bg-blue text-white enabled:hover:bg-blue-hover',
  secondary: 'bg-fill text-ink enabled:hover:bg-fill-hover',
  // blue-ink, not blue: a ghost button often sits on the grey wash, where #0866FF is 4.3:1.
  ghost: 'text-blue-ink enabled:hover:bg-blue-soft',
  quiet: 'text-blue-ink enabled:hover:bg-blue-soft',
} as const

const SIZE = { md: 'h-9 text-[15px]', sm: 'h-7 text-[13px]' } as const
// A ghost button sits in running text and needs less air around it than a filled one.
const PAD = { primary: 'px-4', secondary: 'px-4', ghost: 'px-2.5', quiet: 'px-2.5' } as const

/** The only button in the product. Buttons say what happens: "Save to board", not "Submit". */
export default function Button({
  variant = 'secondary',
  size = 'md',
  pill = false,
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
        'press relative inline-flex shrink-0 items-center justify-center gap-2 font-semibold whitespace-nowrap',
        'disabled:cursor-not-allowed disabled:opacity-50',
        pill ? 'rounded-pill' : 'rounded-input',
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
