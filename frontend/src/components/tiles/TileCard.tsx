// One computed tile (§13): a title, the sentence the server wrote, the visual, the facts it
// found, and a menu of what you can do with it. Overview, Analyses and the saved board all draw
// this same card, so a figure looks identical wherever the analyst meets it.
//
// Nothing here is written by a model. Every string comes from a server template over a DuckDB
// result, which is why a tile can be shown while the models are rate limited.

import { useState } from 'react'
import ResultView from '../charts/ResultView'
import { Card, Chip, Menu, MoreIcon, StatTile, VerifiedList } from '../ui'
import type { MenuAction } from '../ui'
import { csvFileName, downloadCsv, toCsv } from '../../lib/csv'
import type { InsightTile } from '../../types'
import { kpiLabel, kpiValue } from './layout'
import TileDataDialog from './TileDataDialog'

export interface TileCardProps {
  tile: InsightTile
  /** Sends `tile.ask` to the Ask page. Without it the tile simply has no "Ask about this". */
  onAsk?: (question: string) => void
  saved?: boolean
  onToggleSaved?: () => void
  /** The card sits somewhere that supplies its own controls — the board, an analysis result. */
  compact?: boolean
}

export default function TileCard({ tile, onAsk, saved = false, onToggleSaved, compact = false }: TileCardProps) {
  const [dataOpen, setDataOpen] = useState(false)
  const table = tile.table

  const actions: MenuAction[] = []
  const ask = tile.ask
  if (ask && onAsk) actions.push({ id: 'ask', label: 'Ask about this', onSelect: () => onAsk(ask) })
  if (onToggleSaved) actions.push({ id: 'save', label: saved ? 'Remove from board' : 'Save to board', onSelect: onToggleSaved })
  if (table) {
    actions.push({ id: 'data', label: 'View table and SQL', onSelect: () => setDataOpen(true) })
    actions.push({
      id: 'csv',
      label: 'Download CSV',
      onSelect: () => downloadCsv(csvFileName(tile.title), toCsv(table.columns, table.rows)),
    })
  }

  const figure = tile.kind === 'kpi' || tile.chart?.type === 'kpi' ? kpiValue(tile) : null

  return (
    // overflow-wrap is inherited, so one declaration here keeps a long figure ("-₹12.34 Cr" at
    // 40px), a long title and a long insight inside a 171px tile on a 390px phone. Without it the
    // whole page scrolls sideways (§9).
    <Card as="article" className="flex h-full flex-col gap-3 [overflow-wrap:anywhere]">
      <div className="flex items-start gap-2">
        <h3 className="min-w-0 flex-1 type-section text-ink">{tile.title}</h3>
        {saved && !compact && <span className="shrink-0 type-micro text-blue-ink">Saved</span>}
        {!compact && actions.length > 0 && (
          <Menu
            trigger={<MoreIcon size={18} />}
            triggerLabel={`Actions for ${tile.title}`}
            actions={actions}
            className="press -mt-0.5 -mr-1 inline-flex size-7 shrink-0 items-center justify-center rounded-pill text-ink-2 hover:bg-fill hover:text-ink"
          />
        )}
      </div>

      {figure !== null ? (
        // The figure is the tile, so it leads and the sentence explains it underneath.
        <StatTile value={figure} label={kpiLabel(tile, figure)} animate />
      ) : (
        <>
          <p className="measure type-small text-ink-2">{tile.statement}</p>
          {tile.kind === 'quality' ? (
            <VerifiedList items={tile.insights} />
          ) : (
            // Without `allowSwitch` this is the chart alone — no type switch, no download, no
            // expand. A dashboard is for scanning; the table and the query live in the menu.
            // A tile with no chart spec is not a dead end: ResultView draws its table instead.
            <ResultView chart={tile.chart} table={table} />
          )}
        </>
      )}

      {/* The quality tile has already read its insights out as the checklist above. */}
      {tile.kind !== 'quality' && tile.insights.length > 0 && (
        <ul className="mt-auto flex flex-wrap gap-1.5 pt-1">
          {tile.insights.map((insight) => (
            <li key={insight}>
              <Chip static>{insight}</Chip>
            </li>
          ))}
        </ul>
      )}

      {tile.caveats.length > 0 && (
        <div className="rounded-card border-l-[3px] border-amber bg-amber-soft px-3 py-2">
          <p className="type-small font-semibold text-ink">Keep in mind</p>
          <ul className="mt-1 space-y-1">
            {tile.caveats.map((caveat) => (
              <li key={caveat} className="type-small text-ink">
                {caveat}
              </li>
            ))}
          </ul>
        </div>
      )}

      {dataOpen && <TileDataDialog tile={tile} open={dataOpen} onClose={() => setDataOpen(false)} />}
    </Card>
  )
}
