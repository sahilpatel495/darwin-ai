import type { ReactNode } from 'react'
import { cx } from './cx'

export interface AccordionItem {
  id: string
  /** The question, in the analyst's words. Sentence case. */
  question: ReactNode
  answer: ReactNode
}

export interface AccordionProps {
  items: AccordionItem[]
  /** Open this one on arrival. One at most: an accordion that starts open is not an accordion. */
  defaultOpenId?: string
  className?: string
}

/**
 * The FAQ shape (§7): one `xl` item per question, hairline-bounded, opening in 300ms.
 *
 * `<details>` and `<summary>`, not a pile of ARIA: the browser already gives them a button role,
 * an expanded state, Enter and Space, and find-in-page that opens the matching item. The only
 * thing added here is the chevron and the reveal, which `::details-content` animates natively in
 * 2026 browsers and which simply appears in the ones that do not.
 */
export default function Accordion({ items, defaultOpenId, className }: AccordionProps) {
  return (
    <div className={cx('space-y-3', className)}>
      {items.map((item) => (
        <details
          key={item.id}
          open={item.id === defaultOpenId}
          className="group rounded-xl border border-hairline-soft bg-canvas open:bg-surface-soft"
        >
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-5 text-subtitle-lg text-ink-deep marker:hidden [&::-webkit-details-marker]:hidden">
            {item.question}
            <svg
              aria-hidden
              viewBox="0 0 20 20"
              fill="none"
              className="size-5 shrink-0 text-charcoal transition-transform duration-[var(--dur-panel)] ease-[var(--ease-in-out)] group-open:rotate-180"
            >
              <path d="m5.5 8 4.5 4.5L14.5 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </summary>
          <div className="px-6 pb-5 text-body-md text-slate">{item.answer}</div>
        </details>
      ))}
    </div>
  )
}
