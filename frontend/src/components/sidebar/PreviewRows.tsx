// "Preview rows": the first rows of one uploaded table, as Verity read them. An analyst checks a
// file by looking at it, and the Data Health receipt only describes it. The rows travel from the
// server to this browser and nowhere else, and the dialog says so, because the rest of the app
// promises that rows are never shown to the AI.
//
// A native <dialog>, like the privacy explainer in the header: focus trapping, Esc to close and
// the backdrop come for free. Rows are fetched each time it opens and dropped when it closes, so
// personal data does not linger in memory behind a closed dialog.

import { useId, useRef, useState } from 'react'
import { ApiError, previewTable } from '../../api'
import type { ResultTable, TableProfile } from '../../types'
import ErrorNotice from '../answer/ErrorNotice'
import DataTable from '../charts/DataTable'

const PREVIEW_ROWS = 50

type Load = { state: 'closed' } | { state: 'loading' } | { state: 'ready'; table: ResultTable } | { state: 'failed'; message: string; nextStep: string }

export default function PreviewRows({ sessionId, table }: { sessionId: string; table: TableProfile }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const [load, setLoad] = useState<Load>({ state: 'closed' })

  const fetchRows = () => {
    // A reply that lands after the dialog was closed is dropped, so rows never outlive the dialog.
    const settle = (next: Load) => setLoad((now) => (now.state === 'loading' ? next : now))
    setLoad({ state: 'loading' })
    previewTable(sessionId, table.name, PREVIEW_ROWS)
      // The file's own headers ("Emp Code"), not the SQL names: this is the analyst's file.
      .then((rows) => settle({ state: 'ready', table: { ...rows, columns: rows.columns.map((name) => table.columns.find((c) => c.name === name)?.label ?? name) } }))
      .catch((error: unknown) => {
        const known = error instanceof ApiError
        settle({ state: 'failed', message: known ? error.message : 'The rows could not be loaded.', nextStep: known ? error.nextStep : 'Close this and try again.' })
      })
  }

  const open = () => {
    dialog.current?.showModal()
    fetchRows()
  }

  const total = table.row_count.toLocaleString('en-IN')
  return (
    <>
      <button type="button" onClick={open} aria-haspopup="dialog" className="text-sm font-medium text-accent underline-offset-2 hover:underline">
        Preview rows
      </button>
      <dialog
        ref={dialog}
        aria-labelledby={titleId}
        onClose={() => setLoad({ state: 'closed' })}
        className="m-auto w-[min(64rem,calc(100vw-2rem))] rounded-card border border-line bg-surface p-0 text-ink backdrop:bg-ink/40"
      >
        {/* Drawn only while open, so a closed dialog holds no rows. */}
        {load.state !== 'closed' && (
          <div className="space-y-3 p-4 sm:p-5">
            <div>
              <h2 id={titleId} className="text-lg font-semibold break-words text-ink">
                {table.source_file}
                {table.sheet && <span className="font-normal text-ink-soft">, sheet {table.sheet}</span>}
              </h2>
              <p className="mt-1 text-sm text-ink-soft">Shown only to you. Rows are never sent to the AI.</p>
            </div>
            {load.state === 'loading' && <div role="status" aria-label="Loading rows" className="h-40 animate-pulse rounded-lg bg-sunken" />}
            {load.state === 'ready' && (
              <DataTable table={load.table} caption={`First rows of ${table.source_file}`} cutNote={`The first ${load.table.rows.length} of ${total} rows, after cleaning.`} />
            )}
            {load.state === 'failed' && <ErrorNotice message={load.message} nextStep={load.nextStep} onRetry={fetchRows} />}
            <form method="dialog" className="text-right">
              <button className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-ink">Close</button>
            </form>
          </div>
        )}
      </dialog>
    </>
  )
}
