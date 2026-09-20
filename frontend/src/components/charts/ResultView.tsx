// The visual half of an answer (§12): the chart the backend chose, the other shapes that fit the
// same result, and the table always one click away — a chart is for the shape, the table is for
// the figure someone will quote.
//
// Two callers, two shapes. The answer card passes `allowSwitch` and gets the controls; a tile and
// the printed board pass nothing and get the chart alone.
import { useMemo, useState } from 'react'
import { Button, Dialog, IconButton, SegmentedControl } from '../ui'
import { csvFileName, downloadCsv, toCsv } from '../../lib/csv'
import type { ChartSpec, ResultTable } from '../../types'
import { buildChartData, fitTypes, type ChartData } from './chartData'
import DataTable from './DataTable'
import { DownloadIcon, ExpandIcon } from './icons'
import ResultChart from './ResultChart'

export interface ResultViewProps {
  chart: ChartSpec | null
  table: ResultTable | null
  /** Already built by the answer card, so the spec is read once per answer. */
  data?: ChartData | null
  /** Names the downloaded file, so a folder of exports still says what each one answers. */
  question?: string
  /** The controls: the chart-type switch, Download CSV and expand. Off for a tile and the board. */
  allowSwitch?: boolean
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

export default function ResultView({ chart, table, data, question = '', allowSwitch = false }: ResultViewProps) {
  // The type on screen. Null means "whatever the backend chose", so a new answer needs no effect
  // to reset it: a different answer is a different component.
  const [picked, setPicked] = useState<ChartSpec['type'] | null>(null)
  const [expanded, setExpanded] = useState(false)

  const shown = picked ?? chart?.type ?? 'table'
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
      {built?.kind === 'table' && built.reason && <p className="mb-3 type-small text-ink-2">{built.reason}</p>}
      <DataTable table={table} caption={caption} />
      {!plotted && chart?.note && <p className="mt-3 type-small text-ink-2">{chart.note}</p>}
    </>
  )

  const visual = plotted && chart ? <ResultChart chart={chart} data={plotted} /> : tableView

  if (!allowSwitch) return <div>{visual}</div>

  // An empty result is one sentence. Controls around nothing would be furniture.
  if (table.rows.length === 0) return <div>{tableView}</div>

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {options.length > 1 ? (
          <SegmentedControl
            label="Show the result as"
            size="sm"
            value={shown}
            onChange={(value) => setPicked(value as ChartSpec['type'])}
            options={options.map((type) => ({ value: type, label: TYPE_LABELS[type] }))}
          />
        ) : (
          chart?.title && <p className="type-section text-ink">{chart.title}</p>
        )}
        <div className="ml-auto flex items-center gap-1">
          {plotted && (
            <IconButton label="Open the chart larger" variant="ghost" size="sm" onClick={() => setExpanded(true)}>
              <ExpandIcon size={16} />
            </IconButton>
          )}
          {/* Named in full rather than left as a glyph: it is the one control here that produces a
              file, and a tooltip is no help on a phone. The file holds the raw values (full
              precision, ISO dates) of every row the answer has, not only the rows drawn. */}
          <Button variant="ghost" size="sm" onClick={() => downloadCsv(csvFileName(question || caption), toCsv(table.columns, table.rows))}>
            <DownloadIcon size={16} />
            Download CSV
          </Button>
        </div>
      </div>

      {options.length > 1 && chart?.title && <p className="mb-2 type-small text-ink-2">{chart.title}</p>}
      {visual}

      {/* Mounted only while it is open: otherwise every answer on the page would carry a second
          copy of its table in the DOM, for a dialog nobody has asked for. */}
      {expanded && (
        <Dialog open onClose={() => setExpanded(false)} title={caption} size="xl">
          {plotted && chart && <ResultChart chart={chart} data={plotted} height={plotted.kind === 'heatmap' ? undefined : 420} />}
          <div className="mt-6">
            <DataTable table={table} caption={caption} />
          </div>
        </Dialog>
      )}
    </div>
  )
}
