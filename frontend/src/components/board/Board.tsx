// The board (§6.5, §15): a report the analyst can put in front of their CHRO. It holds both kinds
// of saved thing — an answer from the conversation and a tile computed on Overview or Analyses —
// and on screen each one has the three controls a report needs: order, remove, print. On paper it
// has none of them: the print stylesheet drops every button, so what is left is the project's
// name, the date, and the cards in the order they were put in.
//
// ponytail: one order per kind, so a tile cannot be moved above an answer. A single mixed order
// needs an items list on the record; two short lists is what the storage contract has today.

import { useProject } from '../../lib/projects'
import type { Turn } from '../../lib/projects'
import { projectPath } from '../../lib/route'
import AnswerStatement from '../answer/AnswerStatement'
import TileCard from '../tiles/TileCard'
import { Button, ChevronIcon, CloseIcon, EmptyState, IconButton } from '../ui'
import Header from '../shell/Header'
import MissingProject from '../shell/MissingProject'
import { reorder } from './order'

/** Order and remove, for one card. Icon buttons: three words in a row would out-shout the report. */
function Controls({ what, first, last, onMove, onRemove }: { what: string; first: boolean; last: boolean; onMove: (by: number) => void; onRemove: () => void }) {
  return (
    <div className="mb-2 flex items-center justify-end gap-1 print-hide">
      <IconButton label={`Move up: ${what}`} size="sm" variant="ghost" disabled={first} onClick={() => onMove(-1)}>
        <ChevronIcon size={16} className="-rotate-90" />
      </IconButton>
      <IconButton label={`Move down: ${what}`} size="sm" variant="ghost" disabled={last} onClick={() => onMove(1)}>
        <ChevronIcon size={16} className="rotate-90" />
      </IconButton>
      <IconButton label={`Remove from the board: ${what}`} size="sm" variant="ghost" onClick={onRemove}>
        <CloseIcon size={16} />
      </IconButton>
    </div>
  )
}

export default function Board({ projectId }: { projectId: string }) {
  const [project, update] = useProject(projectId)
  if (!project) return <MissingProject />

  // A saved answer whose turn has since been trimmed away (60 turns, §7) can no longer be shown.
  const answers = project.savedAnswerIds
    .map((id) => project.turns.find((turn) => turn.answer.id === id))
    .filter((turn): turn is Turn => turn !== undefined)
  const tiles = project.savedTiles

  /** Reordering also drops any saved id that has no turn left, so the list heals as it is used. */
  const moveAnswer = (answerId: string, by: number) => {
    const ids = answers.map((turn) => turn.answer.id)
    update({ savedAnswerIds: reorder(ids, ids.indexOf(answerId), by) })
  }
  const removeAnswer = (answerId: string) => update({ savedAnswerIds: project.savedAnswerIds.filter((id) => id !== answerId) })

  const moveTile = (tileId: string, by: number) =>
    update({ savedTiles: reorder(tiles, tiles.findIndex((tile) => tile.id === tileId), by) })
  const removeTile = (tileId: string) => update({ savedTiles: tiles.filter((tile) => tile.id !== tileId) })

  const total = answers.length + tiles.length
  // "Saved answers", "Saved tiles", or both: the subtitle says what is actually on the page.
  const kinds = answers.length > 0 ? (tiles.length > 0 ? 'Saved answers and tiles' : 'Saved answers') : 'Saved tiles'
  const headed = answers.length > 0 && tiles.length > 0

  return (
    <div className="flex h-full flex-col">
      <Header project={{ id: project.id, name: project.name }} onRename={(name) => update({ name })} />

      <main className="relative min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3 print-hide">
            <a href={projectPath(project.id)} className="type-small">
              Back to your questions
            </a>
            {total > 0 && (
              <Button variant="primary" onClick={() => window.print()}>
                Print or save as PDF
              </Button>
            )}
          </div>

          <header className="mt-6 border-b border-line pb-4">
            <h1 className="type-page text-ink">{project.name}</h1>
            <p className="mt-1 type-small text-ink-2">
              {total === 0 ? 'Nothing saved yet' : kinds}, {new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}
            </p>
          </header>

          {total === 0 ? (
            <EmptyState
              className="mt-8"
              action={
                <a href={projectPath(project.id)} className="type-body">
                  Ask a question
                </a>
              }
            >
              Save an answer or a tile from the overview to build a report you can print.
            </EmptyState>
          ) : (
            <div className="mt-8 space-y-10">
              {answers.length > 0 && (
                <section>
                  {headed && <h2 className="type-section text-ink-2">Answers</h2>}
                  <ol className={headed ? 'mt-4 space-y-10' : 'space-y-10'}>
                    {answers.map((turn, index) => (
                      <li key={turn.answer.id} className="print-keep">
                        <Controls
                          what={turn.question}
                          first={index === 0}
                          last={index === answers.length - 1}
                          onMove={(by) => moveAnswer(turn.answer.id, by)}
                          onRemove={() => removeAnswer(turn.answer.id)}
                        />
                        <AnswerStatement answer={turn.answer} mode="board" />
                      </li>
                    ))}
                  </ol>
                </section>
              )}

              {tiles.length > 0 && (
                <section>
                  {headed && <h2 className="type-section text-ink-2">From the overview and analyses</h2>}
                  <ol className={headed ? 'mt-4 space-y-10' : 'space-y-10'}>
                    {tiles.map((tile, index) => (
                      <li key={tile.id} className="print-keep">
                        <Controls
                          what={tile.title}
                          first={index === 0}
                          last={index === tiles.length - 1}
                          onMove={(by) => moveTile(tile.id, by)}
                          onRemove={() => removeTile(tile.id)}
                        />
                        <TileCard tile={tile} compact />
                      </li>
                    ))}
                  </ol>
                </section>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
