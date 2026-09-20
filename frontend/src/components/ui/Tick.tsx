import { cx } from './cx'

export interface TickProps {
  /** Side of the square box, in pixels. Default 16, which sits on a 24px line. */
  size?: number
  /** Draw the stroke in (§4). Off means the tick is simply already there. */
  animate?: boolean
  /** Milliseconds before the stroke starts. ProofList staggers its lines by 90. */
  delay?: number
  /** Name the tick when it is the only thing carrying the meaning; otherwise it stays silent. */
  title?: string
  className?: string
}

/**
 * The auditor's tick: a short down-stroke and a long flicked up-stroke, drawn by hand
 * rather than stamped. `pathLength={1}` lets the dash offset animate from 1 to 0 without
 * anyone measuring the curve.
 */
export default function Tick({ size = 16, animate = false, delay = 0, title, className }: TickProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 18 18"
      fill="none"
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      className={cx('shrink-0 text-audit', className)}
    >
      {title && <title>{title}</title>}
      <path
        d="M1.8 9.2C3.3 10 4.9 11.8 6.3 14.7 8.8 8.9 12.2 4.1 16.4 1.4"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
        className={animate ? 'animate-tick' : undefined}
        style={animate ? { strokeDasharray: 1, strokeDashoffset: 1, animationDelay: `${delay}ms` } : undefined}
      />
    </svg>
  )
}
