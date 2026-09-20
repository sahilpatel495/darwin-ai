// "Preview rows": the first rows of one uploaded file, as Verity read them. An analyst checks a
// file by looking at it, and the Data Health receipt only describes it. The rows travel from the
// server to this browser and nowhere else, and the dialog says so, because the rest of the app
// promises that rows are never shown to the AI.
//
// Rows are fetched each time it opens and dropped when it closes, so personal data does not
// linger in memory behind a closed dialog.

import { useState } from 'react'
import { ApiError, previewTable } from '../../api'
import type { ResultTable, TableProfile } from '../../types'
import DataTable from '../charts/DataTable'
import { Banner, Button, Dialog, Skeleton } from '../ui'

const PREVIEW_ROWS = 50

type Load = { state: 'closed' } | { state: 'loading' } | { state: 'ready'; table: ResultTable } | { state: 'failed'; message: string; nextStep: string }

export default function PreviewRows({ sessionId, table }: { sessionId: string; table: TableProfile }) {
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

  const total = table.row_count.toLocaleString('en-IN')
  return (
    <>
      <Button size="sm" onClick={fetchRows} aria-haspopup="dialog">
        Preview rows
      </Button>
      <Dialog
        open={load.state !== 'closed'}
        onClose={() => setLoad({ state: 'closed' })}
        size="lg"
        title={table.sheet ? `${table.source_file}, sheet ${table.sheet}` : table.source_file}
        footer={
          <Button variant="primary" onClick={() => setLoad({ state: 'closed' })}>
            Close
          </Button>
        }
      >
        <p className="type-small text-ink-soft">Shown only to you. Rows are never sent to the AI.</p>
        <div className="mt-3">
          {load.state === 'loading' && (
            <div role="status" aria-label="Loading rows">
              <Skeleton className="h-40 w-full" />
            </div>
          )}
          {load.state === 'ready' && (
            <DataTable table={load.table} caption={`First rows of ${table.source_file}`} cutNote={`The first ${load.table.rows.length} of ${total} rows, after cleaning.`} />
          )}
          {load.state === 'failed' && (
            <Banner
              tone="error"
              nextStep={load.nextStep}
              action={
                <Button size="sm" onClick={fetchRows}>
                  Try again
                </Button>
              }
            >
              {load.message}
            </Banner>
          )}
        </div>
      </Dialog>
    </>
  )
}
