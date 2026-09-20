import { useRef } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { cx } from './cx'

const STEP: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }

export interface SegmentedOption {
  value: string
  label: ReactNode
  /** Needed when `label` is an icon. */
  name?: string
}

export interface SegmentedControlProps {
  /** Names the group, e.g. "Chart type". */
  label: string
  options: SegmentedOption[]
  value: string
  onChange: (value: string) => void
  size?: 'md' | 'sm'
  className?: string
}

/**
 * Pick one of a few: chart type, chart or table, an analysis option. The indicator slides to the
 * chosen segment, which is what tells you the two are the same control (§4).
 *
 * A radio group rather than a row of toggles: one Tab stop, arrows move between the options, and
 * a screen reader says "2 of 4" instead of reading four separate pressed states.
 */
export default function SegmentedControl({ label, options, value, onChange, size = 'md', className }: SegmentedControlProps) {
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({})
  const index = Math.max(0, options.findIndex((option) => option.value === value))

  const goTo = (to: number) => {
    const next = options[(to + options.length) % options.length]
    if (!next) return
    onChange(next.value)
    buttons.current[next.value]?.focus()
  }

  const onKeyDown = (event: KeyboardEvent) => {
    const step = STEP[event.key]
    if (step) goTo(index + step)
    else if (event.key === 'Home') goTo(0)
    else if (event.key === 'End') goTo(options.length - 1)
    else return
    event.preventDefault()
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={onKeyDown}
      // max-w-full: the segments are equal, so three long options would otherwise size the
      // control to the longest one and push a phone's page sideways.
      className={cx('relative inline-grid w-fit max-w-full gap-0.5 rounded-pill bg-fill p-0.5', className)}
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
    >
      {/* One slot wide, moved by whole slots — so the travel is exact at any container width. */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-0.5 left-0.5 rounded-pill bg-surface shadow-1 transition-transform duration-200 ease-[var(--ease-standard)]"
        style={{ width: `calc((100% - 0.25rem) / ${options.length})`, transform: `translateX(${index * 100}%)` }}
      />
      {options.map((option) => {
        const selected = option.value === value
        return (
          <button
            key={option.value}
            ref={(node) => {
              buttons.current[option.value] = node
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={option.name}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(option.value)}
            className={cx(
              'relative z-10 inline-flex items-center justify-center gap-1.5 rounded-pill font-semibold whitespace-nowrap',
              'transition-colors duration-100',
              size === 'md' ? 'h-8 px-3.5 text-[13px]' : 'h-7 px-3 text-[12px]',
              'overflow-hidden text-ellipsis',
              selected ? 'text-ink' : 'text-ink-2 hover:text-ink',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
