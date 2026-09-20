// The primitives, every one in every state, at #/ui. Two jobs: it is how the other
// engineers learn the API without reading the source, and it is where the critic checks
// that nothing has drifted. Content is real Verity copy, so wording drift shows up too.

import { useState } from 'react'
import type { ReactNode } from 'react'
import {
  Badge,
  Banner,
  Button,
  Chip,
  Dialog,
  EmptyState,
  Figure,
  Popover,
  ProofList,
  RuledRow,
  Sheet,
  Skeleton,
  Tabs,
  Tick,
  WhatsThis,
} from './index'

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="border-t border-rule pt-6">
      <h2 className="type-title text-ink">{title}</h2>
      {note && <p className="mt-1 measure type-small text-ink-soft">{note}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

const SWATCHES: [string, string][] = [
  ['paper', 'bg-paper'],
  ['sheet', 'bg-sheet'],
  ['wash', 'bg-wash'],
  ['rule', 'bg-rule'],
  ['rule-strong', 'bg-rule-strong'],
  ['ink', 'bg-ink'],
  ['ink-soft', 'bg-ink-soft'],
  ['ink-faint', 'bg-ink-faint'],
  ['indigo', 'bg-indigo'],
  ['indigo-soft', 'bg-indigo-soft'],
  ['indigo-ink', 'bg-indigo-ink'],
  ['audit', 'bg-audit'],
  ['audit-soft', 'bg-audit-soft'],
  ['amber', 'bg-amber'],
  ['amber-soft', 'bg-amber-soft'],
  ['red', 'bg-red'],
  ['red-soft', 'bg-red-soft'],
  ['series-1', 'bg-series-1'],
  ['series-2', 'bg-series-2'],
  ['series-3', 'bg-series-3'],
  ['series-4', 'bg-series-4'],
  ['series-5', 'bg-series-5'],
]

const PROOF: ReactNode[] = [
  'Computed by a database from your files',
  'A second AI model wrote its own query and got the same result',
  'Used your agreed definition of gross pay',
  <>
    No rows or personal data were sent to the AI. <a href="#/ui">See exactly what was sent</a>
  </>,
]

export default function Gallery() {
  // Bumping this key remounts the animated pieces, so the one orchestrated moment can be
  // watched again without a page reload.
  const [take, setTake] = useState(0)
  const [tab, setTab] = useState('files')
  const [dialog, setDialog] = useState(false)
  const [loading, setLoading] = useState(false)
  const [picked, setPicked] = useState('Gross pay')

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6">
      <h1 className="type-headline text-ink">Primitives</h1>
      <p className="mt-2 measure type-body text-ink-soft">
        Every primitive in components/ui, in every state it has. Read README.md beside it for the props and the
        do/don&apos;t rules.
      </p>

      <div className="mt-10 space-y-10">
        <Section title="Colour" note="Use the names, never the hex: bg-paper, text-ink, border-rule. Charts read var(--color-series-1).">
          <ul className="grid grid-cols-2 gap-x-6 sm:grid-cols-3">
            {SWATCHES.map(([name, cls]) => (
              <li key={name} className="flex items-center gap-2.5 border-b border-rule py-2">
                <span className={`size-5 shrink-0 rounded-chip border border-rule ${cls}`} />
                <span className="type-small text-ink">{name}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Type" note="Seven roles. Mono is for SQL only — never a data label.">
          <div className="space-y-5">
            <div>
              <p className="type-figure text-ink">₹20.40 Cr</p>
              <p className="type-small text-ink-soft">type-figure, Plex Serif 48/52 semibold, tabular figures</p>
            </div>
            <div>
              <p className="type-headline text-ink">Ask your spreadsheets. Verify every answer.</p>
              <p className="type-small text-ink-soft">type-headline, Plex Serif 40/46 semibold, 28/34 on phones</p>
            </div>
            <div>
              <p className="type-statement text-ink">Engineering had the highest gross pay in 2025.</p>
              <p className="type-small text-ink-soft">type-statement, Plex Serif 22/30 medium</p>
            </div>
            <div>
              <p className="type-title text-ink">Files</p>
              <p className="type-small text-ink-soft">type-title, Plex Sans 15/22 semibold</p>
            </div>
            <div>
              <p className="measure type-body text-ink">
                Verity reads your files as they are, writes a query, and shows you the working. No row ever reaches the
                model.
              </p>
              <p className="type-small text-ink-soft">type-body, Plex Sans 15/24 regular</p>
            </div>
            <div>
              <p className="type-small text-ink-soft">93% of employees have pay records.</p>
              <p className="type-small text-ink-soft">type-small, Plex Sans 13/20 regular</p>
            </div>
            <div>
              <pre className="overflow-x-auto rounded-control bg-wash p-3 type-code text-ink">
                {'select department, sum(gross_pay) as gross\nfrom salary_register\nwhere year = 2025\ngroup by 1 order by 2 desc'}
              </pre>
              <p className="mt-1 type-small text-ink-soft">type-code, Plex Mono 13/20 regular</p>
            </div>
          </div>
        </Section>

        <Section title="Button" note="Three variants and two sizes. A loading button keeps its width, so nothing on the page moves.">
          <div className="space-y-3">
            {(['md', 'sm'] as const).map((size) => (
              <div key={size} className="flex flex-wrap items-center gap-3">
                <Button variant="primary" size={size}>
                  Ask
                </Button>
                <Button variant="secondary" size={size}>
                  Download CSV
                </Button>
                <Button variant="quiet" size={size}>
                  How I got this
                </Button>
                <Button variant="primary" size={size} loading>
                  Ask
                </Button>
                <Button variant="secondary" size={size} disabled>
                  Save to board
                </Button>
                <span className="type-small text-ink-soft">size {size}</span>
              </div>
            ))}
            <Button variant="primary" loading={loading} onClick={() => { setLoading(true); setTimeout(() => setLoading(false), 1600) }}>
              Try the loading state
            </Button>
          </div>
        </Section>

        <Section title="Tick, ProofList and Figure" note="The one orchestrated moment: ticks draw 90 ms apart, the double rule extends left to right.">
          <Button variant="secondary" size="sm" onClick={() => setTake((n) => n + 1)}>
            Play it again
          </Button>
          <div key={take} className="mt-4 grid gap-8 sm:grid-cols-2">
            <div className="space-y-4">
              <Figure value="₹20.40 Cr" caption="Gross pay, Engineering, 2025" animate />
              <Figure value="12.4%" caption="Attrition, FY25" />
              <Figure value="1,284" />
            </div>
            <div className="space-y-4">
              <ProofList items={PROOF} animate />
              <div className="flex items-center gap-3">
                <Tick />
                <Tick size={22} />
                <Tick size={28} title="Verified" />
                <span className="type-small text-ink-soft">Sizes 16, 22 and 28. The last one has a title, so it is read aloud.</span>
              </div>
            </div>
          </div>
        </Section>

        <Section title="Sheet and RuledRow" note="The answer statement is the only sheet in a thread. Lists are ruled rows, never cards.">
          <div className="grid gap-6 sm:grid-cols-2">
            <Sheet as="section" className="p-5">
              <p className="type-statement text-ink">Engineering had the highest gross pay in 2025.</p>
              <div className="mt-4">
                <Figure value="₹20.40 Cr" caption="Gross pay, 2025" />
              </div>
            </Sheet>
            <ul>
              {[
                ['Salary Register 2025', '14,208 rows, sheet Register'],
                ['Employees master', '1,284 rows'],
                ['Exits FY25', '96 rows'],
              ].map(([name, meta]) => (
                <RuledRow as="li" key={name} hover className="justify-between px-1">
                  <span className="type-body text-ink">{name}</span>
                  <span className="type-small text-ink-soft">{meta}</span>
                </RuledRow>
              ))}
            </ul>
          </div>
        </Section>

        <Section title="Tabs" note="Roving tabindex: one Tab stop, arrows move, Home and End jump.">
          <Tabs
            label="Your data"
            active={tab}
            onChange={setTab}
            tabs={[
              { id: 'files', label: 'Files (7)', buttonProps: { 'data-tour': 'files' } },
              { id: 'links', label: 'Links (5)' },
              { id: 'glossary', label: 'Glossary' },
            ]}
          >
            <p className="py-4 type-body text-ink-soft">
              {tab === 'files' && 'Seven tables read from five files. One needs a look.'}
              {tab === 'links' && 'employees ↔ salary register on employee code. 93% of employees have pay records.'}
              {tab === 'glossary' && '“Attrition” can be computed three ways. These are the definitions Verity uses.'}
            </p>
          </Tabs>
        </Section>

        <Section title="Dialog, Popover and What's this" note="The dialog is the native element, so Esc closes it and focus goes back to the button that opened it. Popovers open on click and on keyboard, never on hover alone.">
          <div className="flex flex-wrap items-center gap-4">
            <Button variant="secondary" onClick={() => setDialog(true)}>
              Open the dialog
            </Button>
            <Popover
              trigger="Why this number?"
              title="Where the figure comes from"
              className="rounded-control px-2 py-1 type-small text-indigo hover:bg-indigo-soft"
            >
              The database summed gross pay for every row dated in 2025 and grouped it by department. Engineering came
              first.
            </Popover>
            <span className="type-body text-ink">
              High confidence{' '}
              <WhatsThis
                title="What confidence means"
                body="Verity scores each answer on how cleanly it mapped your question to your columns. High means every term matched one column and a second model agreed."
              />
            </span>
            <span className="type-body text-ink">
              Near the right edge{' '}
              <WhatsThis
                align="right"
                title="Aligning a popover"
                body="Pass align='right' when the trigger sits near the right of the screen. The panel then lines up with its right edge instead of running off."
              />
            </span>
          </div>
          <Dialog
            open={dialog}
            onClose={() => setDialog(false)}
            title="Delete this project?"
            footer={
              <>
                <Button variant="secondary" onClick={() => setDialog(false)}>
                  Keep it
                </Button>
                <Button variant="primary" onClick={() => setDialog(false)}>
                  Delete the project
                </Button>
              </>
            }
          >
            <p className="measure">
              This removes “Salary Register 2025 and 5 more”, its 12 questions and its 3 saved answers from this
              browser. Your files are not stored on our server, so nothing else is deleted.
            </p>
          </Dialog>
        </Section>

        <Section title="Banner" note="What happened, then what to do. An error never apologises and never shows a status code.">
          <div className="space-y-3">
            <Banner tone="info">Same question, same data: answered from memory.</Banner>
            <Banner tone="warn" nextStep="Check that Exits FY25 has a header row, then add it again.">
              Two sheets in Exits FY25 had no readable header.
            </Banner>
            <Banner
              tone="error"
              nextStep="Re-attach them to ask new questions."
              action={
                <Button variant="primary" size="sm">
                  Re-attach files
                </Button>
              }
              onDismiss={() => undefined}
            >
              Your files are no longer loaded. We never keep them.
            </Banner>
          </div>
        </Section>

        <Section title="Chip and Badge" note="Chips are whole questions. Badges are confidence and nothing else.">
          <div className="flex flex-wrap gap-2">
            {['Gross pay', 'Net pay', 'Cost to company'].map((label) => (
              <Chip key={label} selected={picked === label} onClick={() => setPicked(label)}>
                {label}
              </Chip>
            ))}
            <Chip disabled>Not available yet</Chip>
          </div>
          <div className="mt-4 flex flex-wrap gap-6">
            <Badge level="high" />
            <Badge level="medium" />
            <Badge level="low" />
          </div>
        </Section>

        <Section title="Skeleton and EmptyState" note="A skeleton is decorative; the sentence beside it is what gets announced.">
          <div className="grid gap-8 sm:grid-cols-2">
            <div role="status" className="space-y-2">
              <Skeleton className="h-7 w-2/3" />
              <Skeleton className="h-5 w-1/2" />
              <Skeleton className="h-5 w-5/6" />
              <p className="type-small text-ink-soft">Reading your files…</p>
            </div>
            <EmptyState
              action={
                <Button variant="primary" size="sm">
                  Ask a question
                </Button>
              }
            >
              Save an answer to build a report you can print.
            </EmptyState>
          </div>
        </Section>

        <Section title="Focus" note="Tab through this page. Every control shows a 2px indigo ring, 2px clear of its edge.">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" size="sm">
              First
            </Button>
            <Chip>Second</Chip>
            <a href="#/ui">A link</a>
            <input
              aria-label="A text field"
              placeholder="A text field"
              className="h-9 rounded-control border border-rule bg-sheet px-3 type-body text-ink placeholder:text-ink-faint"
            />
          </div>
        </Section>
      </div>
    </div>
  )
}
