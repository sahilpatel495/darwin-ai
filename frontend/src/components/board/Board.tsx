// Saved (§8): a report the analyst can put in front of their CHRO. It holds both kinds of saved
// thing — an answer from the conversation and a tile computed on Overview or Analyses — and on
// screen each one has the three controls a report needs: order, remove, print. On paper it has
// none of them: the print stylesheet drops every button, so what is left is the project's name,
// the date, and the cards in the order they were put in.
//
// ponytail: one order per kind, so a tile cannot be moved above an answer. A single mixed order
// needs an items list on the record; two short lists is what the storage contract has today.

import { go, projectPath } from '../../lib/route'
import type { Turn } from '../../lib/projects'
import AnswerStatement from '../answer/AnswerStatement'
import TileCard from '../tiles/TileCard'
import { Button, ChevronIcon, CloseIcon, EmptyState, IconButton } from '../ui'
import type { PageProps } from '../shell/page'
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
      <IconButton label={`Remove from the report: ${what}`} size="sm" variant="ghost" onClick={onRemove}>
        <CloseIcon size={16} />
      </IconButton>
    </div>
  )
}

export default function Board({ project, onProjectChange }: PageProps) {
  // A saved answer whose turn has since been trimmed away (60 turns, §10) can no longer be shown.
  const answers = project.savedAnswerIds
    .map((id) => project.turns.find((turn) => turn.answer.id === id))
    .filter((turn): turn is Turn => turn !== undefined)
  const tiles = project.savedTiles

  /** Reordering also drops any saved id that has no turn left, so the list heals as it is used. */
  const moveAnswer = (answerId: string, by: number) => {
    const ids = answers.map((turn) => turn.answer.id)
    onProjectChange({ ...project, savedAnswerIds: reorder(ids, ids.indexOf(answerId), by) })
  }
  const removeAnswer = (answerId: string) =>
    onProjectChange({ ...project, savedAnswerIds: project.savedAnswerIds.filter((id) => id !== answerId) })

  const moveTile = (tileId: string, by: number) =>
    onProjectChange({ ...project, savedTiles: reorder(tiles, tiles.findIndex((tile) => tile.id === tileId), by) })
  const removeTile = (tileId: string) => onProjectChange({ ...project, savedTiles: tiles.filter((tile) => tile.id !== tileId) })

  const total = answers.length + tiles.length
  // "Saved answers", "Saved tiles", or both: the subtitle says what is actually on the page.
  const kinds = answers.length > 0 ? (tiles.length > 0 ? 'Answers and tiles' : 'Answers') : 'Tiles'
  const headed = answers.length > 0 && tiles.length > 0
  const today = new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })

  return (
    <main className="mx-auto w-full max-w-[820px] px-4 py-10 sm:px-6 sm:py-12">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-hairline-soft pb-6">
        <div className="min-w-0">
          <h1 className="text-heading-lg text-ink-deep">{project.name}</h1>
          <p className="mt-2 text-body-md text-slate">{total === 0 ? `Nothing saved yet · ${today}` : `${kinds} you saved · ${today}`}</p>
        </div>
        {total > 0 && (
          <Button variant="primary" onClick={() => window.print()} className="print-hide">
            Print or save as PDF
          </Button>
        )}
      </header>

      {total === 0 ? (
        <EmptyState
          glyph="receipt"
          className="mt-10"
          action={
            <Button variant="primary" onClick={() => go(projectPath(project.id))}>
              Ask a question
            </Button>
          }
        >
          Save an answer, or a tile from the overview, to build a report you can hand over.
        </EmptyState>
      ) : (
        <div className="mt-10 space-y-12">
          {answers.length > 0 && (
            <section>
              {headed && <h2 className="mb-5 text-subtitle-lg text-ink-deep">Answers</h2>}
              <ol className="space-y-12">
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
              {headed && <h2 className="mb-5 text-subtitle-lg text-ink-deep">From the overview and analyses</h2>}
              <ol className="space-y-12">
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
    </main>
  )
}
