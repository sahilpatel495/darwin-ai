// The top rule of every page (§6.3): the wordmark, the open project's name, and the three places
// you can go from anywhere. Below 768px the secondary items collapse into one menu, because a
// phone header that wraps to three lines pushes the answer off the screen.

import { useState } from 'react'
import { boardPath, HOME, TRUST } from '../../lib/route'
import HowItWorksDialog from '../education/HowItWorksDialog'
import { Popover } from '../ui'
import { ShieldIcon } from './icons'
import RenameField from './RenameField'

export interface HeaderProps {
  /** The open project. Its name is editable here and its board is one click away. */
  project?: { id: string; name: string; savedCount: number }
  onRename?: (name: string) => void
  /** On the Trust Report, the way back to what you were reading. */
  back?: { href: string; label: string }
  /** Runs the first-run tour again (§6.7). Offered inside "How Verity works", which is the one
   *  help surface §6.3 allows in this header — a fourth top-level item is not. */
  onReplayTour?: () => void
}

const item = 'rounded-control px-2 py-1 type-small font-medium text-ink-soft no-underline hover:bg-wash hover:text-ink'

export default function Header({ project, onRename, back, onReplayTour }: HeaderProps) {
  const [renaming, setRenaming] = useState(false)
  const [explaining, setExplaining] = useState(false)

  const saved = project && (
    <a href={boardPath(project.id)} className={item}>
      Saved answers ({project.savedCount})
    </a>
  )
  const trust = back ? (
    <a href={back.href} className={item}>
      {back.label}
    </a>
  ) : (
    <a href={TRUST} data-tour="trust" className={item}>
      Trust Report
    </a>
  )
  const privacy = (
    <button type="button" onClick={() => setExplaining(true)} aria-haspopup="dialog" className={`${item} inline-flex items-center gap-1.5 text-audit`}>
      <ShieldIcon />
      How Verity works
    </button>
  )

  return (
    <header className="shrink-0 border-b border-rule bg-paper print-hide">
      <div className="mx-auto flex w-full max-w-6xl items-center gap-2 px-4 py-2 sm:px-6">
        <a href={HOME} className="shrink-0 font-serif text-[17px] font-semibold tracking-tight text-ink no-underline">
          Verity
        </a>

        {project && (
          <>
            <span aria-hidden className="h-4 w-px shrink-0 bg-rule" />
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
                className="min-w-0 truncate rounded-control px-1.5 py-1 type-body text-ink hover:bg-wash"
              >
                {project.name}
              </button>
            )}
          </>
        )}

        <div className="ml-auto flex shrink-0 items-center gap-1 max-md:hidden">
          {saved}
          {trust}
          {privacy}
        </div>

        {/* On a phone the same three or four items are one button, because a header that wraps to
            three lines pushes the answer off the screen. */}
        <Popover trigger="Menu" triggerLabel="Menu" align="right" className={`ml-auto shrink-0 ${item} md:hidden`}>
          <div className="flex flex-col items-start gap-0.5">
            {saved}
            {trust}
            {privacy}
          </div>
        </Popover>
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
