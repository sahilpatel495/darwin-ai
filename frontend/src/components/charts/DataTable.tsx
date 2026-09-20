// The exact values behind every answer. Cells show the backend's display strings, so the table,
// the answer text and the chart tooltips all quote the same figure.
//
// A sticky header on the soft surface, a hairline under every row, figures right-aligned with
// tabular numerals so a column of rupees lines up (§8).
import type { ResultTable } from '../../types'
import { humanize } from '../../lib/format'

// ponytail: the server caps a result at 5,000 rows; drawing them all stalls a phone. Show the
// first 200 and say so; "Download CSV" above an answer's table has every row. Add paging if
// analysts need to read further on screen.
const MAX_RENDERED_ROWS = 200

/** A column is right-aligned when every value it holds is a number (empty cells aside). */
function numericColumns(table: ResultTable): boolean[] {
  return table.columns.map((_, c) => {
    const cells = table.rows.map((row) => row[c]).filter((cell) => cell !== null)
    return cells.length > 0 && cells.every((cell) => typeof cell === 'number')
  })
}

interface DataTableProps {
  table: ResultTable
  caption: string
  /** Said under the table when it shows only part of the data. Defaults to advice for an answer;
   *  a file preview passes its own, because "add a filter to your question" makes no sense there. */
  cutNote?: string
}

export default function DataTable({ table, caption, cutNote }: DataTableProps) {
  if (table.rows.length === 0) return <p className="text-body-md text-slate">The query ran and returned no rows.</p>
  const numeric = numericColumns(table)
  const shown = table.rows.slice(0, MAX_RENDERED_ROWS)
  const cut = shown.length < table.rows.length || table.truncated
  return (
    <div>
      {/* ~12 rows tall, then it scrolls in place; wide results scroll sideways on a phone. */}
      <div className="max-h-[26.5rem] overflow-auto rounded-xxl border border-hairline-soft" tabIndex={0} role="region" aria-label={`${caption}, table`}>
        <table className="w-full border-collapse text-body-sm">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              {table.columns.map((name, c) => (
                <th
                  key={c}
                  scope="col"
                  className={`sticky top-0 z-10 border-b border-hairline bg-surface-soft px-4 py-2.5 font-bold whitespace-nowrap text-ink-deep ${numeric[c] ? 'text-right' : 'text-left'}`}
                >
                  {humanize(name)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row, r) => (
              <tr key={r} className="border-b border-hairline-soft last:border-b-0 hover:bg-surface-soft">
                {row.map((cell, c) => (
                  <td key={c} className={`max-w-xs truncate px-4 py-2 text-ink ${numeric[c] ? 'text-right tnum' : 'text-left'}`} title={table.display[r]?.[c]}>
                    {table.display[r]?.[c] ?? String(cell ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {cut && (
        <p className="mt-3 text-body-sm text-slate">
          {cutNote ?? `Showing the first ${shown.length.toLocaleString('en-IN')} rows. The full result is longer. Add a filter or a grouping to your question to narrow it down.`}
        </p>
      )}
    </div>
  )
}
