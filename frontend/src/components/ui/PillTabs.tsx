import { useEffect, useId, useRef, useState } from 'react'
import type { HTMLAttributes, KeyboardEvent, ReactNode } from 'react'
import { cx } from './cx'

const STEP: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }

export interface PillTab {
  id: string
  /** Sentence case, one or two words. Put a count in the label itself: "Files (7)". */
  label: ReactNode
  /** Turns the tab into a link — the app's four sections are real routes, not panel toggles. */
  href?: string
  /** Extra attributes on this tab's control. Typed against HTMLElement, because the control is
   *  a <button> or an <a> depending on `href`. */
  props?: HTMLAttributes<HTMLElement> & { [key: `data-${string}`]: string }
}

export interface PillTabsProps {
  /** Names the set for a screen reader, e.g. "Sections of this project". */
  label: string
  tabs: PillTab[]
  active: string
  /** Left out when every tab is a link: the route is what changes. */
  onChange?: (id: string) => void
  /** The active panel's content, when these tabs switch panels rather than pages. */
  children?: ReactNode
  size?: 'md' | 'sm'
  className?: string
}

const SIZE = { md: 'h-11 px-5', sm: 'h-9 px-4' } as const

/**
 * The product's one tab shape (§5): a row of pills on the canvas, the chosen one filled ink with
 * white text and a level-1 shadow, and a single indicator that slides between them — which is
 * what tells you the four pills are one control rather than four buttons (§4).
 *
 * Two modes. With `href` the tabs are links and the browser's own history does the work; without,
 * it is a real tablist with a roving tabindex, arrows between tabs and Home/End to the ends.
 */
export default function PillTabs({ label, tabs, active, onChange, children, size = 'md', className }: PillTabsProps) {
  const uid = useId()
  const nav = tabs.some((tab) => tab.href)
  const controls = useRef<Record<string, HTMLElement | null>>({})
  const [bar, setBar] = useState<{ left: number; width: number } | null>(null)
  // The first paint puts the indicator where it belongs without sliding in from zero.
  const settled = useRef(false)

  // Measured, not computed: the label text decides the width, and a webfont can still be settling.
  useEffect(() => {
    const move = () => {
      const node = controls.current[active]
      setBar(node ? { left: node.offsetLeft, width: node.offsetWidth } : null)
      settled.current = true
    }
    move()
    const observer = new ResizeObserver(move)
    for (const node of Object.values(controls.current)) if (node) observer.observe(node)
    return () => observer.disconnect()
  }, [active, tabs])

  const goTo = (index: number) => {
    const next = tabs[(index + tabs.length) % tabs.length]
    if (!next) return
    onChange?.(next.id)
    controls.current[next.id]?.focus()
  }

  const onKeyDown = (event: KeyboardEvent) => {
    if (nav) return // links: Tab and Enter, like every other link on the page
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
      <div
        role={nav ? undefined : 'tablist'}
        aria-label={label}
        onKeyDown={onKeyDown}
        className="relative flex w-fit max-w-full gap-1 overflow-x-auto rounded-full p-1"
      >
        {/* The sliding pill, under the labels. Hidden until it has been measured once, so it
            never flashes at the left edge. */}
        {bar && (
          <span
            aria-hidden
            className="pointer-events-none absolute inset-y-1 rounded-full bg-ink-deep shadow-level-1"
            style={{
              left: bar.left,
              width: bar.width,
              transition: settled.current ? 'left var(--dur-slow) var(--ease-spring), width var(--dur-slow) var(--ease-spring)' : undefined,
            }}
          />
        )}

        {tabs.map((tab) => {
          const selected = tab.id === active
          const className = cx(
            'press relative z-10 inline-flex shrink-0 items-center justify-center gap-2 rounded-full',
            'text-button-md whitespace-nowrap no-underline',
            SIZE[size],
            // Transparent, not canvas: the indicator slides *under* the pills, so a white fill on
            // an inactive one would hide it for the whole journey.
            selected ? 'text-white' : 'border border-hairline-soft text-charcoal hover:border-hairline hover:text-ink-deep',
          )
          const ref = (node: HTMLElement | null) => {
            controls.current[tab.id] = node
          }

          if (tab.href) {
            return (
              <a key={tab.id} ref={ref} href={tab.href} aria-current={selected ? 'page' : undefined} className={className} {...tab.props}>
                {tab.label}
              </a>
            )
          }
          return (
            <button
              key={tab.id}
              ref={ref}
              type="button"
              role="tab"
              id={`${uid}-${tab.id}`}
              aria-selected={selected}
              aria-controls={`${uid}-panel`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange?.(tab.id)}
              className={className}
              {...tab.props}
            >
              {tab.label}
            </button>
          )
        })}
      </div>

      {children !== undefined && !nav && (
        <div role="tabpanel" id={`${uid}-panel`} aria-labelledby={`${uid}-${active}`}>
          {children}
        </div>
      )}
    </div>
  )
}
