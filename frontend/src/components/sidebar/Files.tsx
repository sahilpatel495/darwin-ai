// The Files tab of the Data drawer: one roomy row per uploaded file, each opening to its Data
// Health receipt. The receipt is the proof that the mess in the export was handled on purpose, so
// it is itemised like a receipt — what was done on the left, how much of it right-aligned — and a
// file that needs a look says so on its closed row, before anyone opens anything.

import type { Catalog, TableProfile } from '../../types'
import { EXPLAIN } from '../education/explain'
import { Badge, Button, WhatsThis } from '../ui'
import Expander from './Expander'
import PreviewRows from './PreviewRows'
import type { ReceiptItem } from './wording'
import { TYPE_NOUN, count, needsALook, receiptLines } from './wording'

/** The amber mark on a receipt line. Never the only signal: the line beside it says the same. */
function Mark() {
  return <span aria-hidden className="mt-[7px] size-1.5 shrink-0 rounded-full bg-attention" />
}

/** The receipt sits in a tinted block: a till roll inside the row it belongs to, not a second card. */
function Receipt({ items }: { items: ReceiptItem[] }) {
  return (
    <ul className="mt-3 rounded-xl bg-surface-soft px-4">
      {items.map((item, i) => (
        // Index keys: the receipt is rebuilt whole whenever the catalog changes and never reordered.
        <li key={i} className="border-b border-hairline py-3 last:border-b-0">
          <div className="flex items-start justify-between gap-4">
            <span className="flex min-w-0 gap-2 text-body-sm text-ink">
              {item.tone === 'warn' && <Mark />}
              <span className="min-w-0">
                {item.tone === 'warn' && <span className="sr-only">Needs a look: </span>}
                {item.label}
              </span>
            </span>
            {item.amount && <span className="shrink-0 text-body-sm font-bold tnum text-ink-deep">{item.amount}</span>}
          </div>
          {item.note && <p className="mt-1 text-body-sm text-steel">{item.note}</p>}
        </li>
      ))}
    </ul>
  )
}

function FileRow({ sessionId, table }: { sessionId: string | null; table: TableProfile }) {
  const label = (column: string) => table.columns.find((c) => c.name === column)?.label ?? column
  const items = receiptLines(table.health, label)
  const look = needsALook(items)

  return (
    <Expander
      chevronAtEnd
      className="border-b border-hairline-soft last:border-b-0"
      summaryClassName="px-3 py-4"
      label={
        <>
          {/* Wrapped, not truncated: at 390 wide a long export name is most of the row, and the
              file's name is the one thing the analyst is looking for. */}
          <span className="block text-subtitle-lg break-words text-ink-deep" title={table.source_file}>
            {table.source_file}
          </span>
          <span className="mt-0.5 block text-body-sm tnum text-slate">
            {table.sheet && <>Sheet {table.sheet}, </>}
            {count(table.row_count, 'row')}, {count(table.columns.length, 'column')}
          </span>
          {look && (
            <span className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
              <Badge tone="attention">Needs a look</Badge>
              <span className="text-body-sm text-charcoal">{look}</span>
            </span>
          )}
        </>
      }
    >
      <div className="px-3 pb-5">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-body-sm font-bold text-ink-deep">When we read this file</h3>
          {/* The "?" sits at the right edge and opens leftwards: the drawer is only as wide as
              this column, so anywhere else its panel would be clipped. */}
          <WhatsThis {...EXPLAIN.dataHealth} align="right" />
        </div>
        <Receipt items={items} />

        {/* Only with a live session: without one there are no rows on the server to show. */}
        {sessionId && (
          <div className="mt-4">
            <PreviewRows sessionId={sessionId} table={table} />
          </div>
        )}

        <Expander
          chevronAtEnd
          className="mt-4 border-t border-hairline-soft"
          summaryClassName="px-0 py-3"
          label={<span className="text-body-sm font-bold text-ink-deep">Columns ({table.columns.length})</span>}
        >
          {/* Headers as they are written in the file. The SQL names matter only to someone reading
              the SQL under an answer, so they sit in a tooltip and a footnote. */}
          <ul className="pb-3">
            {table.columns.map((column) => (
              <li key={column.name} className="flex items-baseline justify-between gap-4 py-1.5">
                <span className="min-w-0 truncate text-body-sm text-ink" title={`${column.label} (${column.name} in the SQL)`}>
                  {column.label}
                </span>
                <span className="shrink-0 text-body-sm text-steel">{column.pii ? 'Hidden from the AI' : TYPE_NOUN[column.type]}</span>
              </li>
            ))}
          </ul>
          <p className="pb-3 text-body-sm break-words text-steel">
            In the SQL under each answer this file is called <code className="text-code text-ink">{table.name}</code>.
          </p>
        </Expander>
      </div>
    </Expander>
  )
}

interface FilesProps {
  sessionId: string | null
  catalog: Catalog
  /** Files are not loaded: the receipts still read, but nothing can be added. */
  readOnly: boolean
  onAddFiles: () => void
}

export default function Files({ sessionId, catalog, readOnly, onAddFiles }: FilesProps) {
  // Combined views are listed under Links, not here: nobody uploaded them.
  const files = catalog.tables.filter((table) => !table.is_view)
  return (
    <div className="-mx-3">
      <ul>
        {files.map((table) => (
          <li key={table.name}>
            <FileRow sessionId={sessionId} table={table} />
          </li>
        ))}
      </ul>
      {!readOnly && (
        <div className="px-3 pt-5">
          <Button variant="primary" size="sm" onClick={onAddFiles}>
            Add files
          </Button>
        </div>
      )}
    </div>
  )
}
