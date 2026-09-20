import { createElement } from 'react'
import type { HTMLAttributes, Ref } from 'react'
import { cx } from './cx'

export interface RuledRowProps extends HTMLAttributes<HTMLElement> {
  as?: 'div' | 'li'
  /** Wash the row on hover. Only for a row that is itself clickable. */
  hover?: boolean
  ref?: Ref<HTMLElement>
}

/**
 * A row on paper, closed by a rule underneath — a line in a register, not a card.
 * Lists of files, links, projects and glossary entries are all made of these.
 * The last row keeps its rule: it is what closes the column.
 */
export default function RuledRow({ as = 'div', hover = false, className, ...rest }: RuledRowProps) {
  return createElement(as, {
    className: cx('flex items-start gap-3 border-b border-rule py-3', hover && 'hover:bg-wash', className),
    ...rest,
  })
}
