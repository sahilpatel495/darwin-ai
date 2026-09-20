import { cx } from './cx'

export interface SkeletonProps {
  /** Size it with utilities: `h-5 w-40`. Match the shape of what is loading. */
  className?: string
}

/**
 * A placeholder while something loads. Decorative, so it is hidden from screen readers —
 * put `role="status"` and a sentence on the container instead, so the wait is announced
 * once in words rather than as a row of empty boxes.
 */
export default function Skeleton({ className }: SkeletonProps) {
  return <div aria-hidden className={cx('animate-pulse rounded-chip bg-wash', className)} />
}
