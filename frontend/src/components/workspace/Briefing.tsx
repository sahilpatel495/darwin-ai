// The briefing: what an empty thread shows. Four things Verity did to the files, each ticked and
// each opening to the real numbers behind it, then the questions worth asking first.
//
// This is the product's strongest moment — the analyst has uploaded a mess and, before asking
// anything, is told what was found. So it sits at the top of the thread, not behind a link, and
// every number in it comes from the catalog rather than from a sentence someone wrote once.

import type { ReactNode } from 'react'
import { labelOf, tableLabel } from '../../lib/tables'
import type { Catalog } from '../../types'
import Expander from '../sidebar/Expander'
import { count, linkLine, unionLine } from '../sidebar/wording'
import { Chip, Sheet, Tick } from '../ui'
import { groupQuestions } from './questions'

export interface BriefingProps {
  catalog: Catalog
  onAsk: (question: string) => void
}

function Row({ left, right }: { left: string; right: string }) {
  return (
    <li className="flex items-baseline justify-between gap-3 border-b border-rule py-1.5 last:border-b-0">
      <span className="min-w-0 type-small text-ink">{left}</span>
      <span className="shrink-0 type-small tabular-nums text-ink-soft">{right}</span>
    </li>
  )
}

function Sentences({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((sentence) => (
        <li key={sentence} className="measure type-small text-ink-soft">
          {sentence}
        </li>
      ))}
    </ul>
  )
}

export default function Briefing({ catalog, onAsk }: BriefingProps) {
  const name = (table: string) => labelOf(table, catalog.tables)
  const files = catalog.tables.filter((table) => !table.is_view)
  const links = catalog.relationships.filter((link) => link.status !== 'rejected')
  const views = catalog.unions.filter((union) => union.status !== 'rejected')
  const combinedFiles = new Set(views.flatMap((union) => union.tables)).size

  // Personal data is reported per file, by the header the analyst wrote, not the cleaned name.
  const hidden = files
    .map((table) => ({
      file: tableLabel(table, catalog.tables),
      columns: table.health.pii_columns.map((pii) => table.columns.find((column) => column.name === pii)?.label ?? pii),
    }))
    .filter((entry) => entry.columns.length > 0)
  const hiddenCount = hidden.reduce((total, entry) => total + entry.columns.length, 0)

  const lines: { summary: string; detail: ReactNode }[] = [
    {
      summary: `Read and cleaned ${count(files.length, 'file')}`,
      detail: (
        <>
          <ul>
            {files.map((table) => (
              <Row key={table.name} left={tableLabel(table, catalog.tables)} right={`${table.row_count.toLocaleString('en-IN')} rows`} />
            ))}
          </ul>
          <p className="mt-2 type-small text-ink-soft">Every change made while reading a file is itemised under Files, counted line by line.</p>
        </>
      ),
    },
    {
      summary: links.length ? `Found ${count(links.length, 'link')} between your files` : 'Found no links between your files',
      detail: links.length ? (
        <Sentences items={links.map((link) => linkLine(link, name).sentence)} />
      ) : (
        <p className="measure type-small text-ink-soft">No column in one file matched a column in another, so each question will use one file at a time.</p>
      ),
    },
    {
      summary: views.length ? `Combined ${count(combinedFiles, 'file')} that have the same columns` : 'No files needed combining',
      detail: views.length ? (
        <Sentences items={views.map((union) => unionLine(union, name).sentence)} />
      ) : (
        <p className="measure type-small text-ink-soft">No two files hold the same kind of rows, so nothing was stacked into a combined view.</p>
      ),
    },
    {
      summary: hiddenCount ? `Hid ${count(hiddenCount, 'personal-data column')} from the AI` : 'Found no personal data to hide',
      detail: (
        <>
          {hidden.length > 0 && (
            <ul>
              {hidden.map((entry) => (
                <Row key={entry.file} left={entry.file} right={entry.columns.join(', ')} />
              ))}
            </ul>
          )}
          <p className="measure mt-2 type-small text-ink-soft">
            The AI is told column names, types and counts. It is never sent a row, whatever the rows contain.
          </p>
        </>
      ),
    },
  ]

  const groups = groupQuestions(catalog)

  return (
    <Sheet as="section" aria-labelledby="briefing-title" className="p-5 sm:p-6">
      <h2 id="briefing-title" className="type-statement text-ink">
        Here’s what I found in your files
      </h2>

      <div className="mt-3">
        {lines.map((line) => (
          <Expander
            key={line.summary}
            className="border-b border-rule"
            label={
              <span className="flex gap-2">
                <Tick className="mt-1" />
                <span className="type-body text-ink">{line.summary}</span>
              </span>
            }
          >
            <div className="pb-3 pl-[18px]">{line.detail}</div>
          </Expander>
        ))}
      </div>

      {groups.length > 0 && (
        <div className="mt-6">
          <h3 className="type-title text-ink">Questions to start with</h3>
          <div className="mt-2 space-y-3">
            {groups.map((group) => (
              <div key={group.kind}>
                <p className="type-small text-ink-soft">{group.title}</p>
                <div className="mt-1.5 flex flex-wrap gap-2">
                  {group.questions.map((question) => (
                    <Chip key={question} onClick={() => onAsk(question)}>
                      {question}
                    </Chip>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* §6.7's three examples of a good question live under the composer, where the analyst is
          looking when they need them. The thread owns them; this sheet said the same thing twice. */}
    </Sheet>
  )
}
