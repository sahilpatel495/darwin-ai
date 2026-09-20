// Input, Select and Textarea. One file because they are one control with three bodies: the same
// 44px height, radius lg, hairline border, 2px cobalt focus ring and error treatment (§5).
//
// The label is part of the control, not something the caller remembers to add: a field without one
// is the commonest way an accessible form stops being accessible.

import { useId } from 'react'
import type { InputHTMLAttributes, ReactNode, Ref, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { cx } from './cx'

interface Shared {
  /** The words above the control. Sentence case, no colon. */
  label: string
  /** Hide the label visually but keep it for a screen reader — a search pill, say. */
  labelHidden?: boolean
  /** One quiet line under the label. Not a paragraph: §12 bans walls of helper text. */
  hint?: ReactNode
  /** What is wrong, in a sentence. Replaces `hint` and turns the border critical. */
  error?: ReactNode
  className?: string
}

const BOX =
  'w-full rounded-lg border bg-canvas px-4 text-body-md text-ink placeholder:text-stone ' +
  // border-color only, not `transition-colors`: that shorthand also transitions `outline-color`,
  // which fades the focus ring in from the browser's default over 150ms. A focus ring appears.
  'transition-[border-color] duration-150 disabled:cursor-not-allowed disabled:bg-surface-soft disabled:text-stone'

const border = (error: unknown) => (error ? 'border-critical' : 'border-hairline hover:border-charcoal')

function Frame({ id, label, labelHidden, hint, error, className, children }: Shared & { id: string; children: ReactNode }) {
  return (
    <div className={cx('w-full', className)}>
      <label htmlFor={id} className={cx('block text-body-sm font-bold text-ink-deep', labelHidden && 'sr-only')}>
        {label}
      </label>
      <div className={cx(!labelHidden && 'mt-2')}>{children}</div>
      {error ? (
        <p id={`${id}-note`} role="alert" className="mt-2 text-body-sm text-critical">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-note`} className="mt-2 text-body-sm text-steel">
            {hint}
          </p>
        )
      )}
    </div>
  )
}

export type InputProps = Shared & Omit<InputHTMLAttributes<HTMLInputElement>, 'className'> & { ref?: Ref<HTMLInputElement> }

export function Input({ label, labelHidden, hint, error, className, id, ...rest }: InputProps) {
  const auto = useId()
  const fieldId = id ?? auto
  return (
    <Frame id={fieldId} label={label} labelHidden={labelHidden} hint={hint} error={error} className={className}>
      <input
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? `${fieldId}-note` : undefined}
        className={cx(BOX, border(error), 'h-11')}
        {...rest}
      />
    </Frame>
  )
}

export type TextareaProps = Shared & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'className'> & { ref?: Ref<HTMLTextAreaElement> }

export function Textarea({ label, labelHidden, hint, error, className, id, rows = 3, ...rest }: TextareaProps) {
  const auto = useId()
  const fieldId = id ?? auto
  return (
    <Frame id={fieldId} label={label} labelHidden={labelHidden} hint={hint} error={error} className={className}>
      <textarea
        id={fieldId}
        rows={rows}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? `${fieldId}-note` : undefined}
        className={cx(BOX, border(error), 'resize-y py-3')}
        {...rest}
      />
    </Frame>
  )
}

export type SelectProps = Shared & Omit<SelectHTMLAttributes<HTMLSelectElement>, 'className'> & { ref?: Ref<HTMLSelectElement> }

export function Select({ label, labelHidden, hint, error, className, id, children, ...rest }: SelectProps) {
  const auto = useId()
  const fieldId = id ?? auto
  return (
    <Frame id={fieldId} label={label} labelHidden={labelHidden} hint={hint} error={error} className={className}>
      <div className="relative">
        <select
          id={fieldId}
          aria-invalid={error ? true : undefined}
          aria-describedby={error || hint ? `${fieldId}-note` : undefined}
          // The native select, styled: it already opens correctly on a phone, handles type-ahead
          // and is the one listbox a screen reader never argues with.
          className={cx(BOX, border(error), 'h-11 appearance-none pr-10')}
          {...rest}
        >
          {children}
        </select>
        <svg aria-hidden viewBox="0 0 20 20" className="pointer-events-none absolute top-1/2 right-4 size-4 -translate-y-1/2 text-charcoal" fill="none">
          <path d="m5.5 8 4.5 4.5L14.5 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </Frame>
  )
}
