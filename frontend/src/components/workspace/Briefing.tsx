// The briefing: what an empty thread shows. Four things Verity did to the files, each checked and
// each opening to the real numbers behind it, then the two ways forward — the automatic overview,
// or the questions worth asking first.
//
// This is the product's strongest moment — the analyst has uploaded a mess and, before asking
// anything, is told what was found. So it sits at the top of the thread, not behind a link, and
// every number in it comes from the catalog rather than from a sentence someone wrote once.

import type { ReactNode } from 'react'
import { go, overviewPath, parseRoute, routeProjectId } from '../../lib/route'
import { labelOf, tableLabel } from '../../lib/tables'
import type { Catalog } from '../../types'
import Expander from '../sidebar/Expander'
import { count, linkLine, unionLine } from '../sidebar/wording'
import { Button, Card, Check, Chip } from '../ui'
import { groupQuestions } from './questions'

export interface BriefingProps {
  catalog: Catalog
  onAsk: (question: string) => void
  /** Opens the automatic dashboard (§13). Optional: the workspace may not wire it. */
  onOpenOverview?: () => void
}

function Row({ left, right }: { left: string; right: string }) {
  return (
    <li className="flex items-baseline justify-between gap-3 border-b border-line-soft py-1.5 last:border-b-0">
      <span className="min-w-0 type-small text-ink">{left}</span>
      <span className="shrink-0 type-small tnum text-ink-2">{right}</span>
    </li>
  )
}

function Sentences({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((sentence) => (
        <li key={sentence} className="measure type-small text-ink-2">
          {sentence}
        </li>
      ))}
    </ul>
  )
}

export default function Briefing({ catalog, onAsk, onOpenOverview }: BriefingProps) {
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
          <p className="mt-2 type-small text-ink-2">Every change made while reading a file is itemised under Files, counted line by line.</p>
        </>
      ),
    },
    {
      summary: links.length ? `Found ${count(links.length, 'link')} between your files` : 'Found no links between your files',
      detail: links.length ? (
        <Sentences items={links.map((link) => linkLine(link, name).sentence)} />
      ) : (
        <p className="measure type-small text-ink-2">No column in one file matched a column in another, so each question will use one file at a time.</p>
      ),
    },
    {
      summary: views.length ? `Combined ${count(combinedFiles, 'file')} that have the same columns` : 'No files needed combining',
      detail: views.length ? (
        <Sentences items={views.map((union) => unionLine(union, name).sentence)} />
      ) : (
        <p className="measure type-small text-ink-2">No two files hold the same kind of rows, so nothing was stacked into a combined view.</p>
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
          <p className="measure mt-2 type-small text-ink-2">
            The AI is told column names, types and counts. It is never sent a row, whatever the rows contain.
          </p>
        </>
      ),
    },
  ]

  const groups = groupQuestions(catalog)
  // The workspace may not pass a handler; the project this briefing is about is in the hash either
  // way, so the one primary action on the screen is never a button that does nothing.
  // `typeof` guard: this file is drawn to HTML in Node by the render tests, where there is no location.
  const here = typeof location === 'undefined' ? null : routeProjectId(parseRoute(location.hash))
  const openOverview = onOpenOverview ?? (here ? () => go(overviewPath(here)) : null)

  return (
    <Card as="section" hero aria-labelledby="briefing-title">
      <h2 id="briefing-title" className="type-card text-ink">
        Here’s what I found in your files
      </h2>
      <p className="mt-1 type-small text-ink-2">Counted while your files were read. No AI was involved in any of it.</p>

      <ul className="mt-4 -mx-2">
        {lines.map((line) => (
          // Check first, chevron last: the check is the claim, and a row that opens with two
          // markers reads as a control before it reads as a statement.
          <li key={line.summary}>
            <Expander
              chevronAtEnd
              className="border-b border-line-soft last:border-b-0"
              label={
                <span className="flex gap-2.5">
                  <Check className="mt-0.5" />
                  <span className="type-body text-ink">{line.summary}</span>
                </span>
              }
            >
              {/* Indented to where the sentence starts (summary padding + check + gap). */}
              <div className="pr-2 pb-3 pl-9">{line.detail}</div>
            </Expander>
          </li>
        ))}
      </ul>

      {openOverview && (
        <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line-soft pt-5">
          <Button variant="primary" onClick={openOverview}>
            See the full overview
          </Button>
          <p className="min-w-0 type-small text-ink-2">Headline numbers, charts and data quality, computed from your files with no AI.</p>
        </div>
      )}

      {groups.length > 0 && (
        <div className="mt-6">
          <h3 className="type-section text-ink">Questions to start with</h3>
          <div className="mt-3 space-y-3">
            {groups.map((group) => (
              <div key={group.kind}>
                <p className="type-small font-semibold text-ink-2">{group.title}</p>
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
          looking when they need them. The thread owns them; this card said the same thing twice. */}
    </Card>
  )
}
