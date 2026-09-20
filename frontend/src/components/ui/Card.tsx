import { createElement } from 'react'
import type { HTMLAttributes, Ref } from 'react'
import { cx } from './cx'

export interface CardProps extends HTMLAttributes<HTMLElement> {
  /** The tag to render. Use `section` or `article` when the card is a landmark. */
  as?: 'div' | 'section' | 'article' | 'li' | 'a' | 'button'
  /** The whole card does something when clicked: it lifts on hover and takes the focus ring. */
  interactive?: boolean
  /** The large hero surfaces (§2): 12px corners and more padding around them. */
  hero?: boolean
  /** Drop the padding, for a card whose own header and body set it. */
  flush?: boolean
  ref?: Ref<HTMLElement>
}

/**
 * A white surface lifted off the grey wash by a 1px shadow. Cards are how this product groups
 * anything — a tile, an answer, a dialog body, a list container.
 *
 * Only an `interactive` card moves: a card that is merely a container never hovers (§4).
 * `data-ui="card"` is what the print stylesheet keys on to keep a card whole on one page.
 */
export default function Card({ as = 'div', interactive = false, hero = false, flush = false, className, ...rest }: CardProps) {
  return createElement(as, {
    'data-ui': 'card',
    className: cx(
      'bg-surface text-ink shadow-1',
      hero ? 'rounded-hero' : 'rounded-card',
      !flush && (hero ? 'p-5 sm:p-6' : 'p-4 sm:p-5'),
      interactive && 'card-hover block w-full cursor-pointer text-left',
      className,
    ),
    ...rest,
  })
}
