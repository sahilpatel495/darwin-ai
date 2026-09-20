// One uploaded table: where it came from, its size, and the Data Health receipt. The receipt is
// the proof that the mess in the export was handled on purpose, so warnings are counted in the
// collapsed summary: the analyst can see "2 to check" without opening anything.

import { AlertIcon, CheckIcon } from '../shell/icons'
import type { TableProfile } from '../../types'
import Expander from './Expander'
import { TYPE_NOUN, receiptLines } from './wording'

export default function FileCard({ table }: { table: TableProfile }) {
  const lines = receiptLines(table.health)
  const toCheck = lines.filter((line) => line.tone === 'warn').length

  return (
    <li className="rounded-card border border-line bg-surface p-3">
      <p className="truncate font-medium text-ink" title={table.source_file}>
        {table.source_file}
      </p>
      <p className="mt-0.5 text-sm break-words text-ink-soft">
        {table.sheet && <>Sheet {table.sheet}, </>}
        {table.row_count.toLocaleString('en-IN')} rows × {table.columns.length} columns
      </p>
      {/* The table name is what appears in links below and in the SQL under each answer. */}
      <p className="mt-0.5 mb-2 truncate text-xs text-ink-soft" title={table.name}>
        Table name <code className="font-mono text-ink">{table.name}</code>
      </p>

      <Expander
        label="Data Health receipt"
        aside={<span className={`text-xs ${toCheck ? 'text-warn' : 'text-good'}`}>{toCheck ? `${toCheck} to check` : 'All clear'}</span>}
      >
        <ul className="space-y-1.5 pt-1 pb-2">
          {lines.map((line, i) => (
            <li key={i} className="flex gap-2 text-sm leading-snug text-ink-soft">
              <span className={`mt-0.5 ${line.tone === 'warn' ? 'text-warn' : 'text-good'}`}>
                {line.tone === 'warn' ? <AlertIcon /> : <CheckIcon />}
              </span>
              <span className="min-w-0 break-words">
                {line.tone === 'warn' && <span className="sr-only">Check: </span>}
                {line.text}
              </span>
            </li>
          ))}
        </ul>
      </Expander>

      <Expander label="Columns">
        <ul className="space-y-1 pt-1 pb-1">
          {table.columns.map((column) => (
            <li key={column.name} className="flex items-baseline justify-between gap-2">
              <code className="min-w-0 truncate font-mono text-xs text-ink" title={column.label}>
                {column.name}
              </code>
              <span className="shrink-0 text-xs text-ink-soft">{column.pii ? 'personal data, hidden from the model' : TYPE_NOUN[column.type]}</span>
            </li>
          ))}
        </ul>
      </Expander>
    </li>
  )
}
