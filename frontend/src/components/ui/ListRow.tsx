import { createElement } from 'react'
import type { HTMLAttributes, Ref } from 'react'
import { cx } from './cx'

export interface ListRowProps extends HTMLAttributes<HTMLElement> {
  as?: 'div' | 'li' | 'a' | 'button' | 'label'
  /** The row itself is clickable: it fills on hover. */
  hover?: boolean
  /** A hairline under the row. Off on the last row of a list inside a card. */
  divided?: boolean
  ref?: Ref<HTMLElement>
}

/**
 * One line of a list — a file, a link, a project, a glossary entry. Full width, so the whole
 * row is the target on a phone, and the fill on hover says so before the pointer arrives.
 */
export default function ListRow({ as = 'div', hover = false, divided = true, className, ...rest }: ListRowProps) {
  return createElement(as, {
    className: cx(
      'flex w-full items-start gap-3 rounded-input px-3 py-2.5 text-left',
      divided && 'border-b border-line-soft last:border-b-0',
      hover && 'press cursor-pointer hover:bg-fill',
      className,
    ),
    ...rest,
  })
}
