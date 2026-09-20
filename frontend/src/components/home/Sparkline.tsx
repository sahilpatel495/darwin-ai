// Fourteen days of questions, in the width of a thumbnail (§8). It carries no numbers of its own:
// the card says "12 questions, 3 saved" right beside it, so this is the shape of the work and not
// the measurement of it — which is why it is hidden from a screen reader rather than described.

import { cx } from '../ui'

export interface SparklineProps {
  /** One count per day, oldest first. */
  days: number[]
  className?: string
}

const W = 72
const H = 20

export default function Sparkline({ days, className }: SparklineProps) {
  if (days.length < 2) return null
  const peak = Math.max(1, ...days)
  const step = W / (days.length - 1)
  // A flat line sits on the baseline rather than in the middle: nothing happened, and the drawing
  // should say nothing happened.
  const points = days.map((count, i) => `${(i * step).toFixed(1)},${(H - 1 - (count / peak) * (H - 2)).toFixed(1)}`)

  return (
    <svg aria-hidden viewBox={`0 0 ${W} ${H}`} width={W} height={H} className={cx('shrink-0 overflow-visible', className)} fill="none">
      <polygon points={`0,${H} ${points.join(' ')} ${W},${H}`} fill="var(--color-primary)" opacity="0.1" />
      <polyline points={points.join(' ')} stroke="var(--color-primary)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
