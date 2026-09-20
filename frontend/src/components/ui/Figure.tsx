import { cx } from './cx'

export interface FigureProps {
  /** The already-formatted display string, e.g. "₹20.40 Cr" or "12.4%". Never a raw number. */
  value: string
  /** One short line under the rule: what the figure counts. */
  caption?: string
  /** Extend the rule left to right when the answer arrives (§4). */
  animate?: boolean
  className?: string
}

/**
 * The headline figure with the double rule beneath it — the one bold element in the
 * product. Two 1px rules 2px apart, the accountant's mark for a total that has been
 * checked and closed.
 */
export default function Figure({ value, caption, animate = false, className }: FigureProps) {
  return (
    // `w-fit` rather than inline-block: the rule has to hug the number, but two figures in
    // a column must still stack.
    <div className={cx('block w-fit', className)}>
      <p className="type-figure text-ink">{value}</p>
      {/* border-box: 4px tall = 1px rule, 2px gap, 1px rule. */}
      <div
        aria-hidden
        className={cx('mt-2 h-[4px] origin-left border-t border-b border-rule-strong', animate && 'animate-rule')}
      />
      {caption && <p className="mt-2 type-small text-ink-soft">{caption}</p>}
    </div>
  )
}
