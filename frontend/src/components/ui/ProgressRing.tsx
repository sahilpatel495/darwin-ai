import { cx } from './cx'

export interface ProgressRingProps {
  /** How far along, 0 to 1. */
  value: number
  /** Diameter in pixels. 48 beside a heading, 96 in the onboarding sequence. */
  size?: number
  /** What the ring is measuring, e.g. "Reading your files". Required: a ring is not self-explaining. */
  label: string
  /** What sits in the middle. Usually the step count, e.g. "2 of 3". */
  children?: React.ReactNode
  className?: string
}

/**
 * A ring that closes as something finishes (§4): onboarding's three steps, an upload, a run.
 * The stroke is drawn with `stroke-dasharray`, so the whole thing is one SVG circle and the
 * animation is a single transitioned property.
 */
export default function ProgressRing({ value, size = 64, label, children, className }: ProgressRingProps) {
  const stroke = Math.max(3, Math.round(size / 14))
  const r = (size - stroke) / 2
  const circumference = 2 * Math.PI * r
  const done = Math.min(1, Math.max(0, value))

  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={Math.round(done * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      style={{ width: size, height: size }}
      className={cx('relative inline-flex shrink-0 items-center justify-center', className)}
    >
      <svg aria-hidden width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-hairline-soft)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--color-primary)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - done)}
          style={{ transition: 'stroke-dashoffset var(--dur-long) var(--ease-out)' }}
        />
      </svg>
      {children && <span className="absolute text-body-sm font-bold text-ink-deep tnum">{children}</span>}
    </div>
  )
}
