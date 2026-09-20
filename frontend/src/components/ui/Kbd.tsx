import type { ReactNode } from 'react'
import { cx } from './cx'

export interface KbdProps {
  children: ReactNode
  className?: string
}

/** One key, as it is printed on the keyboard: `⌘K`, `↵`, `Esc`. Never a sentence. */
export default function Kbd({ children, className }: KbdProps) {
  return (
    <kbd
      className={cx(
        'inline-flex h-6 min-w-6 items-center justify-center rounded-md border border-hairline-soft bg-surface-soft px-1.5',
        'font-sans text-caption font-bold text-charcoal',
        className,
      )}
    >
      {children}
    </kbd>
  )
}
