// One project on Home (§15): what it is, which files it was built from, how much work is in it,
// and when it was last open. Renaming happens in place; deleting asks first and says exactly what
// goes. The whole card is the link — the name carries it, stretched over the card — so the menu
// beside it stays a menu and the card stays one stop in the tab order.

import { useState } from 'react'
import { resetSession } from '../../api'
import { deleteProject, lastOpened, projectSummary, updateProject } from '../../lib/projects'
import type { ProjectRecord } from '../../lib/projects'
import { projectPath } from '../../lib/route'
import { Button, Card, Dialog, Menu, MoreIcon } from '../ui'
import RenameField from '../shell/RenameField'

interface ProjectCardProps {
  project: ProjectRecord
  /** Re-read the list: this card has renamed or deleted itself. */
  onChanged: () => void
}

const count = (n: number, one: string, many: string) => `${n === 0 ? 'no' : n} ${n === 1 ? one : many}`

/** Three names, then how many are left. A card is not the place to read a file list. */
const SHOWN_FILES = 3

export default function ProjectCard({ project, onChanged }: ProjectCardProps) {
  const [renaming, setRenaming] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const files = project.fileNames
  const more = files.length - SHOWN_FILES
  const saved = project.savedAnswerIds.length + project.savedTiles.length

  function remove() {
    deleteProject(project.id)
    // ponytail: resetSession() drops whatever session this tab holds, and it holds one at a time,
    // so deleting a project with files still loaded drops the right ones. If two projects ever
    // hold live sessions at once, api.ts needs a deleteSession(id).
    if (project.sessionId) resetSession()
    setConfirming(false)
    onChanged()
  }

  return (
    <Card as="article" className="card-hover relative flex min-w-0 flex-col gap-3">
      <div className="flex min-w-0 items-start gap-2">
        {renaming ? (
          <RenameField
            name={project.name}
            className="flex-1"
            onSave={(name) => {
              updateProject(project.id, { name })
              setRenaming(false)
              onChanged()
            }}
            onCancel={() => setRenaming(false)}
          />
        ) : (
          // The stretched link: one link for the whole card, so a screen reader hears one
          // destination and a pointer can hit anywhere that is not the menu.
          <h2 className="min-w-0 flex-1 type-section text-ink">
            <a href={projectPath(project.id)} className="text-ink no-underline after:absolute after:inset-0 hover:underline">
              {project.name}
            </a>
          </h2>
        )}

        <Menu
          trigger={<MoreIcon size={18} />}
          triggerLabel={`Actions for ${project.name}`}
          className="press relative z-10 inline-flex size-7 shrink-0 items-center justify-center rounded-pill text-ink-2 hover:bg-fill hover:text-ink"
          actions={[
            { id: 'rename', label: 'Rename', onSelect: () => setRenaming(true) },
            { id: 'delete', label: 'Delete', onSelect: () => setConfirming(true) },
          ]}
        />
      </div>

      {files.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {files.slice(0, SHOWN_FILES).map((name) => (
            <li key={name} className="max-w-full truncate rounded-pill bg-fill px-2.5 py-1 type-micro text-ink-2" title={name}>
              {name}
            </li>
          ))}
          {more > 0 && <li className="rounded-pill bg-fill px-2.5 py-1 type-micro text-ink-2">{`+${more} more`}</li>}
        </ul>
      )}

      <div className="mt-auto flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 type-small text-ink-2">
        <span>{projectSummary(project)}</span>
        <span>{lastOpened(project.lastOpenedAt)}</span>
      </div>

      <Dialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Delete this project?"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Keep it
            </Button>
            <Button variant="primary" onClick={remove}>
              Delete the project
            </Button>
          </>
        }
      >
        <p>
          <span className="font-semibold">{project.name}</span> will be removed from this browser, with {count(project.turns.length, 'question', 'questions')} and{' '}
          {saved === 0 ? 'nothing' : saved} on its board. The files on your own computer are not touched.
        </p>
        {project.sessionId && <p className="mt-2 text-ink-2">The copy on our server, loaded for answering, is dropped now rather than in two hours.</p>}
      </Dialog>
    </Card>
  )
}
