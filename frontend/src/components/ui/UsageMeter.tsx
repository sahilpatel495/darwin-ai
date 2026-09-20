import { cx } from './cx'

export interface UsageMeterProps {
  /** What is being counted, e.g. "Questions this hour". */
  label: string
  used: number
  limit: number
  /** One quiet line under the bar, e.g. "Resets at 4pm." */
  note?: string
  className?: string
}

/**
 * How much of an allowance is gone (§8, Settings). A `<meter>` would be the native answer, but its
 * bar is unstyleable across browsers and the colour is the whole point here, so this draws one and
 * carries the same semantics in ARIA.
 *
 * The bar turns amber at four-fifths and critical when it is full — and the words above it say the
 * same thing, so nothing depends on seeing the colour.
 */
export default function UsageMeter({ label, used, limit, note, className }: UsageMeterProps) {
  const safeLimit = Math.max(1, limit)
  const fraction = Math.min(1, Math.max(0, used / safeLimit))
  const tone = fraction >= 1 ? 'bg-critical' : fraction >= 0.8 ? 'bg-attention' : 'bg-primary'

  return (
    <div className={className}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-body-sm font-bold text-ink-deep">{label}</span>
        <span className="text-body-sm text-slate tnum">
          {Math.max(0, safeLimit - used)} left of {safeLimit}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuenow={used}
        aria-valuemin={0}
        aria-valuemax={safeLimit}
        className="mt-2 h-2 overflow-hidden rounded-full bg-surface-soft"
      >
        <div
          className={cx('h-full rounded-full', tone)}
          style={{ width: `${fraction * 100}%`, transition: 'width var(--dur-draw) var(--ease-out)' }}
        />
      </div>
      {note && <p className="mt-2 text-body-sm text-steel">{note}</p>}
    </div>
  )
}
