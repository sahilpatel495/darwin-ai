// The saved-answers board (§6.5): a report the analyst can put in front of their CHRO. On screen
// it has the three controls a report needs — order, remove, print. On paper it has none of them:
// the print stylesheet drops every button, so what is left is the project's name, the date, and
// the statements in the order they were put in.

import { useProject } from '../../lib/projects'
import type { Turn } from '../../lib/projects'
import { projectPath } from '../../lib/route'
import AnswerStatement from '../answer/AnswerStatement'
import { Button, EmptyState } from '../ui'
import Header from '../shell/Header'
import MissingProject from '../shell/MissingProject'

export default function Board({ projectId }: { projectId: string }) {
  const [project, update] = useProject(projectId)
  if (!project) return <MissingProject />

  // A saved answer whose turn has since been trimmed away (60 turns, §7) can no longer be shown.
  const saved = project.savedAnswerIds
    .map((id) => project.turns.find((turn) => turn.answer.id === id))
    .filter((turn): turn is Turn => turn !== undefined)

  /** Reordering also drops any saved id that has no turn left, so the list heals as it is used. */
  function move(answerId: string, by: number) {
    const ids = saved.map((turn) => turn.answer.id)
    const from = ids.indexOf(answerId)
    const to = from + by
    if (from < 0 || to < 0 || to >= ids.length) return
    ;[ids[from], ids[to]] = [ids[to], ids[from]]
    update({ savedAnswerIds: ids })
  }

  const remove = (answerId: string) => update({ savedAnswerIds: project.savedAnswerIds.filter((id) => id !== answerId) })

  return (
    <div className="flex h-full flex-col">
      <Header project={{ id: project.id, name: project.name, savedCount: saved.length }} onRename={(name) => update({ name })} />

      <main className="relative min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3 print-hide">
            <a href={projectPath(project.id)}>Back to your questions</a>
            {saved.length > 0 && (
              <Button variant="primary" onClick={() => window.print()}>
                Print or save as PDF
              </Button>
            )}
          </div>

          <header className="mt-6 border-b border-rule-strong pb-4">
            <h1 className="type-headline text-ink">{project.name}</h1>
            <p className="mt-1 type-small text-ink-soft">
              Saved answers, {new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}
            </p>
          </header>

          {saved.length === 0 ? (
            <EmptyState
              className="mt-0 border-t-0"
              action={
                <a href={projectPath(project.id)} className="type-body">
                  Ask a question
                </a>
              }
            >
              Save an answer to build a report you can print.
            </EmptyState>
          ) : (
            <ol className="mt-8 space-y-10">
              {saved.map((turn, index) => (
                <li key={turn.answer.id} className="print-keep">
                  <div className="mb-2 flex flex-wrap items-center gap-1 print-hide">
                    <Button
                      variant="quiet"
                      size="sm"
                      disabled={index === 0}
                      aria-label={`Move up: ${turn.question}`}
                      onClick={() => move(turn.answer.id, -1)}
                    >
                      Move up
                    </Button>
                    <Button
                      variant="quiet"
                      size="sm"
                      disabled={index === saved.length - 1}
                      aria-label={`Move down: ${turn.question}`}
                      onClick={() => move(turn.answer.id, 1)}
                    >
                      Move down
                    </Button>
                    <Button variant="quiet" size="sm" aria-label={`Remove from the board: ${turn.question}`} onClick={() => remove(turn.answer.id)}>
                      Remove
                    </Button>
                  </div>
                  <AnswerStatement answer={turn.answer} mode="board" />
                </li>
              ))}
            </ol>
          )}
        </div>
      </main>
    </div>
  )
}
