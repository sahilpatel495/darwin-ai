// The frame around the landing page (§7): the promo strip, the nav and the footer.
//
// Separate from the app's TopBar on purpose. A signed-out visitor has no project to switch, no
// tabs to move between and no data to open, so putting them in front of that bar would be showing
// them the controls of something they have not been let into yet. This chrome has exactly two
// jobs: say what the product is, and offer the two ways in.

import { HOW, SIGNIN, SIGNUP, TRUST } from '../../lib/route'
import { cx } from '../ui'
import { DISCLAIMER, TAGLINE } from './copy'

/** A nav link. A pill, not an underlined word: a row of underlined words is not navigation. */
function NavLink({ href, children, className }: { href: string; children: string; className?: string }) {
  return (
    <a
      href={href}
      className={cx(
        'press shrink-0 rounded-full px-3 py-2 text-button-md whitespace-nowrap text-ink-deep no-underline hover:bg-surface-soft sm:px-4',
        className,
      )}
    >
      {children}
    </a>
  )
}

/**
 * The one dark strip on a white page (§7). `warning` is scoped to this strip and nowhere else,
 * so it is a single dot rather than a block of yellow — enough to catch the eye above a 64px
 * headline without competing with it.
 */
export function PromoStrip() {
  return (
    <div className="bg-ink-deep px-4 py-2.5 text-center">
      <p className="text-body-sm text-white">
        <span aria-hidden className="mr-2 inline-block size-1.5 translate-y-[-1px] rounded-full bg-warning" />
        Runs on open-weight models. Your rows never reach the AI.
      </p>
    </div>
  )
}

export function MarketingNav() {
  return (
    <nav aria-label="DarwinLens" className="border-b border-hairline-soft bg-canvas">
      <div className="mx-auto flex h-18 w-full max-w-[1200px] items-center gap-2 px-4 sm:px-6">
        {/* The wordmark steps down at 390: at `heading-sm` it and the two ways in add up to more
            than the viewport, and a nav bar that scrolls sideways is the first thing a phone
            visitor sees go wrong. */}
        <a href="#/" className="mr-auto text-subtitle-lg text-ink-deep no-underline sm:text-heading-sm">
          DarwinLens
        </a>
        {/* The two reference links fold away on a phone: the footer carries them, and the two
            things a visitor came to do must not be pushed off the row by them. */}
        <NavLink href={HOW} className="hidden sm:inline-block">
          How it works
        </NavLink>
        <NavLink href={TRUST} className="hidden sm:inline-block">
          Trust
        </NavLink>
        <NavLink href={SIGNIN}>Sign in</NavLink>
        <a
          href={SIGNUP}
          className="press inline-flex h-11 shrink-0 items-center rounded-full bg-ink-deep px-5 text-button-md whitespace-nowrap text-white no-underline hover:bg-ink sm:px-[30px]"
        >
          Get started
        </a>
      </div>
    </nav>
  )
}

const FOOTER_LINKS: [string, [string, string][]][] = [
  [
    'Product',
    [
      ['How it works', HOW],
      ['Trust report', TRUST],
      ['Primitives', '#/ui'],
    ],
  ],
  [
    'Get started',
    [
      ['Create an account', SIGNUP],
      ['Sign in', SIGNIN],
    ],
  ],
]

export function MarketingFooter() {
  return (
    <footer className="border-t border-hairline-soft bg-canvas">
      <div className="mx-auto grid w-full max-w-[1200px] grid-cols-1 gap-10 px-4 py-14 sm:grid-cols-2 sm:px-6 lg:grid-cols-4">
        <div className="lg:col-span-2">
          <p className="text-heading-sm text-ink-deep">DarwinLens</p>
          <p className="mt-2 measure text-body-md text-slate">{TAGLINE}</p>
        </div>
        {FOOTER_LINKS.map(([heading, links]) => (
          <div key={heading}>
            <h2 className="text-body-sm font-bold text-ink-deep">{heading}</h2>
            <ul className="mt-3 space-y-2">
              {links.map(([label, href]) => (
                <li key={label}>
                  <a href={href} className="text-body-md text-slate no-underline hover:text-ink-deep">
                    {label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="mx-auto w-full max-w-[1200px] border-t border-hairline-soft px-4 py-6 sm:px-6">
        <p className="measure text-body-sm text-steel">{DISCLAIMER}</p>
      </div>
    </footer>
  )
}
