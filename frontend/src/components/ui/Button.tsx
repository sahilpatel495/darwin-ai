import type { ButtonHTMLAttributes, Ref } from 'react'
import { cx } from './cx'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /**
   * `primary` the black pill, for anything you can do · `action` the cobalt pill, reserved for
   * Ask / Run / Continue / Create account and nothing else · `secondary` a 2px ink outline ·
   * `ghost` a faint outline · `quiet` text only.
   */
  variant?: 'primary' | 'action' | 'secondary' | 'ghost' | 'quiet'
  /** `md` 44px · `sm` 36px. */
  size?: 'md' | 'sm'
  /** Swaps the label for a spinner and disables the button. The width does not change. */
  loading?: boolean
  /** Fills the row. For the one action in a card or a phone-width form. */
  block?: boolean
  /** TEMPORARY alias: every button is a pill now, so this does nothing. Delete the prop at the call site. */
  pill?: boolean
  ref?: Ref<HTMLButtonElement>
}

// Every button is a pill (§2). There is no `pill` prop any more because there is no other shape:
// a squared button is a bug.
const VARIANT = {
  primary: 'bg-ink-deep text-white enabled:hover:bg-ink',
  action: 'bg-primary text-white enabled:hover:bg-primary-deep',
  secondary: 'border-2 border-ink-deep text-ink-deep enabled:hover:bg-surface-soft',
  ghost: 'border-2 border-[rgb(10_19_23_/_.12)] text-ink-deep enabled:hover:border-[rgb(10_19_23_/_.28)]',
  quiet: 'text-charcoal enabled:hover:bg-surface-soft enabled:hover:text-ink-deep',
} as const

// 14×30 padding on the filled pills (§5); an outline eats 2px of it, and a quiet button sits in
// running text and needs less air than either.
const SIZE = { md: 'h-11', sm: 'h-9' } as const
const PAD = {
  primary: 'px-[30px]',
  action: 'px-[30px]',
  secondary: 'px-7',
  ghost: 'px-7',
  quiet: 'px-3.5',
} as const

/** The only button in the product. Buttons say what happens: "Save to board", not "Submit". */
export default function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  block = false,
  pill: _pill,
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
        'press relative inline-flex shrink-0 items-center justify-center gap-2 rounded-full',
        'text-button-md whitespace-nowrap',
        'disabled:cursor-not-allowed disabled:opacity-40',
        block ? 'w-full' : '',
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
