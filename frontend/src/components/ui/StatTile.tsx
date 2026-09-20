import type { ReactNode } from 'react'
import { useCountUp } from './countUp'
import { cx } from './cx'

export interface StatTileProps {
  /** The already-formatted display string, e.g. "₹20.40 Cr" or "12.4%". Never a raw number. */
  value: string
  /** What the figure counts, e.g. "Gross pay, Engineering, 2025". Sits under the figure. */
  label?: ReactNode
  /**
   * The change, already formatted with its sign: "+4.2%", "−18 people". `direction` decides the
   * colour, because up is not always good — attrition up is red for an HR analyst.
   */
  delta?: { text: string; direction: 'up' | 'down' | 'flat'; good?: boolean }
  /** A sparkline or any small visual beside the figure. */
  aside?: ReactNode
  /** Count up over 400 ms when the answer arrives (§4). */
  animate?: boolean
  className?: string
}

const ARROW = { up: '▲', down: '▼', flat: '—' } as const

/** A delta is never colour alone: the arrow says the direction to anyone who cannot see it. */
function Delta({ text, direction, good }: NonNullable<StatTileProps['delta']>) {
  const tone =
    good === undefined
      ? 'bg-fill text-ink-2'
      : good
        ? 'bg-green-soft text-green-ink'
        : 'bg-red-soft text-red-ink'
  return (
    <span className={cx('inline-flex items-center gap-1 rounded-pill px-2 py-0.5 type-micro font-semibold', tone)}>
      <span aria-hidden className="text-[9px] leading-none">
        {ARROW[direction]}
      </span>
      {text}
    </span>
  )
}

/**
 * The hero figure. One per answer: two side by side and neither is the headline.
 * The count-up is the moment the number lands — it draws the eye to the one thing on the card
 * that someone is going to quote (§4).
 */
export default function StatTile({ value, label, delta, aside, animate = false, className }: StatTileProps) {
  const shown = useCountUp(value, animate)
  return (
    <div className={cx('flex items-end justify-between gap-4', className)}>
      <div className="min-w-0">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          {/* aria-label carries the settled figure, so a screen reader never reads the count-up. */}
          <p className="type-hero text-ink" aria-label={value}>
            <span aria-hidden>{shown}</span>
          </p>
          {delta && <Delta {...delta} />}
        </div>
        {label && <p className="mt-1 type-small text-ink-2">{label}</p>}
      </div>
      {aside && <div className="shrink-0">{aside}</div>}
    </div>
  )
}
