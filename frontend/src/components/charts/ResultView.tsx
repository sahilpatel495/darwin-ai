// Chart with a table always one click away: a chart is for the shape, the table is for the
// figure someone will quote. When the result does not fit a chart we show the table and say why.
import { useMemo, useState } from 'react'
import { csvFileName, downloadCsv, toCsv } from '../../lib/csv'
import type { ChartSpec, ResultTable } from '../../types'
import { buildChartData } from './chartData'
import DataTable from './DataTable'
import ResultChart from './ResultChart'

const toggle = (active: boolean): string =>
  `px-3 py-1 text-sm first:rounded-l-md last:rounded-r-md border border-line -ml-px first:ml-0 ${active ? 'bg-accent-soft text-accent-ink font-medium' : 'bg-surface text-ink-soft hover:bg-sunken'}`

interface ResultViewProps {
  chart: ChartSpec | null
  table: ResultTable
  /** Names the downloaded file, so a folder of exports still says what each one answers. */
  question: string
}

export default function ResultView({ chart, table, question }: ResultViewProps) {
  const data = useMemo(() => (chart ? buildChartData(chart, table) : null), [chart, table])
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const caption = chart?.title || 'Result'

  // The table with its way out to Excel. The file holds the raw values (full precision, ISO dates)
  // of every row the answer has, not only the rows drawn on screen.
  const tableView = (
    <>
      <DataTable table={table} caption={caption} />
      {table.rows.length > 0 && (
        <button
          type="button"
          onClick={() => downloadCsv(csvFileName(question), toCsv(table.columns, table.rows))}
          className="mt-2 rounded-md border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink hover:bg-sunken"
        >
          Download CSV ({table.rows.length.toLocaleString('en-IN')} {table.rows.length === 1 ? 'row' : 'rows'})
        </button>
      )}
    </>
  )

  if (!chart || !data || data.kind === 'table') {
    return (
      <div>
        {data?.kind === 'table' && data.reason && <p className="mb-2 text-xs text-ink-soft">{data.reason}</p>}
        {tableView}
        {chart?.note && <p className="mt-2 text-xs text-ink-soft">{chart.note}</p>}
      </div>
    )
  }
  return (
    <div>
      <div role="group" aria-label="Show the result as" className="mb-3 flex justify-end">
        <button type="button" aria-pressed={view === 'chart'} onClick={() => setView('chart')} className={toggle(view === 'chart')}>
          Chart
        </button>
        <button type="button" aria-pressed={view === 'table'} onClick={() => setView('table')} className={toggle(view === 'table')}>
          Table
        </button>
      </div>
      {view === 'chart' ? <ResultChart chart={chart} data={data} /> : tableView}
    </div>
  )
}
