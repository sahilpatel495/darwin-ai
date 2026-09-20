import { createElement } from 'react'
import type { HTMLAttributes, Ref } from 'react'
import { cx } from './cx'

export interface SheetProps extends HTMLAttributes<HTMLElement> {
  /** The tag to render. Use `section` or `article` when the sheet is a landmark. */
  as?: 'div' | 'section' | 'article' | 'li'
  ref?: Ref<HTMLElement>
}

/**
 * A white surface on paper, held by a hairline. The answer statement is the only sheet
 * in the thread — that is what makes it read as the statement. No shadow: shadows are
 * for things that float (dialogs, popovers).
 *
 * `data-ui="sheet"` is what the print stylesheet keys on to keep a statement on one page.
 */
export default function Sheet({ as = 'div', className, ...rest }: SheetProps) {
  return createElement(as, {
    'data-ui': 'sheet',
    className: cx('rounded-control border border-rule bg-sheet', className),
    ...rest,
  })
}
