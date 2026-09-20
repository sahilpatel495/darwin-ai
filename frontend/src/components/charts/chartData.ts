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
// Column names are returned as they are ("total_gross"); the component makes them readable with
// lib/format humanize. Series names of a grouped bar are data values and are shown untouched.
//
// No runtime imports on purpose: the tests load this file directly with `node --test`.

import type { Cell, ChartSpec, ResultTable } from '../../types'

const MAX_GROUPS = 12 // bars stay readable on a phone; the backend adds a note when it trims
const MAX_SERIES = 5 // one per --color-series-* token; colours are never recycled
const MAX_SCATTER_POINTS = 500 // ponytail: SVG dots get slow past this; sample server-side if it matters

export interface Point {
  x: string
  values: (number | null)[]
}

export interface ScatterPoint {
  x: number
  y: number
  label: string
  xDisplay: string
  yDisplay: string
}

export type ChartData =
  | { kind: 'kpi'; value: string; supporting: { label: string; value: string }[] }
  | { kind: 'bar' | 'line' | 'grouped_bar'; points: Point[]; series: string[] }
  | { kind: 'scatter'; points: ScatterPoint[]; xLabel: string; yLabel: string }
  | { kind: 'table'; reason: string | null }

const NOT_DRAWABLE = 'This result does not fit a chart cleanly, so it is shown as a table.'
// The backend's own sentence for the same decision, so the analyst reads one wording.
const TOO_MANY_GROUPS = 'There are too many groups to chart clearly, so this is shown as a table.'

const fallback = (reason: string | null = NOT_DRAWABLE): ChartData => ({ kind: 'table', reason })
const numberOrNull = (cell: Cell | undefined): number | null => (typeof cell === 'number' && Number.isFinite(cell) ? cell : null)
const hasNumber = (points: Point[]): boolean => points.some((p) => p.values.some((v) => v !== null))

export function buildChartData(chart: ChartSpec, table: ResultTable): ChartData {
  if (chart.type === 'table') return fallback(null)
  if (table.rows.length === 0) return fallback(null) // the table itself says "no rows"; no second excuse needed
  const col = (name: string | null): number => (name === null ? -1 : table.columns.indexOf(name))
  const display = (row: number, column: number): string => table.display[row]?.[column] ?? String(table.rows[row][column] ?? '')

  if (chart.type === 'kpi') {
    // A single-cell result needs no column name. With several columns we only headline the one
    // the spec names, and with several rows none at all: guessing could put the wrong number in
    // large type.
    const valueCol = chart.y.length > 0 ? col(chart.y[0]) : table.columns.length === 1 ? 0 : -1
    if (valueCol < 0 || table.rows.length !== 1) return fallback()
    const supporting = table.columns.map((name, c) => ({ label: name, value: display(0, c) })).filter((_, c) => c !== valueCol)
    return { kind: 'kpi', value: display(0, valueCol), supporting }
  }

  const yCols = chart.y.map(col)
  if (yCols.length === 0 || yCols.includes(-1)) return fallback()

  if (chart.type === 'scatter') {
    // presentation.py puts the first measure in x and the second in y.
    const xCol = col(chart.x)
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

  const xCol = col(chart.x)
  if (xCol < 0) return fallback()

  if (chart.type === 'grouped_bar') {
    const sCol = col(chart.series)
    if (sCol < 0) return fallback()
    const series: string[] = []
    const byX = new Map<string, Point>()
    table.rows.forEach((row, r) => {
      const name = display(r, sCol)
      let s = series.indexOf(name)
      if (s < 0) s = series.push(name) - 1
      const x = display(r, xCol)
      const point = byX.get(x) ?? { x, values: [] }
      point.values[s] = numberOrNull(row[yCols[0]])
      byX.set(x, point)
    })
    // Unlike a bar, a grouped bar has no note to say what was left out, so it is never trimmed.
    if (series.length > MAX_SERIES || byX.size > MAX_GROUPS) return fallback(TOO_MANY_GROUPS)
    // Fill the gaps so every point has one slot per series (a missing combination stays empty).
    const points = [...byX.values()].map((p) => ({ x: p.x, values: series.map((_, s) => p.values[s] ?? null) }))
    return hasNumber(points) ? { kind: 'grouped_bar', points, series } : fallback()
  }

  // bar and line: one point per row, one series per measured column.
  if (yCols.length > MAX_SERIES) return fallback(TOO_MANY_GROUPS)
  const rows = chart.type === 'bar' ? table.rows.slice(0, MAX_GROUPS) : table.rows
  const points = rows.map((row, r) => ({ x: display(r, xCol), values: yCols.map((c) => numberOrNull(row[c])) }))
  return hasNumber(points) ? { kind: chart.type, points, series: yCols.map((c) => table.columns[c]) } : fallback()
}
