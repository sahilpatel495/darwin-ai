// The small line beside a figure on the Overview (§8): the section's own trend, drawn at a size
// where only the shape is readable — which is all a sparkline is for.
//
// Hand-drawn SVG rather than Recharts: a polyline of twelve points needs no axes, no tooltip and
// no responsive container, and the chart library's smallest chart is heavier than this whole file.
//
// The series comes through a context because the numbers belong to a *sibling* tile (the section's
// trend) while the sparkline belongs inside the figure's card — and `TileCardProps` is a seam
// other screens depend on, so it cannot grow a prop. Nothing provides the context on the saved
// board, so a printed figure is simply a figure.

import { createContext, useContext } from 'react'
import { cx } from '../ui'

export interface Spark {
  points: number[]
  /** The trend tile's own title: printed under the line, so it is never a mystery shape. */
  label: string
}

const SparkContext = createContext<Spark | null>(null)
export const SparkProvider = SparkContext.Provider
export const useSpark = (): Spark | null => useContext(SparkContext)

/** 100×30 user units, stretched to the box: the stroke stays 1.5px because it does not scale. */
export default function Sparkline({ points, label, className }: Spark & { className?: string }) {
  if (points.length < 2) return null
  const low = Math.min(...points)
  const span = Math.max(...points) - low || 1
  const step = 100 / (points.length - 1)
  const at = (value: number, i: number) => `${(i * step).toFixed(2)},${(28 - ((value - low) / span) * 26).toFixed(2)}`
  const line = points.map(at).join(' ')

  return (
    <figure className={cx('w-[104px] sm:w-[128px]', className)}>
      <svg viewBox="0 0 100 30" preserveAspectRatio="none" role="img" aria-label={label} className="h-9 w-full">
        <polygon points={`0,30 ${line} 100,30`} fill="var(--color-primary)" opacity="0.1" />
        <polyline
          points={line}
          fill="none"
          stroke="var(--color-primary)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <figcaption className="mt-1 truncate text-right text-caption text-steel">{label}</figcaption>
    </figure>
  )
}
