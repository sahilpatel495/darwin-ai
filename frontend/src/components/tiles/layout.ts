// How the automatic overview arranges itself (§8), and which figure a KPI tile shows.
//
// Pure and free of React so `node --test` can read it directly: the bento is the one thing on the
// Overview that is easy to get subtly wrong (a heatmap squeezed into half a row is unreadable, a
// row that ends three columns short looks like a bug) and easy to test.

import type { InsightTile, TileKind } from '../../types'

/** How much of the four-column grid one tile wants. */
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

/** The bento: one column on a phone, two from 768, four from 1024. */
export const BENTO_GRID = 'grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4'

const COLUMNS = 4
const NATURAL: Record<TileSpan, number> = { kpi: 1, half: 2, full: COLUMNS }
// Figures first, then charts, then the full-width ones: the headline numbers are what a dashboard
// is read for, and grouping by width is also what lets every row come out exactly full.
const ORDER: TileSpan[] = ['kpi', 'half', 'full']

export interface BentoCell<T> {
  tile: T
  /** Columns of the four this tile takes at 1280. */
  cols: number
}

/**
 * The tiles of one section, as rows that each use the whole content width — no dead columns at
 * 1280 (§8). Tiles of one width are laid out together (four figures, two charts, one two-way
 * tile per row) and whatever is left over at the end of a row is shared out among the tiles in
 * it, so a section with a single figure opens on a wide one rather than on a quarter tile beside
 * three empty columns.
 */
export function packBento<T extends Pick<InsightTile, 'kind' | 'chart'>>(tiles: T[]): BentoCell<T>[][] {
  const rows: BentoCell<T>[][] = []
  for (const span of ORDER) {
    const group = tiles.filter((tile) => tileSpan(tile) === span)
    const perRow = COLUMNS / NATURAL[span]
    for (let i = 0; i < group.length; i += perRow) {
      rows.push(widen(group.slice(i, i + perRow).map((tile) => ({ tile, cols: NATURAL[span] }))))
    }
  }
  return rows
}

/** Share the spare columns out from the left, one at a time, until the row is full. */
function widen<T>(row: BentoCell<T>[]): BentoCell<T>[] {
  let spare = COLUMNS - row.reduce((sum, cell) => sum + cell.cols, 0)
  for (let i = 0; spare > 0; i = (i + 1) % row.length, spare--) row[i].cols += 1
  return row
}

/**
 * What each width costs in that grid. Written out in full because Tailwind reads the source:
 * a class built from a variable never reaches the stylesheet.
 */
export const CELL_CLASS: Record<number, string> = {
  1: 'md:col-span-1 lg:col-span-1',
  2: 'md:col-span-2 lg:col-span-2',
  3: 'md:col-span-2 lg:col-span-3',
  4: 'md:col-span-2 lg:col-span-4',
}

/**
 * The section's trend as bare numbers, for the sparkline beside its figures (§8). A figure with
 * the section's own history under it is the fastest true thing a dashboard can say; a sparkline
 * of anything else would be decoration, so this returns null unless the section really holds a
 * trend, and the caller prints the trend's title under the line so it is never a mystery.
 */
export function trendSeries<T extends Pick<InsightTile, 'kind' | 'chart' | 'table' | 'title'>>(
  tiles: T[],
): { points: number[]; label: string } | null {
  const trend = tiles.find((tile) => tile.kind === 'trend' && (tile.table?.rows.length ?? 0) >= 3)
  const table = trend?.table
  if (!trend || !table) return null
  const named = trend.chart?.y?.[0]
  const at = named ? table.columns.indexOf(named) : -1
  // The value column the chart plots; failing that the last one, which is where a template puts
  // the measure when the first column is the month.
  const column = at >= 0 ? at : table.columns.length - 1
  const points = table.rows.map((row) => Number(row[column])).filter((value) => Number.isFinite(value))
  return points.length >= 3 ? { points, label: trend.title } : null
}

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

/**
 * The single figure a KPI tile shows, as the server already formatted it — never re-formatted
 * here, so the tile, the table under it and the CSV all quote the same string.
 * `chart.y[0]` names the column; a tile that somehow lost it falls back to the first column.
 */
export function kpiValue(tile: Pick<InsightTile, 'chart' | 'table'>): string | null {
  const table = tile.table
  if (!table || table.rows.length === 0) return null
  const named = tile.chart?.y?.[0]
  const column = named ? table.columns.indexOf(named) : 0
  return table.display[0]?.[column < 0 ? 0 : column] ?? null
}
