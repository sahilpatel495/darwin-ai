// The Files tab: one row per uploaded file, each opening to its Data Health receipt.
// The receipt is the proof that the mess in the export was handled on purpose, so it is itemised
// like a receipt — what was done on the left, how much of it right-aligned — and a file that needs
// a look says so on its closed row, before anyone opens anything.

import type { Catalog, TableProfile } from '../../types'
import { EXPLAIN } from '../education/explain'
import { Button, WhatsThis } from '../ui'
import Expander from './Expander'
import PreviewRows from './PreviewRows'
import type { ReceiptItem } from './wording'
import { TYPE_NOUN, needsALook, receiptLines } from './wording'

/** The amber mark. Never the only signal: the sentence beside it says the same thing in words. */
function Mark() {
  return <span aria-hidden className="mt-[6px] size-1.5 shrink-0 rounded-pill bg-amber" />
}

/** The receipt sits in an inset block: a till roll inside the row it belongs to, not a second card. */
function Receipt({ items }: { items: ReceiptItem[] }) {
  return (
    <ul className="mt-2 rounded-input bg-surface-2 px-3">
      {items.map((item, i) => (
        // Index keys: the receipt is rebuilt whole whenever the catalog changes and never reordered.
        <li key={i} className="border-b border-line-soft py-2 last:border-b-0">
          <div className="flex items-start justify-between gap-3">
            <span className="flex min-w-0 gap-1.5 type-small text-ink">
              {item.tone === 'warn' && <Mark />}
              <span className="min-w-0">
                {item.tone === 'warn' && <span className="sr-only">Needs a look: </span>}
                {item.label}
              </span>
            </span>
            {item.amount && <span className="shrink-0 type-small font-semibold tnum text-ink">{item.amount}</span>}
          </div>
          {item.note && <p className="mt-0.5 type-small text-ink-2">{item.note}</p>}
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
      className="border-b border-line-soft last:border-b-0"
      label={
        <>
          <span className="flex items-baseline justify-between gap-3">
            <span className="min-w-0 truncate type-body font-semibold text-ink" title={table.source_file}>
              {table.source_file}
            </span>
            <span className="shrink-0 type-small tnum text-ink-2">{table.row_count.toLocaleString('en-IN')} rows</span>
          </span>
          <span className="block type-small text-ink-2">
            {table.sheet && <>Sheet {table.sheet}, </>}
            {table.columns.length} columns
          </span>
          {look && (
            <span className="mt-1 flex gap-1.5">
              <Mark />
              <span className="type-small text-amber-ink">
                <span className="sr-only">Needs a look: </span>
                {look}
              </span>
            </span>
          )}
        </>
      }
    >
      {/* Indented to where the file's name starts (summary padding + chevron + gap), so the
          receipt reads as part of the row it opened rather than as the next row. */}
      <div className="pr-2 pb-3 pl-8">
        {/* The "?" sits at the right edge and opens leftwards: the panel is as wide as this
            column, so anywhere else it would be clipped by the sidebar's own scroller. */}
        <div className="flex items-center justify-between gap-2">
          <h3 className="type-small font-semibold text-ink">When we read this file</h3>
          <WhatsThis {...EXPLAIN.dataHealth} align="right" />
        </div>
        <Receipt items={items} />

        {/* Only with a live session: without one there are no rows on the server to show. */}
        {sessionId && (
          <div className="mt-3">
            <PreviewRows sessionId={sessionId} table={table} />
          </div>
        )}

        <Expander
          className="mt-2 border-t border-line-soft"
          summaryClassName="py-2"
          label={<span className="type-small font-semibold text-ink">Columns ({table.columns.length})</span>}
        >
          {/* Headers as they are written in the file. The SQL names matter only to someone reading
              the SQL under an answer, so they sit in a tooltip and a footnote. */}
          <ul className="pb-2">
            {table.columns.map((column) => (
              <li key={column.name} className="flex items-baseline justify-between gap-3 py-1">
                <span className="min-w-0 truncate type-small text-ink" title={`${column.label} (${column.name} in the SQL)`}>
                  {column.label}
                </span>
                <span className="shrink-0 type-small text-ink-2">{column.pii ? 'hidden from the AI' : TYPE_NOUN[column.type]}</span>
              </li>
            ))}
          </ul>
          <p className="pb-2 type-small break-words text-ink-2">
            In the SQL under each answer this file is called <code className="type-code text-ink">{table.name}</code>.
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
    <div className="-mx-2">
      <ul>
        {files.map((table) => (
          <li key={table.name}>
            <FileRow sessionId={sessionId} table={table} />
          </li>
        ))}
      </ul>
      {!readOnly && (
        <div className="px-2 pt-3">
          <Button size="sm" onClick={onAddFiles}>
            Add files
          </Button>
        </div>
      )}
    </div>
  )
}
