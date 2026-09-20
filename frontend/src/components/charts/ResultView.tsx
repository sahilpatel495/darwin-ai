// The visual half of an answer (§8): the chart the backend chose, the other shapes that fit the
// same result, and the table always one tap away — a chart is for the shape, the table is for the
// figure someone will quote.
//
// Two callers, two shapes. The answer card passes `allowSwitch` and gets the chart-type pill tabs;
// a tile and the printed board pass nothing and get the chart alone. Saving, copying, downloading
// and expanding belong to the card around this, not to the picture.
import { useMemo, useState } from 'react'
import { PillTabs } from '../ui'
import type { ChartSpec, ResultTable } from '../../types'
import { buildChartData, fitTypes, type ChartData } from './chartData'
import DataTable from './DataTable'
import ResultChart from './ResultChart'

export interface ResultViewProps {
  chart: ChartSpec | null
  table: ResultTable | null
  /** Already built by the answer card, so the spec is read once per answer. */
  data?: ChartData | null
  /** The chart-type switcher. Off for a tile and for the board, which print one view. */
  allowSwitch?: boolean
  /** The shape to show, when the card around this remembers what the reader picked. With it, this
   *  view is controlled — which is what keeps the chart in the card and the chart in the expand
   *  dialog on the same shape. Without it the view keeps its own choice. */
  type?: ChartSpec['type']
  /** Reports what the reader switched to, so the card can open the expanded view on the same shape. */
  onTypeChange?: (type: ChartSpec['type']) => void
  /** A floor on the chart's height, for the expanded dialog — which is wider than the card and,
   *  without this, exactly as short. A chart that sizes itself by its rows keeps its own height. */
  minHeight?: number
}

const TYPE_LABELS: Record<ChartSpec['type'], string> = {
  kpi: 'Figure',
  bar: 'Bar',
  line: 'Line',
  area: 'Area',
  grouped_bar: 'Grouped',
  stacked_bar: 'Stacked',
  donut: 'Donut',
  histogram: 'Histogram',
  heatmap: 'Heatmap',
  scatter: 'Scatter',
  table: 'Table',
}

export default function ResultView({ chart, table, data, allowSwitch = false, type, onTypeChange, minHeight }: ResultViewProps) {
  // The type on screen. Null means "whatever the backend chose", so a new answer needs no effect
  // to reset it: a different answer is a different component.
  const [picked, setPicked] = useState<ChartSpec['type'] | null>(null)

  const shown = type ?? picked ?? chart?.type ?? 'table'
  const options = useMemo(() => (chart && table && allowSwitch ? fitTypes(chart, table) : []), [chart, table, allowSwitch])
  // `data` is the backend's own choice, already built; any other type is built here on demand.
  const built = useMemo(() => {
    if (!chart || !table) return null
    if (shown === chart.type && data) return data
    return buildChartData({ ...chart, type: shown }, table)
  }, [chart, table, data, shown])

  if (!table) return null // a tile with no result at all (the data-quality checklist)
  const caption = chart?.title || 'Result'
  // kpi is drawn as the answer's hero figure, never here; if one reaches this far, the table is right.
  const plotted = built && built.kind !== 'table' && built.kind !== 'kpi' ? built : null

  const tableView = (
    <>
      {built?.kind === 'table' && built.reason && <p className="mb-3 text-body-sm text-slate">{built.reason}</p>}
      <DataTable table={table} caption={caption} />
      {!plotted && chart?.note && <p className="mt-3 text-body-sm text-slate">{chart.note}</p>}
    </>
  )

  const visual = plotted && chart ? <ResultChart chart={chart} data={plotted} minHeight={minHeight} /> : tableView

  // A tile and the board draw the picture alone: their own heading already says what it is.
  if (!allowSwitch) return <div>{visual}</div>
  // An empty result is one sentence. Controls around nothing would be furniture.
  if (table.rows.length === 0) return <div>{tableView}</div>

  const titled = (
    <>
      {chart?.title && <p className="mb-3 text-body-sm text-slate">{chart.title}</p>}
      {visual}
    </>
  )
  if (options.length < 2) return <div>{titled}</div>

  return (
    <PillTabs
      label="Show the result as"
      size="sm"
      active={shown}
      onChange={(value) => {
        setPicked(value as ChartSpec['type'])
        onTypeChange?.(value as ChartSpec['type'])
      }}
      tabs={options.map((type) => ({ id: type, label: TYPE_LABELS[type] }))}
    >
      {/* The panel the pills switch. Naming it as one is what makes them a real tablist. */}
      <div className="pt-5">{titled}</div>
    </PillTabs>
  )
}
