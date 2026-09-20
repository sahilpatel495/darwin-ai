import { useId, useState } from 'react'
import type { ReactNode } from 'react'
import { cx } from './cx'

export interface TooltipProps {
  /** The words, two or three at most. Never the only place something is said. */
  label: string
  /** Exactly one focusable child: the control being named. */
  children: ReactNode
  side?: 'top' | 'bottom'
  /**
   * Where the label sits along the control. `center` is right almost everywhere; `start` is for
   * a control at the edge of the screen — a 72px nav rail's tooltip, centred, hangs off the
   * left of the window and is cut in half.
   */
  align?: 'center' | 'start'
  className?: string
}

/**
 * Keyboard focus only. A modal dialog gives its close button focus the moment it opens, and a
 * tooltip nobody asked for reads as a glitch; `:focus-visible` is the browser's own answer to
 * "did a person navigate here with the keyboard?".
 */
const keyboardFocus = (target: EventTarget) => (target as HTMLElement).matches?.(':focus-visible') ?? false

/**
 * The name of an icon-only control, shown on hover and on keyboard focus. It is an echo, never
 * the only signal: the control carries the same words in `aria-label`, so a touch screen — which
 * has no hover — loses nothing. Anything that needs explaining is a `WhatsThis`, not a tooltip.
 */
export default function Tooltip({ label, children, side = 'top', align = 'center', className }: TooltipProps) {
  const [open, setOpen] = useState(false)
  const id = useId()

  return (
    <span
      className={cx('relative inline-flex', className)}
      onPointerEnter={() => setOpen(true)}
      onPointerLeave={() => setOpen(false)}
      onFocusCapture={(event) => setOpen(keyboardFocus(event.target))}
      onBlurCapture={() => setOpen(false)}
    >
      {children}
      {open && (
        <span
          id={id}
          role="tooltip"
          className={cx(
            'popover-in pointer-events-none absolute z-40 rounded-input bg-ink px-2 py-1',
            'type-micro whitespace-nowrap text-wash shadow-3',
            align === 'start' ? 'left-0' : 'left-1/2 -translate-x-1/2',
            side === 'top' ? 'bottom-full mb-1.5' : 'top-full mt-1.5',
          )}
        >
          {label}
        </span>
      )}
    </span>
  )
}
