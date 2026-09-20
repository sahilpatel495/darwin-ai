import { useEffect, useId, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { cx } from './cx'

export interface PopoverProps {
  /** What sits inside the trigger button. */
  trigger: ReactNode
  /** Accessible name for the trigger, needed whenever `trigger` is an icon or one character. */
  triggerLabel?: string
  /** First line inside the panel, in the section-heading style. */
  title?: string
  children: ReactNode
  /** Which edge of the trigger the panel lines up with. Use `right` near the right of the screen. */
  align?: 'left' | 'right'
  /** Classes for the trigger button. */
  className?: string
}

/**
 * A small explanation that opens next to whatever it explains. Click and keyboard, never
 * hover-only: a hover tooltip is unreachable on a phone and invisible to a keyboard.
 * Esc closes it and puts focus back on the trigger; so does a click anywhere outside.
 */
export default function Popover({ trigger, triggerLabel, title, children, align = 'left', className }: PopoverProps) {
  const [open, setOpen] = useState(false)
  const wrapper = useRef<HTMLSpanElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const panelId = useId()

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: PointerEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setOpen(false)
      button.current?.focus()
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <span ref={wrapper} className="relative inline-block">
      <button
        ref={button}
        type="button"
        aria-label={triggerLabel}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((was) => !was)}
        className={className}
      >
        {trigger}
      </button>
      {open && (
        <div
          id={panelId}
          className={cx(
            'popover-in absolute top-full z-40 mt-2 w-72 max-w-[calc(100vw-2rem)]',
            'rounded-xl bg-surface p-3.5 shadow-level-2',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {title && <p className="text-subtitle-lg text-ink">{title}</p>}
          <div className={cx('text-body-sm text-slate', title && 'mt-1')}>{children}</div>
        </div>
      )}
    </span>
  )
}
