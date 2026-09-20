import { useId, useRef } from 'react'
import type { ButtonHTMLAttributes, KeyboardEvent, ReactNode } from 'react'
import { cx } from './cx'

const STEP: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }

export interface TabItem {
  id: string
  /** Sentence case. Add a count in the label itself: "Files (7)". */
  label: string
  /**
   * Extra attributes on this tab's button — how `data-tour="files"` gets onto the Files
   * tab (§10). `data-*` is spelled out because HTMLAttributes only allows it on JSX itself.
   */
  buttonProps?: ButtonHTMLAttributes<HTMLButtonElement> & { [key: `data-${string}`]: string }
}

export interface TabsProps {
  /** Names the tab list for a screen reader, e.g. "Your data". */
  label: string
  tabs: TabItem[]
  active: string
  onChange: (id: string) => void
  /** The active panel's content. Render only the active one. */
  children?: ReactNode
  className?: string
}

/**
 * Roving tabindex with arrow keys: one Tab stop for the whole list, arrows move between
 * tabs, Home and End jump to the ends. Activation follows focus, which is right for tabs
 * whose panels are already loaded.
 */
export default function Tabs({ label, tabs, active, onChange, children, className }: TabsProps) {
  const uid = useId()
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({})

  const goTo = (index: number) => {
    const next = tabs[(index + tabs.length) % tabs.length]
    if (!next) return
    onChange(next.id)
    buttons.current[next.id]?.focus()
  }

  const onKeyDown = (event: KeyboardEvent) => {
    const here = tabs.findIndex((tab) => tab.id === active)
    const step = STEP[event.key]
    if (step) goTo(here + step)
    else if (event.key === 'Home') goTo(0)
    else if (event.key === 'End') goTo(tabs.length - 1)
    else return
    event.preventDefault()
  }

  return (
    <div className={className}>
      <div role="tablist" aria-label={label} onKeyDown={onKeyDown} className="flex gap-4 border-b border-rule">
        {tabs.map((tab) => {
          const selected = tab.id === active
          return (
            <button
              key={tab.id}
              ref={(node) => {
                buttons.current[tab.id] = node
              }}
              type="button"
              role="tab"
              id={`${uid}-${tab.id}`}
              aria-selected={selected}
              aria-controls={`${uid}-panel`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(tab.id)}
              className={cx(
                '-mb-px border-b-2 pb-2 type-title transition-colors duration-100',
                selected ? 'border-indigo text-ink' : 'border-transparent text-ink-soft hover:text-ink',
              )}
              {...tab.buttonProps}
            >
              {tab.label}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" id={`${uid}-panel`} aria-labelledby={`${uid}-${active}`}>
        {children}
      </div>
    </div>
  )
}
