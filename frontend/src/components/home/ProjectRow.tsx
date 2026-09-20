// One line in the register of projects (§6.1): what it is, how much work is in it, when it was
// last open. Renaming happens in place; deleting asks first and says exactly what goes.

import { useState } from 'react'
import { resetSession } from '../../api'
import { deleteProject, lastOpened, projectSummary, updateProject } from '../../lib/projects'
import type { ProjectRecord } from '../../lib/projects'
import { projectPath } from '../../lib/route'
import { Button, Dialog, RuledRow } from '../ui'
import RenameField from '../shell/RenameField'

interface ProjectRowProps {
  project: ProjectRecord
  /** Re-read the list: this row has renamed or deleted itself. */
  onChanged: () => void
}

const count = (n: number, one: string, many: string) => `${n === 0 ? 'no' : n} ${n === 1 ? one : many}`

export default function ProjectRow({ project, onChanged }: ProjectRowProps) {
  const [renaming, setRenaming] = useState(false)
  const [confirming, setConfirming] = useState(false)

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
    <RuledRow as="li" className="flex-col gap-2 py-4 sm:flex-row sm:items-baseline sm:gap-6">
      <div className="min-w-0 flex-1">
        {renaming ? (
          <RenameField
            name={project.name}
            onSave={(name) => {
              updateProject(project.id, { name })
              setRenaming(false)
              onChanged()
            }}
            onCancel={() => setRenaming(false)}
          />
        ) : (
          <a href={projectPath(project.id)} className="type-title text-ink no-underline hover:underline">
            {project.name}
          </a>
        )}
        <p className="mt-0.5 truncate type-small text-ink-soft">{project.fileNames.join(', ') || 'No files yet'}</p>
      </div>

      <div className="shrink-0 sm:w-44 sm:text-right">
        <p className="type-small text-ink">{projectSummary(project)}</p>
        <p className="type-small text-ink-soft">{lastOpened(project.lastOpenedAt)}</p>
      </div>

      <div className="flex shrink-0 gap-1">
        <Button variant="quiet" size="sm" aria-label={`Rename ${project.name}`} onClick={() => setRenaming(true)}>
          Rename
        </Button>
        <Button variant="quiet" size="sm" aria-label={`Delete ${project.name}`} onClick={() => setConfirming(true)}>
          Delete
        </Button>
      </div>

      <Dialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Delete this project?"
        size="sm"
        footer={
          <>
            <Button variant="quiet" onClick={() => setConfirming(false)}>
              Keep it
            </Button>
            <Button variant="primary" onClick={remove}>
              Delete the project
            </Button>
          </>
        }
      >
        <p>
          <span className="font-medium">{project.name}</span> will be removed from this browser, with{' '}
          {count(project.turns.length, 'question', 'questions')} and {count(project.savedAnswerIds.length, 'saved answer', 'saved answers')}.
          The files on your own computer are not touched.
        </p>
        {project.sessionId && <p className="mt-2 text-ink-soft">The copy on our server, loaded for answering, is dropped now rather than in two hours.</p>}
      </Dialog>
    </RuledRow>
  )
}
