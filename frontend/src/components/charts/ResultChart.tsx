// Draws the chart the backend's rules chose. The model never picks or styles a chart: the spec
// is plain data, and chartData.ts has already turned anything that does not fit into a table.
//
// Ledger styling (§2): series colours in token order, no frame around the plot, a hairline grid
// in the rule colour, and every number in the small type with tabular figures — the axis, the
// tooltip and the label beside a bar all read like the table under them.
import { Bar, BarChart, CartesianGrid, LabelList, Legend, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, type LabelProps } from 'recharts'
import type { ChartSpec } from '../../types'
import { formatTick, formatValue, humanize } from '../../lib/format'
import type { ChartData, Point, ScatterPoint } from './chartData'

type Plotted = Exclude<ChartData, { kind: 'table' | 'kpi' }>
type Series = Extract<ChartData, { kind: 'bar' | 'line' | 'grouped_bar' }>

// Written out in full so Tailwind sees each token in the source and keeps it in the CSS.
const SERIES_COLORS = ['var(--color-series-1)', 'var(--color-series-2)', 'var(--color-series-3)', 'var(--color-series-4)', 'var(--color-series-5)']

const TICK = { fill: 'var(--color-ink-soft)', fontSize: 13 }
const GRID = 'var(--color-rule)'
// A tooltip floats, so it is the one thing here that casts a shadow.
const TOOLTIP_BOX = {
  background: 'var(--color-sheet)',
  border: '1px solid var(--color-rule)',
  borderRadius: 4,
  fontSize: 13,
  color: 'var(--color-ink)',
  boxShadow: 'var(--shadow-float)',
}
const shorten = (label: string): string => (label.length > 20 ? `${label.slice(0, 19)}…` : label) // full name is in the tooltip and table
// Legend text stays in ink: colour identifies the mark, never the words.
const legendText = (name: string) => <span className="type-small text-ink-soft">{name}</span>

interface Props {
  chart: ChartSpec
  data: Plotted
}

export default function ResultChart({ chart, data }: Props) {
  const count = data.points.length
  const label = `${chart.title}. ${CHART_NAMES[data.kind]} with ${count} ${count === 1 ? 'point' : 'points'}. Switch to the table for exact values.`
  const omitted = data.kind === 'scatter' ? 0 : data.omitted
  return (
    <figure className="m-0">
      <figcaption className="mb-3 type-small text-ink-soft">{chart.title}</figcaption>
      {/* tabular-nums is set once here and inherited by every <text> the chart draws. */}
      <div role="img" aria-label={label} className="tabular-nums">
        {data.kind === 'scatter' ? <ScatterPlot data={data} /> : data.kind === 'line' ? <LinePlot chart={chart} data={data} /> : <BarPlot chart={chart} data={data} />}
      </div>
      {omitted > 0 && (
        <p className="mt-3 type-small text-ink-soft">
          The first {count} of {count + omitted} rows are drawn. The table has all of them.
        </p>
      )}
      {chart.note && <p className="mt-2 type-small text-ink-soft">{chart.note}</p>}
    </figure>
  )
}

const CHART_NAMES: Record<Plotted['kind'], string> = {
  bar: 'Bar chart',
  grouped_bar: 'Grouped bar chart',
  line: 'Line chart',
  scatter: 'Scatter chart',
}

/** Series names of a grouped bar are the customer's own values; column names get tidied. */
const seriesLabel = (data: Series, i: number): string => (data.kind === 'grouped_bar' ? data.series[i] : humanize(data.series[i]))

const tooltipValue = (format: ChartSpec['value_format']) => (value: unknown) => (typeof value === 'number' ? formatValue(value, format) : String(value ?? ''))

/** The exact value beside a bar, in the full format so it reads like the table and the answer.
 *  It always sits to the right of the bar's rightmost edge. For a negative bar that edge is the
 *  zero line, where the row is empty; Recharts' own position="right" would put the label at the
 *  bar's left end, on top of the department name. */
export const barEndLabel = (format: ChartSpec['value_format']) => ({ x, y, width, height, value }: LabelProps) => {
  if (typeof value !== 'number') return null
  const rightEdge = Math.max(Number(x), Number(x) + Number(width))
  return (
    <text x={rightEdge + 6} y={Number(y) + Number(height) / 2} dominantBaseline="central" fontSize={13} fill="var(--color-ink)">
      {formatValue(value, format)}
    </text>
  )
}

/** Horizontal bars: department and location names are long, and 12 of them do not fit under
 *  vertical bars on a phone. Bars always start at zero. */
function BarPlot({ chart, data }: { chart: ChartSpec; data: Series }) {
  const format = chart.value_format
  const single = data.series.length === 1
  const height = data.points.length * (data.series.length * 18 + 14) + (single ? 40 : 72)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data.points} layout="vertical" margin={{ top: 4, right: single ? 84 : 16, bottom: 4, left: 0 }} barGap={2}>
        <CartesianGrid horizontal={false} stroke={GRID} />
        <XAxis type="number" tick={TICK} tickLine={false} axisLine={false} tickFormatter={(v: number) => formatTick(v, format)} />
        <YAxis type="category" dataKey="x" width="auto" tick={TICK} tickLine={false} axisLine={{ stroke: GRID }} tickFormatter={shorten} interval={0} />
        <Tooltip cursor={{ fill: 'var(--color-wash)' }} contentStyle={TOOLTIP_BOX} formatter={tooltipValue(format)} isAnimationActive={false} />
        {!single && <Legend iconType="square" formatter={legendText} />}
        {data.series.map((_, i) => (
          // 2px corners: a bar is a ruled block, not a lozenge.
          <Bar key={i} name={seriesLabel(data, i)} dataKey={(p: Point) => p.values[i]} fill={SERIES_COLORS[i]} radius={[0, 2, 2, 0]} maxBarSize={22} isAnimationActive={false}>
            {single && <LabelList content={barEndLabel(format)} />}
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

/** The value axis of a line is fitted to the data (a trend of 165 to 172 is flat from zero). */
function LinePlot({ chart, data }: { chart: ChartSpec; data: Series }) {
  const format = chart.value_format
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data.points} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="x" tick={TICK} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={24} padding={{ left: 12, right: 12 }} />
        <YAxis width={64} tick={TICK} tickLine={false} axisLine={false} domain={['auto', 'auto']} tickFormatter={(v: number) => formatTick(v, format)} />
        <Tooltip contentStyle={TOOLTIP_BOX} formatter={tooltipValue(format)} isAnimationActive={false} />
        {data.series.length > 1 && <Legend iconType="plainline" formatter={legendText} />}
        {data.series.map((_, i) => (
          <Line
            key={i}
            type="linear"
            name={seriesLabel(data, i)}
            dataKey={(p: Point) => p.values[i]}
            stroke={SERIES_COLORS[i]}
            strokeWidth={2}
            dot={data.points.length <= 24 ? { r: 3, strokeWidth: 0, fill: SERIES_COLORS[i] } : false}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

/** Two measures rarely share a unit (CTC against rating), so the axes use plain short numbers
 *  and the tooltip shows the backend's own display strings for both. */
function ScatterPlot({ data }: { data: Extract<ChartData, { kind: 'scatter' }> }) {
  const xLabel = humanize(data.xLabel)
  const yLabel = humanize(data.yLabel)
  const axis = { type: 'number' as const, tick: TICK, tickLine: false, domain: ['auto', 'auto'] as ['auto', 'auto'], tickFormatter: (v: number) => formatTick(v, 'number') }
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
        <CartesianGrid stroke={GRID} />
        <XAxis {...axis} dataKey="x" name={xLabel} axisLine={{ stroke: GRID }} label={{ value: xLabel, position: 'insideBottom', offset: -12, fontSize: 13, fill: 'var(--color-ink-soft)' }} />
        <YAxis {...axis} dataKey="y" name={yLabel} width={64} axisLine={false} label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 13, fill: 'var(--color-ink-soft)' }} />
        <Tooltip
          cursor={{ stroke: GRID }}
          isAnimationActive={false}
          content={({ active, payload }) => {
            const point = payload?.[0]?.payload as ScatterPoint | undefined
            if (!active || !point) return null
            return (
              <div className="rounded-control border border-rule bg-sheet px-3 py-2 type-small text-ink shadow-float">
                {point.label && <p className="font-medium">{point.label}</p>}
                <p>{xLabel}: {point.xDisplay}</p>
                <p>{yLabel}: {point.yDisplay}</p>
              </div>
            )
          }}
        />
        <Scatter data={data.points} fill={SERIES_COLORS[0]} fillOpacity={0.7} isAnimationActive={false} />
      </ScatterChart>
    </ResponsiveContainer>
  )
}
