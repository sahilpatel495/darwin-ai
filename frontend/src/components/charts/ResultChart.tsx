// Draws the chart the backend's rules chose. The model never picks or styles a chart: the spec
// is plain data, and chartData.ts has already turned anything that does not fit into a table.
//
// Clarity styling (§12): series colours in token order, no frame around the plot, a hairline
// grid, one tooltip card everywhere, the legend as chips, every number through lib/format so the
// axis, the tooltip and the table under them read the same. The draw happens once, on mount.
import { useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  type LabelProps,
} from 'recharts'
import type { ChartSpec } from '../../types'
import { axisTicks, formatTick, formatValue, humanize } from '../../lib/format'
import type { ChartData, Point, ScatterPoint, SeriesKind } from './chartData'

type Plotted = Exclude<ChartData, { kind: 'table' | 'kpi' }>
type Series = Extract<ChartData, { kind: SeriesKind }>

// Written out in full so Tailwind sees each token in the source and keeps it in the CSS.
// Seven, in the §2 order; the seventh is the grey a donut's "Other" slice takes.
const SERIES_COLORS = [
  'var(--color-series-1)',
  'var(--color-series-2)',
  'var(--color-series-3)',
  'var(--color-series-4)',
  'var(--color-series-5)',
  'var(--color-series-6)',
  'var(--color-series-7)',
]
const OTHER_COLOR = 'var(--color-series-7)'

const TICK = { fill: 'var(--color-ink-2)', fontSize: 12 }
const GRID = 'var(--color-line-soft)'
const AXIS = { stroke: 'var(--color-line)' }
const shorten = (label: string): string => (label.length > 20 ? `${label.slice(0, 19)}…` : label) // full name is in the tooltip and table

/** The largest number the value axis has to show, so every tick on it can share one unit. */
function axisMax(data: Series, stacked = false): number {
  const of = (values: (number | null)[]): number => {
    const sizes = values.map((value) => Math.abs(value ?? 0))
    return stacked ? sizes.reduce((sum, size) => sum + size, 0) : Math.max(0, ...sizes)
  }
  return Math.max(0, ...data.points.map((point) => of(point.values)))
}

/** The chart draws itself once, when the answer arrives (§4) — never again on a re-render, and
 *  never for a reader who asked for less motion. */
function useDrawOnce(): boolean {
  const [draw] = useState(() => typeof matchMedia === 'function' && !matchMedia('(prefers-reduced-motion: reduce)').matches)
  return draw
}

// --- The one tooltip, and the one legend -----------------------------------

interface TipRow {
  name: string
  value: number | null
  color: string
}

function TipCard({ title, rows, format }: { title: string; rows: TipRow[]; format: ChartSpec['value_format'] }) {
  return (
    <div className="rounded-card bg-surface px-3 py-2 type-micro text-ink shadow-3">
      <p className="font-semibold">{title}</p>
      <ul className="mt-1 space-y-0.5">
        {rows.map((row, i) => (
          <li key={i} className="flex items-center gap-2">
            <span aria-hidden className="size-2 shrink-0 rounded-pill" style={{ background: row.color }} />
            <span className="text-ink-2">{row.name}</span>
            <span className="ml-auto pl-3 tnum font-semibold">{formatValue(row.value, format)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Recharts hands the hovered point back as the object we put in `data`, which is our own Point. */
const pointTooltip = (data: Series, format: ChartSpec['value_format']) =>
  function PointTooltip({ active, payload }: { active?: boolean; payload?: readonly { payload?: unknown }[] }) {
    const point = payload?.[0]?.payload as Point | undefined
    if (!active || !point) return null
    const rows = data.series
      .map((_, i) => ({ name: seriesLabel(data, i), value: point.values[i], color: SERIES_COLORS[i] }))
      .filter((row) => row.value !== null)
    return <TipCard title={point.x} rows={rows} format={format} />
  }

/** Identity is never colour alone: the name sits beside its swatch, and the table has it all. */
function Legend({ names, colors }: { names: string[]; colors: string[] }) {
  if (names.length < 2) return null // one series is already named by the title
  return (
    <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-1.5">
      {names.map((name, i) => (
        <li key={i} className="inline-flex items-center gap-1.5 rounded-pill bg-fill px-2.5 py-1 type-micro text-ink-2">
          <span aria-hidden className="size-2 shrink-0 rounded-pill" style={{ background: colors[i] }} />
          {name}
        </li>
      ))}
    </ul>
  )
}

interface Props {
  chart: ChartSpec
  data: Plotted
  /** Taller, for the expanded dialog. Defaults to the shape's own height. */
  height?: number
}

const CHART_NAMES: Record<Plotted['kind'], string> = {
  bar: 'Bar chart',
  grouped_bar: 'Grouped bar chart',
  stacked_bar: 'Stacked bar chart',
  histogram: 'Histogram',
  line: 'Line chart',
  area: 'Area chart',
  donut: 'Donut chart',
  heatmap: 'Heatmap',
  scatter: 'Scatter chart',
}

const countOf = (data: Plotted): number =>
  data.kind === 'donut' ? data.slices.length : data.kind === 'heatmap' ? data.rows.length * data.cols.length : data.points.length

export default function ResultChart({ chart, data, height }: Props) {
  const count = countOf(data)
  const label = `${chart.title}. ${CHART_NAMES[data.kind]} with ${count} ${count === 1 ? 'point' : 'points'}. Switch to the table for exact values.`
  const omitted = 'omitted' in data ? data.omitted : 0
  return (
    <figure className="m-0">
      {/* tnum is set once here and inherited by every <text> the chart draws. */}
      <div role="img" aria-label={label} className="tnum">
        {data.kind === 'scatter' ? (
          <ScatterPlot data={data} height={height} />
        ) : data.kind === 'donut' ? (
          <DonutPlot chart={chart} data={data} height={height} />
        ) : data.kind === 'heatmap' ? (
          <HeatmapPlot chart={chart} data={data} />
        ) : data.kind === 'line' || data.kind === 'area' ? (
          <LinePlot chart={chart} data={data} height={height} />
        ) : (
          <BarPlot chart={chart} data={data} height={height} />
        )}
      </div>
      {omitted > 0 && (
        <p className="mt-3 type-small text-ink-2">
          The first {count} of {count + omitted} rows are drawn. The table has all of them.
        </p>
      )}
      {chart.note && <p className="mt-2 type-small text-ink-2">{chart.note}</p>}
    </figure>
  )
}

/** Series names of a grouped bar are the customer's own values; column names get tidied. */
const seriesLabel = (data: Series, i: number): string =>
  data.kind === 'grouped_bar' || data.kind === 'stacked_bar' ? data.series[i] : humanize(data.series[i])

/** The exact value beside a bar, in the full format so it reads like the table and the answer.
 *  It always sits to the right of the bar's rightmost edge. For a negative bar that edge is the
 *  zero line, where the row is empty; Recharts' own position="right" would put the label at the
 *  bar's left end, on top of the department name. */
export const barEndLabel = (format: ChartSpec['value_format']) => ({ x, y, width, height, value }: LabelProps) => {
  if (typeof value !== 'number') return null
  const rightEdge = Math.max(Number(x), Number(x) + Number(width))
  return (
    <text x={rightEdge + 6} y={Number(y) + Number(height) / 2} dominantBaseline="central" fontSize={12} fill="var(--color-ink)">
      {formatValue(value, format)}
    </text>
  )
}

/**
 * Bars, grouped bars, stacked bars and histograms: one family, four arrangements.
 * Horizontal when any label is longer than ten characters (§12), because department and location
 * names do not fit under vertical bars on a phone. Histogram bands touch; everything else has a
 * 2px gap so two fills never read as one.
 */
function BarPlot({ chart, data, height }: { chart: ChartSpec; data: Series; height?: number }) {
  const format = chart.value_format
  const draw = useDrawOnce()
  const stacked = data.kind === 'stacked_bar'
  const single = data.series.length === 1
  const valueTick = axisTicks(format, axisMax(data, stacked))
  const rowHeight = data.points.length * (data.series.length * 18 + 14) + (single ? 40 : 24)
  const tall = height ?? (data.horizontal ? rowHeight : 280)
  return (
    <>
      <ResponsiveContainer width="100%" height={tall}>
        <BarChart
          data={data.points}
          layout={data.horizontal ? 'vertical' : 'horizontal'}
          margin={{ top: 8, right: data.horizontal && single ? 84 : 8, bottom: 4, left: 0 }}
          barGap={data.kind === 'histogram' ? 0 : 2}
          barCategoryGap={data.kind === 'histogram' ? 1 : '20%'}
        >
          <CartesianGrid horizontal={!data.horizontal} vertical={data.horizontal} stroke={GRID} />
          {data.horizontal ? (
            <>
              <XAxis type="number" tick={TICK} tickLine={false} axisLine={false} tickFormatter={valueTick} />
              <YAxis type="category" dataKey="x" width="auto" tick={TICK} tickLine={false} axisLine={AXIS} tickFormatter={shorten} interval={0} />
            </>
          ) : (
            <>
              {/* Every band is named while they fit; past twelve the axis thins them out itself. */}
              <XAxis dataKey="x" tick={TICK} tickLine={false} axisLine={AXIS} tickFormatter={shorten} interval={data.points.length > 12 ? 'preserveStartEnd' : 0} />
              <YAxis width={64} tick={TICK} tickLine={false} axisLine={false} tickFormatter={valueTick} />
            </>
          )}
          <Tooltip cursor={{ fill: 'var(--color-surface-2)' }} content={pointTooltip(data, format)} isAnimationActive={false} />
          {data.series.map((_, i) => (
            <Bar
              key={i}
              name={seriesLabel(data, i)}
              dataKey={(p: Point) => p.values[i]}
              stackId={stacked ? 'one' : undefined}
              fill={SERIES_COLORS[i]}
              // 4px on the value end only, anchored at the baseline. A stacked segment stays square:
              // rounding every segment turns a stack into a pile of lozenges.
              radius={stacked ? 0 : data.horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
              maxBarSize={data.kind === 'histogram' ? 9999 : 28}
              isAnimationActive={draw}
              animationDuration={400}
            >
              {/* A number on every bar is noise; one series of horizontal bars is the one case
                  where the label replaces the axis lookup entirely. */}
              {single && data.horizontal && <LabelList content={barEndLabel(format)} />}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
      <Legend names={data.series.map((_, i) => seriesLabel(data, i))} colors={SERIES_COLORS} />
    </>
  )
}

/** A trend. The value axis is fitted to the data (165 to 172 is flat from zero), and an area
 *  fills from its own colour at 24% down to 0% (§12). */
function LinePlot({ chart, data, height }: { chart: ChartSpec; data: Series; height?: number }) {
  const format = chart.value_format
  const draw = useDrawOnce()
  const area = data.kind === 'area'
  const Chart = area ? AreaChart : LineChart
  return (
    <>
      <ResponsiveContainer width="100%" height={height ?? 260}>
        <Chart data={data.points} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <defs>
            {area &&
              data.series.map((_, i) => (
                <linearGradient key={i} id={`fill-${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={SERIES_COLORS[i]} stopOpacity={0.24} />
                  <stop offset="100%" stopColor={SERIES_COLORS[i]} stopOpacity={0} />
                </linearGradient>
              ))}
          </defs>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="x" tick={TICK} tickLine={false} axisLine={AXIS} minTickGap={24} padding={{ left: 12, right: 12 }} />
          <YAxis width={64} tick={TICK} tickLine={false} axisLine={false} domain={['auto', 'auto']} tickFormatter={axisTicks(format, axisMax(data))} />
          <Tooltip cursor={{ stroke: 'var(--color-line)' }} content={pointTooltip(data, format)} isAnimationActive={false} />
          {data.series.map((_, i) =>
            area ? (
              <Area
                key={i}
                type="linear"
                name={seriesLabel(data, i)}
                dataKey={(p: Point) => p.values[i]}
                stroke={SERIES_COLORS[i]}
                strokeWidth={2}
                fill={`url(#fill-${i})`}
                dot={false}
                activeDot={{ r: 5, strokeWidth: 2, stroke: 'var(--color-surface)' }}
                isAnimationActive={draw}
                animationDuration={400}
              />
            ) : (
              <Line
                key={i}
                type="linear"
                name={seriesLabel(data, i)}
                dataKey={(p: Point) => p.values[i]}
                stroke={SERIES_COLORS[i]}
                strokeWidth={2}
                dot={data.points.length <= 24 ? { r: 3, strokeWidth: 0, fill: SERIES_COLORS[i] } : false}
                activeDot={{ r: 5, strokeWidth: 2, stroke: 'var(--color-surface)' }}
                isAnimationActive={draw}
                animationDuration={400}
              />
            ),
          )}
        </Chart>
      </ResponsiveContainer>
      <Legend names={data.series.map((_, i) => seriesLabel(data, i))} colors={SERIES_COLORS} />
    </>
  )
}

/** Part of a whole, at a glance: at most six slices with the tail as "Other", and the total in
 *  the middle, which is the number the analyst quotes. */
function DonutPlot({ chart, data, height }: { chart: ChartSpec; data: Extract<ChartData, { kind: 'donut' }>; height?: number }) {
  const format = chart.value_format
  const draw = useDrawOnce()
  const colour = (i: number) => (data.slices[i].name === 'Other' ? OTHER_COLOR : SERIES_COLORS[i])
  const share = (value: number) => `${Math.round((value / data.total) * 100)}%`
  return (
    <>
      <div className="relative">
        <ResponsiveContainer width="100%" height={height ?? 240}>
          <PieChart>
            <Tooltip
              isAnimationActive={false}
              content={({ active, payload }) => {
                const slice = payload?.[0]?.payload as { name: string; value: number } | undefined
                if (!active || !slice) return null
                return <TipCard title={slice.name} rows={[{ name: share(slice.value), value: slice.value, color: 'var(--color-series-1)' }]} format={format} />
              }}
            />
            <Pie
              data={data.slices}
              dataKey="value"
              nameKey="name"
              innerRadius="62%"
              outerRadius="92%"
              // 2px of surface between slices, rather than a stroke drawn around each one.
              paddingAngle={1}
              stroke="var(--color-surface)"
              strokeWidth={2}
              isAnimationActive={draw}
              animationDuration={400}
            >
              {data.slices.map((slice, i) => (
                <Cell key={slice.name} fill={colour(i)} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {/* The total, in the hole. Pointer-events off so it never steals a slice's hover. */}
        <div aria-hidden className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <p className="type-section tnum text-ink">{formatValue(data.total, format)}</p>
          <p className="type-micro text-ink-2">Total</p>
        </div>
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-1.5">
        {data.slices.map((slice, i) => (
          <li key={slice.name} className="inline-flex items-center gap-1.5 rounded-pill bg-fill px-2.5 py-1 type-micro text-ink-2">
            <span aria-hidden className="size-2 shrink-0 rounded-pill" style={{ background: colour(i) }} />
            {slice.name === 'Other' ? `Other (${data.otherCount})` : slice.name}
            <span className="tnum font-semibold text-ink">{share(slice.value)}</span>
          </li>
        ))}
      </ul>
    </>
  )
}

/** Two categories against a count: a grid of cells on the blue scale, with the legend that says
 *  what light and dark mean. A CSS grid, not an SVG — the cells are rectangles with text in them,
 *  and this way they wrap, print and read aloud. */
function HeatmapPlot({ chart, data }: { chart: ChartSpec; data: Extract<ChartData, { kind: 'heatmap' }> }) {
  const format = chart.value_format
  // Values fit inside a cell while the grid is short; past that they are on hover and in the table.
  const inCell = data.cols.length <= 8
  // blue-soft → blue, the §2 sequential scale: one hue, light to dark. It stops at half strength
  // on purpose — the value is written inside the cell in ink, and a cell any deeper than this
  // drops that text under 4.5:1 in dark mode, where the same scale runs the other way.
  const shade = (strength: number) => `color-mix(in srgb, var(--color-blue) ${Math.round(12 + strength * 38)}%, var(--color-blue-soft))`
  const cell = (value: number | null) =>
    value === null
      ? { background: 'var(--color-surface-2)', color: 'var(--color-ink-3)' }
      : { background: shade(Math.abs(value) / data.max), color: 'var(--color-ink)' }
  return (
    <div className="overflow-x-auto">
      <div className="min-w-fit">
        <div className="grid gap-1" style={{ gridTemplateColumns: `auto repeat(${data.cols.length}, minmax(48px, 1fr))` }}>
          <span />
          {data.cols.map((col) => (
            <span key={col} className="truncate pb-1 text-center type-micro text-ink-2" title={col}>
              {col}
            </span>
          ))}
          {data.rows.map((row, r) => (
            <div key={row} className="contents">
              <span className="self-center pr-2 text-right type-micro text-ink-2">{row}</span>
              {data.cols.map((col, c) => {
                const value = data.cells[r][c]
                return (
                  <span
                    key={col}
                    title={`${row}, ${col}: ${formatValue(value, format)}`}
                    style={cell(value)}
                    className="flex h-9 items-center justify-center rounded-input type-micro tnum"
                  >
                    {inCell ? formatValue(value, format) : ''}
                  </span>
                )
              })}
            </div>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-2 type-micro text-ink-2">
          <span>0</span>
          {/* The same two ends the cells use, so the legend is not a prettier scale than the grid. */}
          <span aria-hidden className="h-2 w-28 rounded-pill" style={{ background: `linear-gradient(90deg, ${shade(0)}, ${shade(1)})` }} />
          <span className="tnum">{formatValue(data.max, format)}</span>
          <span>{humanize(chart.y[0] ?? '')}</span>
        </div>
      </div>
    </div>
  )
}

/** Two measures rarely share a unit (CTC against rating), so the axes use plain short numbers
 *  and the tooltip shows the backend's own display strings for both. */
function ScatterPlot({ data, height }: { data: Extract<ChartData, { kind: 'scatter' }>; height?: number }) {
  const draw = useDrawOnce()
  const xLabel = humanize(data.xLabel)
  const yLabel = humanize(data.yLabel)
  const axis = { type: 'number' as const, tick: TICK, tickLine: false, domain: ['auto', 'auto'] as ['auto', 'auto'], tickFormatter: (v: number) => formatTick(v, 'number') }
  return (
    <ResponsiveContainer width="100%" height={height ?? 300}>
      <ScatterChart margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
        <CartesianGrid stroke={GRID} />
        <XAxis {...axis} dataKey="x" name={xLabel} axisLine={AXIS} label={{ value: xLabel, position: 'insideBottom', offset: -12, fontSize: 12, fill: 'var(--color-ink-2)' }} />
        <YAxis {...axis} dataKey="y" name={yLabel} width={64} axisLine={false} label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 12, fill: 'var(--color-ink-2)' }} />
        <Tooltip
          cursor={{ stroke: 'var(--color-line)' }}
          isAnimationActive={false}
          content={({ active, payload }) => {
            const point = payload?.[0]?.payload as ScatterPoint | undefined
            if (!active || !point) return null
            return (
              <div className="rounded-card bg-surface px-3 py-2 type-micro text-ink shadow-3">
                {point.label && <p className="font-semibold">{point.label}</p>}
                <p className="text-ink-2">
                  {xLabel}: <span className="tnum text-ink">{point.xDisplay}</span>
                </p>
                <p className="text-ink-2">
                  {yLabel}: <span className="tnum text-ink">{point.yDisplay}</span>
                </p>
              </div>
            )
          }}
        />
        <Scatter
          data={data.points}
          fill={SERIES_COLORS[0]}
          fillOpacity={0.75}
          // A 2px surface ring, so two dots that overlap stay two dots.
          stroke="var(--color-surface)"
          strokeWidth={2}
          isAnimationActive={draw}
          animationDuration={400}
        />
      </ScatterChart>
    </ResponsiveContainer>
  )
}
