// Chart with a table always one click away: a chart is for the shape, the table is for the
// figure someone will quote. When the result does not fit a chart we show the table and say why.
import { useMemo, useState } from 'react'
import type { ChartSpec, ResultTable } from '../../types'
import { buildChartData } from './chartData'
import DataTable from './DataTable'
import ResultChart from './ResultChart'

const toggle = (active: boolean): string =>
  `px-3 py-1 text-sm first:rounded-l-md last:rounded-r-md border border-line -ml-px first:ml-0 ${active ? 'bg-accent-soft text-accent-ink font-medium' : 'bg-surface text-ink-soft hover:bg-sunken'}`

export default function ResultView({ chart, table }: { chart: ChartSpec | null; table: ResultTable }) {
  const data = useMemo(() => (chart ? buildChartData(chart, table) : null), [chart, table])
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const caption = chart?.title || 'Result'

  if (!chart || !data || data.kind === 'table') {
    return (
      <div>
        {data?.kind === 'table' && data.reason && <p className="mb-2 text-xs text-ink-soft">{data.reason}</p>}
        <DataTable table={table} caption={caption} />
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
      {view === 'chart' ? <ResultChart chart={chart} data={data} /> : <DataTable table={table} caption={caption} />}
    </div>
  )
}
