// The top bar of every screen (§6.3 v2). The nav rail is the navigation now, so nothing here
// navigates except the wordmark: this bar carries what is true of the screen you are on — the
// open project's name (click to rename) and whatever that page can do — plus the two things that
// belong to no page, the privacy promise and the light/dark switch.
//
// What used to sit here and no longer does: "Saved answers (n)" and "Trust Report". Both are
// items in the rail at every width, and the same link in two places is two things to scan.

import { useState } from 'react'
import type { ReactNode } from 'react'
import { HOME } from '../../lib/route'
import HowItWorksDialog from '../education/HowItWorksDialog'
import { Button, ThemeToggle } from '../ui'
import { LockIcon } from './icons'
import RenameField from './RenameField'

export interface HeaderProps {
  /** The open project. Its name is editable here. */
  project?: { id: string; name: string }
  onRename?: (name: string) => void
  /** On the Trust Report, the way back to what you were reading. */
  back?: { href: string; label: string }
  /** Runs the first-run tour again (§6.7). Offered inside "How Verity works". */
  onReplayTour?: () => void
  /** What this page can do, e.g. the Ask page's "Data" button. */
  actions?: ReactNode
}

export default function Header({ project, onRename, back, onReplayTour, actions }: HeaderProps) {
  const [renaming, setRenaming] = useState(false)
  const [explaining, setExplaining] = useState(false)

  return (
    <header className="shrink-0 border-b border-line-soft bg-surface print-hide">
      <div className="flex w-full items-center gap-2 px-4 py-2 sm:px-6">
        <a href={HOME} className="shrink-0 type-section font-bold tracking-tight text-ink no-underline">
          Verity
        </a>

        {back && (
          <>
            <span aria-hidden className="h-4 w-px shrink-0 bg-line" />
            <a href={back.href} className="min-w-0 truncate type-small">
              {back.label}
            </a>
          </>
        )}

        {project && (
          <>
            <span aria-hidden className="h-4 w-px shrink-0 bg-line" />
            {renaming && onRename ? (
              <RenameField
                name={project.name}
                onSave={(name) => {
                  onRename(name)
                  setRenaming(false)
                }}
                onCancel={() => setRenaming(false)}
                className="min-w-0 flex-1"
              />
            ) : (
              <button
                type="button"
                onClick={() => onRename && setRenaming(true)}
                aria-label={onRename ? `Rename project ${project.name}` : undefined}
                className="press min-w-0 truncate rounded-input px-1.5 py-1 type-body font-medium text-ink hover:bg-fill"
              >
                {project.name}
              </button>
            )}
          </>
        )}

        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          {actions}

          {/* The privacy promise is one press from every screen, at every width: it is the claim
              the whole product rests on, so it never hides in a menu. */}
          <Button variant="ghost" size="sm" onClick={() => setExplaining(true)} aria-haspopup="dialog" className="gap-1.5 text-green-ink hover:bg-green-soft">
            <LockIcon size={16} />
            <span className="max-sm:sr-only">How Verity works</span>
          </Button>

          {/* The icon variant, not the three named options: a popover is 288px wide and "Match
              my system" ellipsises inside it, which is a worse control than one button whose
              label says where pressing it goes. It lives here rather than in the nav rail
              because the rail's footer is hidden on phones. */}
          <ThemeToggle />
          {/* "Show me around again" is not here: it lives in How Verity works, one press away,
              where the analyst is already being shown around. */}
        </div>
      </div>

      <HowItWorksDialog
        open={explaining}
        onClose={() => setExplaining(false)}
        onReplayTour={
          onReplayTour &&
          (() => {
            setExplaining(false)
            onReplayTour()
          })
        }
      />
    </header>
  )
}
