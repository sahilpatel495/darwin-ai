// Turns the backend's chart spec + result table into the exact arrays a chart draws.
//
// Why a separate pure module: the spec is data chosen by backend rules, and the table comes from
// a customer's file. If the two ever disagree (a column that is not in the result, text where a
// number should be, more groups than we have colours) the safe answer is the plain table, never
// a half-drawn chart next to a number someone will quote. Every such case returns kind "table".
//
// Series values are addressed by position (values[i]), not by name, so a department called
// "Sr. Manager" or "__proto__" cannot collide with a key or be read as a path by Recharts.
//
// Numbers stay raw here; the component formats them with lib/format, which follows the backend's
// own rules. Column names are returned as they are ("total_gross") and made readable by humanize;
// series names are data values and are shown untouched.
//
// No runtime imports on purpose: the tests load this file directly with `node --test`.

import type { Cell, ChartSpec, ResultTable } from '../../types'

const MAX_GROUPS = 12 // bars stay readable on a phone; the backend adds a note when it trims
const MAX_SERIES = 5 // one per --color-series-* token; colours are never recycled
const MAX_BANDS = 40 // a histogram is never trimmed: a distribution missing its tail is a lie
const MAX_CELLS = 12 // heatmap rows and columns; past this a cell is a sliver
const MAX_SCATTER_POINTS = 500 // ponytail: SVG dots get slow past this; sample server-side if it matters
const DONUT_SLICES = 6 // §12: at most six, the rest as "Other"
const LONG_LABEL = 10 // §12: bars go horizontal when any label is longer than this

export interface Point {
  x: string
  values: (number | null)[]
}

export interface Slice {
  name: string
  value: number
}

export interface ScatterPoint {
  x: number
  y: number
  label: string
  xDisplay: string
  yDisplay: string
}

/** The shapes that are one point per x with one value per series. */
export type SeriesKind = 'bar' | 'line' | 'area' | 'grouped_bar' | 'stacked_bar' | 'histogram'

export type ChartData =
  | { kind: 'kpi'; value: string; supporting: { label: string; value: string }[] }
  /** `omitted`: rows past the first 12 of a long breakdown. The chart says so; the table has them all. */
  | { kind: SeriesKind; points: Point[]; series: string[]; omitted: number; horizontal: boolean }
  | { kind: 'donut'; slices: Slice[]; total: number; otherCount: number }
  /** `cells[row][col]`, null where that combination has no row. `max` scales the colour. */
  | { kind: 'heatmap'; cols: string[]; rows: string[]; cells: (number | null)[][]; max: number }
  | { kind: 'scatter'; points: ScatterPoint[]; xLabel: string; yLabel: string }
  | { kind: 'table'; reason: string | null }

const NOT_DRAWABLE = 'This result does not fit a chart cleanly, so it is shown as a table.'
// The backend's own sentence for the same decision, so the analyst reads one wording.
const TOO_MANY_GROUPS = 'There are too many groups to chart clearly, so this is shown as a table.'

const fallback = (reason: string | null = NOT_DRAWABLE): ChartData => ({ kind: 'table', reason })
const numberOrNull = (cell: Cell | undefined): number | null => (typeof cell === 'number' && Number.isFinite(cell) ? cell : null)
const hasNumber = (points: Point[]): boolean => points.some((p) => p.values.some((v) => v !== null))
/** Long names ("Customer Success", "2025-01-01") do not fit under vertical bars on a phone. */
const isLong = (points: Point[]): boolean => points.some((p) => p.x.length > LONG_LABEL)

/** One row per x value, one column per value of the series column. Shared by grouped, stacked
 *  and heatmap: they differ only in how they draw the same pivot. */
function pivot(rows: Cell[][], xCol: number, sCol: number, yCol: number, display: (row: number, column: number) => string) {
  const series: string[] = []
  const byX = new Map<string, Point>()
  rows.forEach((row, r) => {
    const name = display(r, sCol)
    let s = series.indexOf(name)
    if (s < 0) s = series.push(name) - 1
    const x = display(r, xCol)
    const point = byX.get(x) ?? { x, values: [] }
    point.values[s] = numberOrNull(row[yCol])
    byX.set(x, point)
  })
  // Fill the gaps so every point has one slot per series (a missing combination stays empty).
  const points = [...byX.values()].map((p) => ({ x: p.x, values: series.map((_, s) => p.values[s] ?? null) }))
  return { series, points }
}

export function buildChartData(spec: ChartSpec, table: ResultTable): ChartData {
  if (spec.type === 'table') return fallback(null)
  if (table.rows.length === 0) return fallback(null) // the table itself says "no rows"; no second excuse needed
  const col = (name: string | null): number => (name === null ? -1 : table.columns.indexOf(name))
  const display = (row: number, column: number): string => table.display[row]?.[column] ?? String(table.rows[row][column] ?? '')

  if (spec.type === 'kpi') {
    // A single-cell result needs no column name. With several columns we only headline the one
    // the spec names, and with several rows none at all: guessing could put the wrong number in
    // large type.
    const valueCol = spec.y.length > 0 ? col(spec.y[0]) : table.columns.length === 1 ? 0 : -1
    if (valueCol < 0 || table.rows.length !== 1) return fallback()
    const supporting = table.columns.map((name, c) => ({ label: name, value: display(0, c) })).filter((_, c) => c !== valueCol)
    return { kind: 'kpi', value: display(0, valueCol), supporting }
  }

  const yCols = spec.y.map(col)
  if (yCols.length === 0 || yCols.includes(-1)) return fallback()

  if (spec.type === 'scatter') {
    // presentation.py puts the first measure in x and the second in y.
    const xCol = col(spec.x)
    const yCol = yCols[0]
    if (xCol < 0) return fallback()
    const labelCol = table.columns.findIndex((_, c) => c !== xCol && c !== yCol)
    const points = table.rows.slice(0, MAX_SCATTER_POINTS).flatMap((row, r): ScatterPoint[] => {
      const x = numberOrNull(row[xCol])
      const y = numberOrNull(row[yCol])
      if (x === null || y === null) return [] // a dot needs both numbers; the table still shows the row
      return [{ x, y, label: labelCol < 0 ? '' : display(r, labelCol), xDisplay: display(r, xCol), yDisplay: display(r, yCol) }]
    })
    if (points.length === 0) return fallback()
    return { kind: 'scatter', points, xLabel: table.columns[xCol], yLabel: table.columns[yCol] }
  }

  const xCol = col(spec.x)
  if (xCol < 0) return fallback()

  if (spec.type === 'donut') {
    // A share of a whole. Negative values have no share, so such a result stays a table.
    const slices = table.rows
      .map((row, r): Slice => ({ name: display(r, xCol), value: numberOrNull(row[yCols[0]]) ?? 0 }))
      .filter((slice) => slice.value > 0)
      .sort((a, b) => b.value - a.value)
    if (slices.length < 2 || table.rows.some((row) => (numberOrNull(row[yCols[0]]) ?? 0) < 0)) return fallback()
    const total = slices.reduce((sum, slice) => sum + slice.value, 0)
    const tail = slices.slice(DONUT_SLICES)
    const kept = slices.slice(0, DONUT_SLICES)
    if (tail.length > 0) kept.push({ name: 'Other', value: tail.reduce((sum, slice) => sum + slice.value, 0) })
    return { kind: 'donut', slices: kept, total, otherCount: tail.length }
  }

  if (spec.type === 'heatmap') {
    const sCol = col(spec.series)
    if (sCol < 0) return fallback()
    const { series, points } = pivot(table.rows, xCol, sCol, yCols[0], display)
    if (series.length > MAX_CELLS || points.length > MAX_CELLS) return fallback(TOO_MANY_GROUPS)
    const cells = series.map((_, s) => points.map((p) => p.values[s]))
    const max = Math.max(...cells.flat().map((v) => Math.abs(v ?? 0)))
    if (!Number.isFinite(max) || max === 0) return fallback()
    return { kind: 'heatmap', cols: points.map((p) => p.x), rows: series, cells, max }
  }

  if (spec.type === 'grouped_bar' || spec.type === 'stacked_bar') {
    const sCol = col(spec.series)
    if (sCol < 0) return fallback()
    const { series, points } = pivot(table.rows, xCol, sCol, yCols[0], display)
    // Unlike a bar, these have no note to say what was left out, so they are never trimmed.
    if (series.length > MAX_SERIES || points.length > MAX_GROUPS) return fallback(TOO_MANY_GROUPS)
    // A stack of negative and positive values reads as neither, so it stays a grouped bar's job.
    if (spec.type === 'stacked_bar' && points.some((p) => p.values.some((v) => v !== null && v < 0))) return fallback()
    return hasNumber(points) ? { kind: spec.type, points, series, omitted: 0, horizontal: isLong(points) } : fallback()
  }

  // bar, line, area and histogram: one point per row, one series per measured column.
  if (yCols.length > MAX_SERIES) return fallback(TOO_MANY_GROUPS)
  if (spec.type === 'histogram' && table.rows.length > MAX_BANDS) return fallback(TOO_MANY_GROUPS)
  const rows = spec.type === 'bar' ? table.rows.slice(0, MAX_GROUPS) : table.rows
  const points = rows.map((row, r) => ({ x: display(r, xCol), values: yCols.map((c) => numberOrNull(row[c])) }))
  if (!hasNumber(points)) return fallback()
  const omitted = table.rows.length - rows.length
  // Only a bar turns: a trend and a distribution are read left to right along their own axis.
  const horizontal = spec.type === 'bar' && isLong(points)
  return { kind: spec.type, points, series: yCols.map((c) => table.columns[c]), omitted, horizontal }
}

// --- Which chart types fit this result (§12) --------------------------------
// The backend has already read the shape of the result to choose a type; its choice tells us
// which family the result is in, and the family says what else would read the same data.

type Family = ChartSpec['type'][]
const CATEGORY: Family = ['bar', 'donut', 'table']
const DISTRIBUTION: Family = ['histogram', 'bar', 'table']
const OVER_TIME: Family = ['line', 'area', 'bar', 'table']
const TWO_CATEGORIES: Family = ['grouped_bar', 'stacked_bar', 'heatmap', 'table']
const TWO_MEASURES: Family = ['scatter', 'table']

const FAMILY: Record<ChartSpec['type'], Family> = {
  bar: CATEGORY,
  donut: CATEGORY,
  histogram: DISTRIBUTION,
  line: OVER_TIME,
  area: OVER_TIME,
  grouped_bar: TWO_CATEGORIES,
  stacked_bar: TWO_CATEGORIES,
  heatmap: TWO_CATEGORIES,
  scatter: TWO_MEASURES,
  kpi: [],
  table: [],
}

/**
 * The chart types the analyst may switch to for this result, in a fixed order so the control
 * does not rearrange itself between answers. "table" is always last and always offered.
 *
 * A type is offered only when it actually builds, which is the real test of whether it fits:
 * a donut of six departments is honest, a donut of six months is not, and the builder above
 * already knows the difference.
 * ponytail: builds the data once per candidate (at most four). Memoise if a 5,000-row result
 * ever makes that noticeable.
 */
export function fitTypes(spec: ChartSpec, table: ResultTable): ChartSpec['type'][] {
  return FAMILY[spec.type].filter(
    // The server's own choice is never removed — it read the query, not just the column names.
    (type) => type === 'table' || ((type !== 'donut' || type === spec.type || addsUp(spec)) && buildChartData({ ...spec, type }, table).kind !== 'table'),
  )
}

/** An average, a median, a rate or a percentage is not a part of a whole: the slices of such a
 *  donut would add up to a number that means nothing, and the total in its middle would be a
 *  figure no one could quote. Judged on the measure's own name, which is how the server writes
 *  it ("avg_salary", "attrition_rate"), plus the format for the percentages. */
const NOT_A_PART = /(^|[_ ])(avg|average|mean|median|rate|ratio|pct|percent|share|per_[a-z]+)([_ ]|$)/i
const addsUp = (spec: ChartSpec): boolean => spec.value_format !== 'percent' && !spec.y.some((name) => NOT_A_PART.test(name))
