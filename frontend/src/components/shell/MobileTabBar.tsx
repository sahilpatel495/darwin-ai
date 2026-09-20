// The four sections on a phone (§6). The top bar keeps the wordmark, Data and the avatar; the
// tabs move down here, where a thumb reaches them.
//
// A separate element from the top bar's PillTabs rather than the same DOM shown twice: the two
// shapes want different markup (icon over label against a row of pills), and `aria-current` on
// the one that is hidden at this width would have a screen reader read the navigation twice.

import { analysesPath, boardPath, overviewPath, projectPath } from '../../lib/route'
import type { Route } from '../../lib/route'
import { AnalysesIcon, AskIcon, OverviewIcon, SavedIcon, cx } from '../ui'

export interface MobileTabBarProps {
  route: Route
  projectId: string
}

const TAB: Partial<Record<Route['name'], string>> = {
  project: 'ask',
  overview: 'overview',
  analyses: 'analyses',
  board: 'board',
}

export default function MobileTabBar({ route, projectId }: MobileTabBarProps) {
  const active = TAB[route.name] ?? ''
  const items = [
    { id: 'ask', label: 'Ask', href: projectPath(projectId), icon: <AskIcon /> },
    { id: 'overview', label: 'Overview', href: overviewPath(projectId), icon: <OverviewIcon /> },
    { id: 'analyses', label: 'Analyses', href: analysesPath(projectId), icon: <AnalysesIcon /> },
    { id: 'board', label: 'Saved', href: boardPath(projectId), icon: <SavedIcon /> },
  ]

  return (
    <nav
      aria-label="Sections of this project"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-hairline-soft bg-canvas pb-[env(safe-area-inset-bottom,0px)] print-hide md:hidden"
    >
      <ul className="flex items-stretch justify-around px-2 py-1.5">
        {items.map((item) => {
          const on = item.id === active
          return (
            <li key={item.id} className="min-w-0 flex-1">
              <a
                href={item.href}
                aria-current={on ? 'page' : undefined}
                className={cx(
                  'flex flex-col items-center gap-0.5 rounded-xl px-1 py-1.5 text-caption font-bold no-underline',
                  'transition-[color] duration-150',
                  on ? 'text-ink-deep' : 'text-steel',
                )}
              >
                <span aria-hidden className={cx('inline-flex rounded-full px-4 py-1', on && 'bg-primary-soft text-primary-deep')}>
                  {item.icon}
                </span>
                {item.label}
              </a>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
