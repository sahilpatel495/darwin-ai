import { cx } from './cx'

export interface SkeletonProps {
  /** Size it with utilities: `h-5 w-40`. Match the shape of what is loading. */
  className?: string
}

/**
 * A placeholder while something loads, with a light sweeping across it at 1.2s (§4).
 * Decorative, so it is hidden from screen readers — put `role="status"` and a sentence on the
 * container instead, so the wait is announced once in words rather than as a row of empty boxes.
 */
export default function Skeleton({ className }: SkeletonProps) {
  return <div aria-hidden className={cx('shimmer rounded-input bg-fill', className)} />
}
