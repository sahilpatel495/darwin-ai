// One computed tile (§8): a title, the sentence the server wrote, the visual, the facts it found,
// and — on hover or keyboard focus — what you can do with it. Overview, Analyses and the saved
// board all draw this same card, so a figure looks identical wherever the analyst meets it.
//
// Nothing here is written by a model. Every string comes from a server template over a DuckDB
// result, which is why a tile can be shown while the models are rate limited.

import { useState } from 'react'
import type { SVGProps } from 'react'
import ResultView from '../charts/ResultView'
import { AskIcon, Card, Chip, IconButton, SavedIcon, StatTile, VerifiedList, cx } from '../ui'
import { csvFileName, downloadCsv, toCsv } from '../../lib/csv'
import type { InsightTile } from '../../types'
import { kpiLabel, kpiValue } from './layout'
import Sparkline, { useSpark } from './Sparkline'
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

// Two glyphs the shared set does not have yet, on its own 20px grid. They belong in
// components/ui/icons.tsx the day a second screen needs them.
const Glyph = ({ size = 18, children, ...rest }: SVGProps<SVGSVGElement> & { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden {...rest}>
    {children}
  </svg>
)
const TableIcon = (p: SVGProps<SVGSVGElement>) => (
  <Glyph {...p}>
    <rect x="3" y="3.5" width="14" height="13" rx="1.6" />
    <path d="M3 8h14M8.5 8v8.5" />
  </Glyph>
)
const DownloadIcon = (p: SVGProps<SVGSVGElement>) => (
  <Glyph {...p}>
    <path d="M10 3.5v9M10 12.5 6.5 9M10 12.5 13.5 9" />
    <path d="M3.5 14.5v1a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-1" />
  </Glyph>
)

export default function TileCard({ tile, onAsk, saved = false, onToggleSaved, compact = false }: TileCardProps) {
  const [dataOpen, setDataOpen] = useState(false)
  const spark = useSpark()
  const table = tile.table
  const figure = tile.kind === 'kpi' || tile.chart?.type === 'kpi' ? kpiValue(tile) : null

  return (
    // `group` drives the toolbar; overflow-wrap is inherited, so one declaration here keeps a long
    // figure ("-₹12.34 Cr" at 36px), a long title and a long insight inside a quarter tile on a
    // 390px phone. Without it the whole page scrolls sideways (§12).
    <Card as="article" className="group flex h-full flex-col gap-4 [overflow-wrap:anywhere]">
      <div className="flex items-start gap-3">
        <h3 className="min-w-0 flex-1 text-heading-sm text-ink-deep">{tile.title}</h3>
        {!compact && (
          // Visible on a touch screen, which has no hover; on a pointer device the card is quiet
          // until you go near it. Keyboard focus reveals it too, so it is never hidden from Tab.
          <div
            className={cx(
              'flex shrink-0 items-center gap-0.5 transition-opacity',
              'md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100',
              saved && 'md:opacity-100',
            )}
          >
            {tile.ask && onAsk && (
              <IconButton label="Ask about this" variant="ghost" size="sm" onClick={() => onAsk(tile.ask as string)}>
                <AskIcon size={18} />
              </IconButton>
            )}
            {onToggleSaved && (
              <IconButton
                label={saved ? 'Remove from the board' : 'Save to the board'}
                variant={saved ? 'soft' : 'ghost'}
                size="sm"
                aria-pressed={saved}
                onClick={onToggleSaved}
              >
                <SavedIcon size={18} className={saved ? 'fill-current' : undefined} />
              </IconButton>
            )}
            {table && (
              <>
                <IconButton label="Table and SQL" variant="ghost" size="sm" onClick={() => setDataOpen(true)}>
                  <TableIcon />
                </IconButton>
                <IconButton
                  label="Download CSV"
                  variant="ghost"
                  size="sm"
                  onClick={() => downloadCsv(csvFileName(tile.title), toCsv(table.columns, table.rows))}
                >
                  <DownloadIcon />
                </IconButton>
              </>
            )}
          </div>
        )}
      </div>

      {figure !== null ? (
        // The figure is the tile, so it leads and the sentence explains it underneath. The
        // sparkline is the section's trend, and says so under itself.
        <StatTile value={figure} label={kpiLabel(tile, figure)} aside={spark && <Sparkline {...spark} />} animate />
      ) : (
        <>
          <p className="measure text-body-md text-slate">{tile.statement}</p>
          {tile.kind === 'quality' ? (
            // The quality tile is a checklist: one checked sentence per thing that was done to
            // the data, which is the whole point of the tile.
            <VerifiedList items={tile.insights} />
          ) : (
            // Without `allowSwitch` this is the chart alone — no type switch, no download, no
            // expand. A dashboard is for scanning; the table and the query live in the toolbar.
            // A tile with no chart spec is not a dead end: ResultView draws its table instead.
            <ResultView chart={tile.chart} table={table} />
          )}
        </>
      )}

      {/* The quality tile has already read its insights out as the checklist above. */}
      {tile.kind !== 'quality' && tile.insights.length > 0 && (
        <ul className="mt-auto flex flex-wrap gap-2 pt-1">
          {tile.insights.map((insight) => (
            <li key={insight}>
              <Chip static>{insight}</Chip>
            </li>
          ))}
        </ul>
      )}

      {tile.caveats.length > 0 && (
        <div className="rounded-xl border-l-[3px] border-attention bg-attention-soft px-4 py-3">
          <p className="text-body-sm font-bold text-ink-deep">Keep in mind</p>
          <ul className="mt-1 space-y-1">
            {tile.caveats.map((caveat) => (
              <li key={caveat} className="text-body-sm text-ink">
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
