import { createElement } from 'react'
import type { HTMLAttributes, Ref } from 'react'
import { cx } from './cx'

export interface CardProps extends HTMLAttributes<HTMLElement> {
  /** The tag to render. Use `section` or `article` when the card is a landmark. */
  as?: 'div' | 'section' | 'article' | 'li' | 'a' | 'button'
  /** `canvas` white · `soft` the pale tile · `dark` the showcase card, ink with light text. */
  tone?: 'canvas' | 'soft' | 'dark'
  /** `xl` 16 small tiles · `xxl` 24 the standard card · `xxxl` 32 hero frames and showcase cards. */
  radius?: 'xl' | 'xxl' | 'xxxl'
  /** The whole card does something when clicked: its border firms up and it lifts 2px. */
  interactive?: boolean
  /** Drop the padding, for a card whose own header and body set it. */
  flush?: boolean
  /** TEMPORARY alias for `radius="xxxl"`. */
  hero?: boolean
  ref?: Ref<HTMLElement>
}

const TONE = {
  canvas: 'bg-canvas text-ink border-hairline-soft',
  soft: 'bg-surface-soft text-ink border-transparent',
  dark: 'bg-ink-deep text-white border-transparent',
} as const

const RADIUS = { xl: 'rounded-xl', xxl: 'rounded-xxl', xxxl: 'rounded-xxxl' } as const
// Card padding 32, 24 on phones (§2). A small tile gets less, or the 16px corner swallows it.
const PAD = { xl: 'p-5 sm:p-6', xxl: 'p-6 sm:p-8', xxxl: 'p-6 sm:p-8' } as const

/**
 * A surface bounded by a hairline. **Never a shadow** (§2): elevation in v3 is space and a line,
 * and the two things that do lift — the docked composer and a drawer — say so themselves.
 *
 * Only an `interactive` card moves. `data-ui="card"` is what the print stylesheet keys on to
 * keep a card whole on one page.
 */
export default function Card({
  as = 'div',
  tone = 'canvas',
  radius,
  interactive = false,
  flush = false,
  hero = false,
  className,
  ...rest
}: CardProps) {
  const r = radius ?? (hero ? 'xxxl' : 'xxl')
  return createElement(as, {
    'data-ui': 'card',
    className: cx(
      'border',
      TONE[tone],
      RADIUS[r],
      !flush && PAD[r],
      interactive && 'card-hover block w-full cursor-pointer text-left',
      className,
    ),
    ...rest,
  })
}
