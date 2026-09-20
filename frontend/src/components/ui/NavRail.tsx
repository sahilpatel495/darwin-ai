import type { AnchorHTMLAttributes, ReactNode } from 'react'
import Tooltip from './Tooltip'
import { cx } from './cx'

export interface NavItemSpec {
  id: string
  /** Sentence case, one or two words. It is shown, not just announced. */
  label: string
  href: string
  icon: ReactNode
  /** Outside a project the project pages are off; a disabled item says why on hover. */
  disabled?: boolean
  /** Why it is off, e.g. "Open a project first". Shown as a tooltip. */
  disabledReason?: string
  /** Extra attributes, e.g. `data-tour="trust"` (§10). */
  anchorProps?: AnchorHTMLAttributes<HTMLAnchorElement> & { [key: `data-${string}`]: string }
}

export interface NavItemProps extends NavItemSpec {
  active: boolean
}

/** One destination: icon above its label. Active sits on blue-soft with a blue icon (§6 v2). */
export function NavItem({ label, href, icon, disabled, disabledReason, anchorProps, active }: NavItemProps) {
  const body = (
    <span
      className={cx(
        'flex w-full flex-col items-center gap-1 rounded-card px-1 py-2 type-micro no-underline',
        'transition-colors duration-100',
        active ? 'bg-blue-soft text-blue-ink' : 'text-ink-2',
        disabled ? 'opacity-40' : 'hover:bg-fill hover:text-ink',
      )}
    >
      <span aria-hidden className={cx('inline-flex', active && 'text-blue')}>
        {icon}
      </span>
      {label}
    </span>
  )

  if (disabled) {
    return (
      <li className="w-full">
        {/* Aligned to the rail's own left edge: a centred label on a 72px column is cut off by the window. */}
        <Tooltip label={disabledReason ?? 'Not available yet'} align="start" className="w-full">
          {/* Not a link: there is nowhere to go. A button says "this exists but not yet". */}
          <button type="button" disabled aria-disabled className="w-full cursor-not-allowed">
            {body}
          </button>
        </Tooltip>
      </li>
    )
  }

  return (
    <li className="w-full">
      <a href={href} aria-current={active ? 'page' : undefined} className="block no-underline" {...anchorProps}>
        {body}
      </a>
    </li>
  )
}

export interface NavRailProps {
  items: NavItemSpec[]
  /** The id of the item you are on. */
  active: string
  /** The open project. Its initials sit at the top of the rail, its name in the tooltip. */
  project?: { name: string; href: string } | null
  /** One control at the foot of the rail on desktop — the theme toggle. */
  footer?: ReactNode
  className?: string
}

/** Two initials from "Salary Register 2025 and 5 more" → "SR". A name is never blank here. */
const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('') || 'P'

/**
 * The one navigation in the product (§6 v2). One list, two shapes: a 72px rail down the left on
 * desktop, a bottom tab bar on phones. Same DOM both times, so there is one tab order, one
 * `aria-current`, and no duplicate landmark for a screen reader to read twice.
 */
export default function NavRail({ items, active, project, footer, className }: NavRailProps) {
  return (
    <nav
      aria-label="Sections"
      className={cx(
        'print-hide z-30 shrink-0 bg-surface',
        // Phone: a bar across the bottom, above the home indicator.
        'fixed inset-x-0 bottom-0 border-t border-line-soft pb-[env(safe-area-inset-bottom,0px)]',
        // Desktop: a column down the left.
        'md:static md:inset-auto md:w-[72px] md:border-t-0 md:border-r md:pb-0',
        className,
      )}
    >
      <div className="flex items-stretch md:h-full md:flex-col md:py-3">
        {project && (
          <a
            href={project.href}
            aria-label={`Project ${project.name}`}
            className="mx-auto mb-3 hidden size-9 shrink-0 items-center justify-center rounded-pill bg-blue-soft type-micro font-semibold text-blue-ink no-underline md:flex"
          >
            {initials(project.name)}
          </a>
        )}

        <ul className="flex flex-1 items-stretch justify-around gap-0.5 px-1 py-1 md:flex-col md:justify-start md:gap-1 md:px-2 md:py-0">
          {items.map((item) => (
            <NavItem key={item.id} {...item} active={item.id === active} />
          ))}
        </ul>

        {footer && <div className="hidden justify-center pt-3 md:flex">{footer}</div>}
      </div>
    </nav>
  )
}
