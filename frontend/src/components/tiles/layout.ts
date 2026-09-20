// How the automatic dashboard arranges itself (§13), and which figure a KPI tile shows.
//
// Pure and free of React so `node --test` can read it directly: the grid is the one thing on the
// Overview that is easy to get subtly wrong (a heatmap squeezed into half a row is unreadable)
// and easy to test.

import type { InsightTile, TileKind } from '../../types'

/** How much of the four-column grid one tile takes. */
export type TileSpan = 'kpi' | 'half' | 'full'

// A tile whose chart has a `series` has two categories in it — a grouped bar, a stacked bar, a
// heatmap. Those need the whole width or the bars are too thin to compare. The two kinds are the
// belt to that braces: a server template could send one with the second category already folded
// into the columns.
const TWO_WAY: TileKind[] = ['comparison', 'relationship']

/**
 * One number is a quarter of a row, one chart is half, a two-way chart is the whole width.
 * The data quality checklist is full width too: it is a list of sentences, not a chart.
 */
export function tileSpan(tile: Pick<InsightTile, 'kind' | 'chart'>): TileSpan {
  if (tile.kind === 'kpi' || tile.chart?.type === 'kpi') return 'kpi'
  if (tile.kind === 'quality') return 'full'
  if (tile.chart?.series || TWO_WAY.includes(tile.kind)) return 'full'
  return 'half'
}

/**
 * The grid itself: two columns on a phone, four from 1024 up. `items-start` so a tile is as tall
 * as what is in it — a figure stretched to the height of the chart beside it is a card that
 * looks broken, and nothing in a dashboard depends on two cards ending on the same line.
 */
export const TILE_GRID = 'grid grid-cols-2 items-start gap-4 lg:grid-cols-4'

const PACK_ORDER: Record<TileSpan, number> = { kpi: 0, half: 1, full: 2 }

/**
 * The order tiles are laid out in: figures, then charts, then the full-width ones. The server
 * groups a section by meaning, which can leave a single figure beside a chart and three quarters
 * of a row empty. Sorting by width packs the row and gives the section the reading order a
 * dashboard wants anyway — the headline numbers first. Stable, so the server's order survives
 * inside each width.
 */
export function packTiles<T extends Pick<InsightTile, 'kind' | 'chart'>>(tiles: T[]): T[] {
  return [...tiles].sort((a, b) => PACK_ORDER[tileSpan(a)] - PACK_ORDER[tileSpan(b)])
}

/** What each span costs in that grid. Four KPIs, two charts, or one two-way tile per row. */
export const SPAN_CLASS: Record<TileSpan, string> = {
  kpi: 'col-span-1',
  half: 'col-span-2',
  full: 'col-span-2 lg:col-span-4',
}

/**
 * The single figure a KPI tile shows, as the server already formatted it — never re-formatted
 * here, so the tile, the table under it and the CSV all quote the same string.
 * `chart.y[0]` names the column; a tile that somehow lost it falls back to the first column.
 */
const squash = (text: string) => text.toLowerCase().replace(/[^a-z0-9]/g, '')

/**
 * The line under a KPI figure — or nothing, when the server's sentence is the title and the
 * figure again ("Active headcount is 430."). The card already says both, and a number read three
 * times is a card that looks like a bug. A sentence that adds anything ("37 exits against an
 * average headcount of 416.5") is kept whole.
 */
export function kpiLabel(tile: Pick<InsightTile, 'title' | 'statement'>, figure: string): string | undefined {
  return squash(tile.statement) === squash(`${tile.title} is ${figure}`) ? undefined : tile.statement
}

export function kpiValue(tile: Pick<InsightTile, 'chart' | 'table'>): string | null {
  const table = tile.table
  if (!table || table.rows.length === 0) return null
  const named = tile.chart?.y?.[0]
  const column = named ? table.columns.indexOf(named) : 0
  return table.display[0]?.[column < 0 ? 0 : column] ?? null
}
