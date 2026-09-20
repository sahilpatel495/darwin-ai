// "Here's what I found in your files": four checked lines, each opening to the real numbers behind
// it. It is the last thing onboarding shows (§7, step 3) and it stays one tap away at the top of
// the Data drawer, because it is the only place that says — before a single question is asked —
// what was done to the files and what was kept away from the AI.
//
// Every number comes from the catalog. Nothing here is a sentence someone wrote once.

import type { ReactNode } from 'react'
import { labelOf, tableLabel } from '../../lib/tables'
import type { Catalog } from '../../types'
import Expander from '../sidebar/Expander'
import { count, linkLine, unionLine } from '../sidebar/wording'
import { VerifiedList, cx } from '../ui'

export interface ReadyStateProps {
  catalog: Catalog
  /** The title above the lines. Pass `null` where the caller has already written one. */
  heading?: ReactNode
  /** Pop the checks in one after another, for onboarding's reveal. */
  animate?: boolean
  className?: string
}

/** One fact inside an opened line: what it is about on the left, its count on the right. */
function Row({ left, right }: { left: string; right: string }) {
  return (
    <li className="flex items-baseline justify-between gap-3 border-b border-hairline-soft py-2 last:border-b-0">
      <span className="min-w-0 text-body-sm text-ink">{left}</span>
      <span className="shrink-0 text-body-sm tnum text-steel">{right}</span>
    </li>
  )
}

function Sentences({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2">
      {items.map((sentence) => (
        <li key={sentence} className="measure text-body-sm text-slate">
          {sentence}
        </li>
      ))}
    </ul>
  )
}

export default function ReadyState({ catalog, heading = 'Here’s what I found in your files', animate = false, className }: ReadyStateProps) {
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
          <p className="mt-3 text-body-sm text-slate">Every change made while reading a file is itemised under Files, counted line by line.</p>
        </>
      ),
    },
    {
      summary: links.length ? `Found ${count(links.length, 'link')} between your files` : 'Found no links between your files',
      detail: links.length ? (
        <Sentences items={links.map((link) => linkLine(link, name).sentence)} />
      ) : (
        <p className="measure text-body-sm text-slate">No column in one file matched a column in another, so each question will use one file at a time.</p>
      ),
    },
    {
      summary: views.length ? `Combined ${count(combinedFiles, 'file')} that have the same columns` : 'No files needed combining',
      detail: views.length ? (
        <Sentences items={views.map((union) => unionLine(union, name).sentence)} />
      ) : (
        <p className="measure text-body-sm text-slate">No two files hold the same kind of rows, so nothing was stacked into a combined view.</p>
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
          <p className="measure mt-3 text-body-sm text-slate">
            The AI is told column names, types and counts. It is never sent a row, whatever the rows contain.
          </p>
        </>
      ),
    },
  ]

  return (
    <section className={cx('text-ink', className)}>
      {heading && <h2 className="text-heading-sm text-ink-deep">{heading}</h2>}
      <p className={cx('text-body-sm text-slate', heading ? 'mt-2' : '')}>Counted while your files were read. No AI was involved in any of it.</p>

      {/* The check is the claim and the chevron is the offer, so the claim comes first and the
          chevron sits at the far edge. `flex-1` on the line lets it get there: VerifiedList sizes
          its content span to the sentence, which would leave four chevrons in a ragged column. */}
      <VerifiedList
        className="mt-4 [&>li>span:last-child]:flex-1"
        animate={animate}
        items={lines.map((line) => (
          <Expander
            key={line.summary}
            chevronAtEnd
            // No padding of its own: the check beside it is aligned to a bare line of body text,
            // and the rows are spaced by the list instead.
            summaryClassName="px-0 py-0 hover:bg-transparent"
            label={<span className="text-body-md text-ink">{line.summary}</span>}
          >
            <div className="pt-1 pb-3">{line.detail}</div>
          </Expander>
        ))}
      />
    </section>
  )
}
