import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { cx } from './cx'

export interface MenuAction {
  id: string
  /** What happens, in the analyst's words: "Ask about this", "Download CSV". */
  label: string
  onSelect: () => void
  disabled?: boolean
}

export interface MenuProps {
  /** What sits inside the trigger button. An icon needs `triggerLabel`. */
  trigger: ReactNode
  triggerLabel?: string
  actions: MenuAction[]
  align?: 'left' | 'right'
  /** Classes for the trigger button. */
  className?: string
}

/**
 * A short list of things you can do to one thing — a tile's menu, a project row's menu.
 * Opens on click, Down and Up; arrows move between items, Enter chooses, Esc closes and puts
 * focus back on the trigger. Not a navigation: everything here does something to what it is next to.
 */
export default function Menu({ trigger, triggerLabel, actions, align = 'right', className }: MenuProps) {
  const [open, setOpen] = useState(false)
  const wrapper = useRef<HTMLSpanElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const items = useRef<(HTMLButtonElement | null)[]>([])
  const menuId = useId()

  const close = (focusTrigger = true) => {
    setOpen(false)
    if (focusTrigger) button.current?.focus()
  }

  useEffect(() => {
    if (!open) return
    items.current.find((node) => node && !node.disabled)?.focus()
    const onPointerDown = (event: PointerEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  const move = (from: number, step: number) => {
    const live = items.current.map((node, i) => (node && !node.disabled ? i : -1)).filter((i) => i >= 0)
    if (live.length === 0) return
    const here = live.indexOf(from)
    const next = live[(here + step + live.length) % live.length]
    items.current[next]?.focus()
  }

  const onMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const from = items.current.findIndex((node) => node === document.activeElement)
    if (event.key === 'Escape') close()
    else if (event.key === 'ArrowDown') move(from, 1)
    else if (event.key === 'ArrowUp') move(from, -1)
    else if (event.key === 'Tab') close(false)
    else return
    if (event.key !== 'Tab') event.preventDefault()
  }

  return (
    <span ref={wrapper} className="relative inline-block">
      <button
        ref={button}
        type="button"
        aria-label={triggerLabel}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((was) => !was)}
        onKeyDown={(event) => {
          if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
          setOpen(true)
          event.preventDefault()
        }}
        className={className}
      >
        {trigger}
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          onKeyDown={onMenuKeyDown}
          className={cx(
            'popover-in absolute top-full z-40 mt-1.5 min-w-48 max-w-[calc(100vw-2rem)] overflow-hidden',
            'rounded-card bg-surface p-1 shadow-3',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {actions.map((action, i) => (
            <button
              key={action.id}
              ref={(node) => {
                items.current[i] = node
              }}
              type="button"
              role="menuitem"
              disabled={action.disabled}
              onClick={() => {
                close()
                action.onSelect()
              }}
              className={cx(
                'block w-full rounded-input px-3 py-2 text-left type-body text-ink',
                'hover:bg-fill disabled:cursor-not-allowed disabled:text-ink-3 disabled:hover:bg-transparent',
              )}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </span>
  )
}
