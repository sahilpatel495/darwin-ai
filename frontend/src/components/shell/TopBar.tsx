// The one piece of app chrome (§6): a sticky 64px bar, on every screen once somebody is signed in.
// There is no left rail and no permanent side panel — everything that used to live down the left
// is either a tab in the middle of this bar or one press away on the right.
//
// Left: the wordmark and the project switcher. Centre: the four sections. Right: search, Data,
// and you. On a phone the four sections move to the bottom tab bar, where a thumb reaches them.

import { analysesPath, boardPath, go, HOW, overviewPath, PROJECTS, projectPath, SETTINGS, SIGNUP, TRUST } from '../../lib/route'
import type { Route } from '../../lib/route'
import type { ProjectRecord } from '../../lib/projects'
import type { User } from '../../types'
import { Avatar, Badge, ChevronIcon, DataIcon, Kbd, Menu, PillTabs, SearchIcon, cx } from '../ui'

export interface TopBarProps {
  route: Route
  /** The open project, if the route is about one. */
  project?: ProjectRecord | null
  /** Newest first. The switcher offers the first few by name. */
  projects: ProjectRecord[]
  user: User | null
  /** Opens the Data drawer. Given only where there is a project to show data for. */
  onOpenData?: () => void
  /** Opens the command palette. ⌘K is bound by App, which also owns the palette. */
  onOpenSearch: () => void
  onSignOut: () => void
}

/** Which of the four tabs is lit. */
const TAB: Partial<Record<Route['name'], string>> = {
  project: 'ask',
  overview: 'overview',
  analyses: 'analyses',
  board: 'board',
}

/** Enough to recognise your own work without turning a menu into a list. */
const RECENT = 5

export default function TopBar({ route, project, projects, user, onOpenData, onOpenSearch, onSignOut }: TopBarProps) {
  const guest = user?.kind !== 'member'
  const name = user?.name ?? 'Guest'

  const tabs = project
    ? [
        { id: 'ask', label: 'Ask', href: projectPath(project.id) },
        { id: 'overview', label: 'Overview', href: overviewPath(project.id) },
        { id: 'analyses', label: 'Analyses', href: analysesPath(project.id) },
        { id: 'board', label: 'Saved', href: boardPath(project.id) },
      ]
    : []

  const recent = projects.filter((other) => other.id !== project?.id).slice(0, RECENT)
  const switcher = [
    ...recent.map((other) => ({ id: other.id, label: other.name, onSelect: () => go(projectPath(other.id)) })),
    { id: 'all', label: 'All projects', onSelect: () => go(PROJECTS) },
    { id: 'new', label: 'New project', onSelect: () => go(PROJECTS) },
  ]

  return (
    <header className="sticky top-0 z-30 shrink-0 border-b border-hairline-soft bg-canvas print-hide" style={{ top: 'env(safe-area-inset-top, 0px)' }}>
      <div className="mx-auto flex h-16 w-full max-w-[1120px] items-center gap-2 px-4 sm:gap-3 sm:px-6">
        <a href={PROJECTS} className="shrink-0 text-subtitle-lg tracking-[-0.02em] text-ink-deep no-underline">
          DarwinLens
        </a>

        {project && (
          <Menu
            align="left"
            triggerLabel={`Project: ${project.name}. Switch project.`}
            className="press hidden min-w-0 items-center gap-1.5 rounded-full border border-hairline-soft px-3.5 py-1.5 text-body-sm text-ink hover:border-hairline md:inline-flex"
            trigger={
              <>
                <span className="max-w-[16ch] truncate">{project.name}</span>
                <ChevronIcon size={14} className="shrink-0 rotate-90 text-charcoal" />
              </>
            }
            actions={switcher}
          />
        )}

        {/* The four sections. On a phone they are the bottom tab bar instead. */}
        {project && <PillTabs label="Sections of this project" size="sm" tabs={tabs} active={TAB[route.name] ?? ''} className="mx-auto hidden md:block" />}

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onOpenSearch}
            className="press hidden h-10 items-center gap-2 rounded-full bg-surface-soft pr-2 pl-4 text-body-sm text-steel hover:text-ink lg:inline-flex"
          >
            <SearchIcon size={16} />
            Search or ask…
            <Kbd className="bg-canvas">⌘K</Kbd>
          </button>
          {/* The same thing, where there is no room for the words. */}
          <button
            type="button"
            aria-label="Search or ask"
            onClick={onOpenSearch}
            className="press inline-flex size-10 items-center justify-center rounded-circle bg-surface-soft text-charcoal hover:text-ink lg:hidden"
          >
            <SearchIcon size={18} />
          </button>

          {onOpenData && project && (
            <button
              type="button"
              onClick={onOpenData}
              className="press inline-flex h-10 items-center gap-2 rounded-full border border-hairline-soft px-3 text-button-md text-ink-deep hover:border-hairline sm:px-4"
            >
              <DataIcon size={18} />
              <span className="hidden sm:inline">Data</span>
              {/* The count is a fact about the project, so it is a Badge and not a dot. Cobalt
                  while there are files; plain while there are none to look at. */}
              <Badge tone="neutral" className={cx('px-2 tnum', project.fileNames.length > 0 && 'bg-primary-soft text-primary-deep')}>
                {project.fileNames.length}
              </Badge>
            </button>
          )}

          <Menu
            align="right"
            triggerLabel={`Your account: ${name}`}
            className="press rounded-circle"
            trigger={<Avatar name={name} guest={guest} />}
            actions={[
              { id: 'settings', label: 'Profile and usage', onSelect: () => go(SETTINGS) },
              { id: 'how', label: 'How DarwinLens works', onSelect: () => go(HOW) },
              { id: 'trust', label: 'Trust report', onSelect: () => go(TRUST) },
              guest
                ? { id: 'signup', label: 'Create an account', onSelect: () => go(SIGNUP) }
                : { id: 'signout', label: 'Sign out', onSelect: onSignOut },
            ]}
          />
        </div>
      </div>
    </header>
  )
}
