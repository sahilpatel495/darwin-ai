import { CheckIcon } from './icons'
import { cx } from './cx'

export interface CheckProps {
  /** Side of the circle, in pixels. Default 18, which sits on a 22px line. */
  size?: number
  /** Pop in when the answer arrives (§4). Off means the check is simply already there. */
  animate?: boolean
  /** Milliseconds before it pops. VerifiedList staggers its lines by 90. */
  delay?: number
  /** Name it when it is the only thing carrying the meaning; otherwise it stays silent. */
  title?: string
  className?: string
}

/**
 * Checked, in a green circle. Replaces the old hand-drawn Tick: the green disc is what makes a
 * verified line readable at a glance in a column of them, and it survives dark mode, which a
 * thin ink stroke did not.
 */
export default function Check({ size = 18, animate = false, delay = 0, title, className }: CheckProps) {
  return (
    <span
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      style={{ width: size, height: size, animationDelay: animate ? `${delay}ms` : undefined }}
      className={cx('inline-flex shrink-0 items-center justify-center rounded-full bg-success text-white', animate && 'check-pop', className)}
    >
      <CheckIcon size={Math.round(size * 0.72)} strokeWidth={2.4} />
    </span>
  )
}
