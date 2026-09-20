// Chart with a table always one click away: a chart is for the shape, the table is for the
// figure someone will quote. When the result does not fit a chart we show the table and say why.
import { useState } from 'react'
import { Button } from '../ui'
import { csvFileName, downloadCsv, toCsv } from '../../lib/csv'
import type { ChartSpec, ResultTable } from '../../types'
import type { ChartData } from './chartData'
import DataTable from './DataTable'
import ResultChart from './ResultChart'

const view = (active: boolean): string =>
  `-mb-px border-b-2 pb-2 type-title transition-colors duration-100 ${active ? 'border-indigo text-ink' : 'border-transparent text-ink-soft hover:text-ink'}`

interface ResultViewProps {
  chart: ChartSpec | null
  table: ResultTable
  /** Already built by the statement, so the spec is read once per answer. */
  data: ChartData | null
  /** Names the downloaded file, so a folder of exports still says what each one answers. */
  question: string
  /** The board prints one view and no controls (§6.5). */
  board?: boolean
}

export default function ResultView({ chart, table, data, question, board = false }: ResultViewProps) {
  const [shown, setShown] = useState<'chart' | 'table'>('chart')
  const caption = chart?.title || 'Result'
  // kpi is drawn as the statement's Figure, never here; if one reaches this far, the table is right.
  const plotted = data && data.kind !== 'table' && data.kind !== 'kpi' ? data : null

  const tableView = (
    <>
      {data?.kind === 'table' && data.reason && <p className="mb-3 type-small text-ink-soft">{data.reason}</p>}
      <DataTable table={table} caption={caption} />
      {!plotted && chart?.note && <p className="mt-3 type-small text-ink-soft">{chart.note}</p>}
    </>
  )

  if (board) return <div>{plotted && chart ? <ResultChart chart={chart} data={plotted} /> : tableView}</div>

  // An empty result is one sentence. A rule with a toggle over it would be furniture around nothing.
  if (table.rows.length === 0) return <div>{tableView}</div>

  return (
    <div>
      <div className="flex flex-wrap items-end gap-x-6 gap-y-1 border-b border-rule">
        {plotted ? (
          <div role="group" aria-label="Show the result as" className="flex gap-5">
            <button type="button" aria-pressed={shown === 'chart'} onClick={() => setShown('chart')} className={view(shown === 'chart')}>
              Chart
            </button>
            <button type="button" aria-pressed={shown === 'table'} onClick={() => setShown('table')} className={view(shown === 'table')}>
              Table
            </button>
          </div>
        ) : (
          chart?.title && <p className="pb-2 type-title text-ink">{chart.title}</p>
        )}
        {/* The file holds the raw values (full precision, ISO dates) of every row the answer has,
            not only the rows drawn on screen. */}
        <div className="ml-auto pb-1.5">
          <Button variant="quiet" size="sm" onClick={() => downloadCsv(csvFileName(question), toCsv(table.columns, table.rows))}>
            Download CSV
          </Button>
        </div>
      </div>

      <div className="mt-4">{plotted && chart && shown === 'chart' ? <ResultChart chart={chart} data={plotted} /> : tableView}</div>
    </div>
  )
}
