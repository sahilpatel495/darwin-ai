import { useEffect, useId, useRef, useState } from 'react'
import type { ButtonHTMLAttributes, KeyboardEvent, ReactNode } from 'react'
import { cx } from './cx'

const STEP: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }

export interface TabItem {
  id: string
  /** Sentence case. Put a count in the label itself: "Files (7)". */
  label: string
  /**
   * Extra attributes on this tab's button — how `data-tour="files"` gets onto the Files tab
   * (§10). `data-*` is spelled out because HTMLAttributes only allows it on JSX itself.
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
 * Roving tabindex with arrow keys: one Tab stop for the whole list, arrows move between tabs,
 * Home and End jump to the ends. Activation follows focus, which is right for tabs whose panels
 * are already loaded.
 *
 * The underline is one element that slides, because labels have different widths and a border
 * that simply switches on and off gives no sense that the two tabs are one control (§4).
 */
export default function Tabs({ label, tabs, active, onChange, children, className }: TabsProps) {
  const uid = useId()
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({})
  const [bar, setBar] = useState<{ left: number; width: number } | null>(null)

  // Measured, not computed: the label text decides the width, and a font can still be settling.
  useEffect(() => {
    const move = () => {
      const node = buttons.current[active]
      setBar(node ? { left: node.offsetLeft, width: node.offsetWidth } : null)
    }
    move()
    const observer = new ResizeObserver(move)
    for (const node of Object.values(buttons.current)) if (node) observer.observe(node)
    return () => observer.disconnect()
  }, [active, tabs])

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
      {/* Scrolls rather than wraps: a tab that breaks over two lines leaves the sliding indicator
          measuring the wrong row, and a narrow sidebar is exactly where that happens. */}
      <div role="tablist" aria-label={label} onKeyDown={onKeyDown} className="relative flex gap-0.5 overflow-x-auto border-b border-line-soft">
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
                // px-2.5: three labels with their counts ("Files (7) · Links (5) · Glossary (10)") have to
                // fit the 320px data panel, or the row scrolls and cuts the first tab in half.
                'shrink-0 rounded-t-input px-2.5 pt-1.5 pb-2.5 type-body font-semibold whitespace-nowrap transition-colors duration-100',
                selected ? 'text-blue' : 'text-ink-2 hover:bg-fill hover:text-ink',
              )}
              {...tab.buttonProps}
            >
              {tab.label}
            </button>
          )
        })}
        {bar && (
          <span
            aria-hidden
            className="absolute -bottom-px h-[3px] rounded-pill bg-blue transition-all duration-200 ease-[var(--ease-standard)]"
            style={{ left: bar.left, width: bar.width }}
          />
        )}
      </div>
      <div role="tabpanel" id={`${uid}-panel`} aria-labelledby={`${uid}-${active}`}>
        {children}
      </div>
    </div>
  )
}
