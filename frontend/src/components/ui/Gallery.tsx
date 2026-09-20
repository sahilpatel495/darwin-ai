// The primitives, every one in every state, at #/ui. Two jobs: it is how the other engineers
// learn the API without reading the source, and it is where the critic checks that nothing has
// drifted. Content is real Verity copy, so wording drift shows up too.
//
// Everything below renders twice, side by side, in a light frame and a dark one: a nested
// [data-theme] re-declares every colour token for its subtree, so both themes are on screen at
// once and a contrast mistake cannot hide until someone happens to switch.

import { useState } from 'react'
import type { ReactNode } from 'react'
import {
  Badge,
  Banner,
  Button,
  Card,
  Check,
  Chip,
  Dialog,
  EmptyState,
  IconButton,
  ListRow,
  Menu,
  NavItem,
  Popover,
  ProgressSteps,
  SegmentedControl,
  Skeleton,
  StatTile,
  Tabs,
  ThemeToggle,
  Tooltip,
  VerifiedList,
  WhatsThis,
  toast,
} from './index'
import type { ProgressStep } from './index'
import { AnalysesIcon, AskIcon, CloseIcon, HomeIcon, MoreIcon, OverviewIcon, SavedIcon, TrustIcon } from './icons'

const SWATCHES: [string, string][] = [
  ['wash', 'bg-wash'],
  ['surface', 'bg-surface'],
  ['surface-2', 'bg-surface-2'],
  ['fill', 'bg-fill'],
  ['fill-hover', 'bg-fill-hover'],
  ['line', 'bg-line'],
  ['line-soft', 'bg-line-soft'],
  ['ink', 'bg-ink'],
  ['ink-2', 'bg-ink-2'],
  ['ink-3', 'bg-ink-3'],
  ['blue', 'bg-blue'],
  ['blue-hover', 'bg-blue-hover'],
  ['blue-soft', 'bg-blue-soft'],
  ['blue-ink', 'bg-blue-ink'],
  ['green', 'bg-green'],
  ['green-soft', 'bg-green-soft'],
  ['green-ink', 'bg-green-ink'],
  ['amber', 'bg-amber'],
  ['amber-soft', 'bg-amber-soft'],
  ['amber-ink', 'bg-amber-ink'],
  ['red', 'bg-red'],
  ['red-soft', 'bg-red-soft'],
  ['red-ink', 'bg-red-ink'],
  ['series-1', 'bg-series-1'],
  ['series-2', 'bg-series-2'],
  ['series-3', 'bg-series-3'],
  ['series-4', 'bg-series-4'],
  ['series-5', 'bg-series-5'],
  ['series-6', 'bg-series-6'],
  ['series-7', 'bg-series-7'],
]

const VERIFIED: ReactNode[] = [
  'Computed by a database from your files',
  'A second AI model wrote its own query and got the same result',
  'Used your agreed definition of gross pay',
  <>
    No rows or personal data were sent to the AI. <a href="#/ui">See exactly what was sent</a>
  </>,
]

const STEPS: ProgressStep[] = [
  { id: 'u', label: 'Understanding the question', detail: 'Gross pay, by department, 2025', state: 'done' },
  { id: 'g', label: 'Writing the query', state: 'done', meta: 'llama-3.3-70b' },
  { id: 's', label: 'Checking the query is safe', detail: 'Read-only, 2 tables, 3 columns', state: 'done' },
  { id: 'r', label: 'Running it on your data', detail: '14,208 rows read, 9 groups out', state: 'active' },
  { id: 'v', label: 'Double-checking with a second AI model', detail: 'All the free AI models are busy. Trying again in 12 s.', state: 'waiting' },
  { id: 'f', label: 'Fixing the query', detail: 'A column name did not match; rewritten once', state: 'warn' },
  { id: 'x', label: 'Choosing a chart', state: 'failed', detail: 'The result has no measurable column' },
  { id: 'n', label: 'Writing the answer', state: 'pending' },
]

const NAV = [
  { id: 'home', label: 'Home', href: '#/ui', icon: <HomeIcon /> },
  { id: 'ask', label: 'Ask', href: '#/ui', icon: <AskIcon /> },
  { id: 'overview', label: 'Overview', href: '#/ui', icon: <OverviewIcon /> },
  { id: 'analyses', label: 'Analyses', href: '#/ui', icon: <AnalysesIcon />, disabled: true, disabledReason: 'Open a project first' },
  { id: 'saved', label: 'Saved', href: '#/ui', icon: <SavedIcon /> },
  { id: 'trust', label: 'Trust', href: '#/ui', icon: <TrustIcon /> },
]

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="type-section text-ink">{title}</h2>
      {note && <p className="mt-0.5 measure type-small text-ink-2">{note}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

/** Everything in the gallery, rendered once per theme frame. */
function Primitives({ suffix }: { suffix: string }) {
  const [take, setTake] = useState(0)
  const [tab, setTab] = useState('files')
  const [dialog, setDialog] = useState(false)
  const [loading, setLoading] = useState(false)
  const [picked, setPicked] = useState('Gross pay')
  const [chart, setChart] = useState('bar')
  const [view, setView] = useState('chart')

  return (
    <div className="space-y-8 bg-wash p-4 sm:p-6">
      <Section title="Colour" note="Use the names, never the hex: bg-wash, text-ink-2, border-line. Charts read var(--color-series-1).">
        <ul className="grid grid-cols-2 gap-x-4 sm:grid-cols-3">
          {SWATCHES.map(([name, cls]) => (
            <li key={name} className="flex items-center gap-2.5 py-1">
              <span className={`size-5 shrink-0 rounded-input ring-1 ring-line ${cls}`} />
              <span className="type-small text-ink">{name}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Type" note="Seven roles, system faces. Mono is for SQL only — never a data label.">
        <Card className="space-y-4">
          <div>
            <p className="type-hero text-ink">₹20.40 Cr</p>
            <p className="type-small text-ink-2">type-hero · 40/44 bold, tabular figures</p>
          </div>
          <div>
            <p className="type-page text-ink">Ask your spreadsheets. Verify every answer.</p>
            <p className="type-small text-ink-2">type-page · 28/34 bold (22/28 on phones)</p>
          </div>
          <div>
            <p className="type-card text-ink">Engineering had the highest gross pay in 2025.</p>
            <p className="type-small text-ink-2">type-card · 20/26 bold</p>
          </div>
          <div>
            <p className="type-section text-ink">Files</p>
            <p className="type-small text-ink-2">type-section · 17/22 semibold</p>
          </div>
          <div>
            <p className="measure type-body text-ink">
              Verity reads your files as they are, writes a query, and shows you the working. No row ever reaches the model.
            </p>
            <p className="type-small text-ink-2">type-body · 15/22 regular</p>
          </div>
          <div>
            <p className="type-small text-ink">93% of employees have pay records.</p>
            <p className="type-small text-ink-2">type-small · 13/18 regular</p>
          </div>
          <div>
            <p className="type-micro text-ink">Gross pay · 2025</p>
            <p className="type-small text-ink-2">type-micro · 12/16 medium — chips, badges, axis labels</p>
          </div>
          <div>
            <pre className="overflow-x-auto rounded-input bg-surface-2 p-3 type-code text-ink">
              {'select department, sum(gross_pay) as gross\nfrom salary_register\nwhere year = 2025\ngroup by 1 order by 2 desc'}
            </pre>
            <p className="mt-1 type-small text-ink-2">type-code · 13/20 mono</p>
          </div>
        </Card>
      </Section>

      <Section title="Button and IconButton" note="Three variants, two sizes. A loading button keeps its width, so nothing on the page moves.">
        <Card className="space-y-3">
          {(['md', 'sm'] as const).map((size) => (
            <div key={size} className="flex flex-wrap items-center gap-3">
              <Button variant="primary" size={size}>
                Ask
              </Button>
              <Button variant="secondary" size={size}>
                Download CSV
              </Button>
              <Button variant="ghost" size={size}>
                How I got this
              </Button>
              <Button variant="primary" size={size} pill>
                New project
              </Button>
              <Button variant="primary" size={size} loading>
                Ask
              </Button>
              <Button variant="secondary" size={size} disabled>
                Save to board
              </Button>
              <span className="type-small text-ink-2">size {size}</span>
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-3">
            <IconButton label="More actions">
              <MoreIcon size={18} />
            </IconButton>
            <IconButton label="Close" variant="ghost">
              <CloseIcon size={18} />
            </IconButton>
            <IconButton label="More actions" size="sm">
              <MoreIcon size={16} />
            </IconButton>
            <IconButton label="Not available yet" disabled>
              <MoreIcon size={18} />
            </IconButton>
            <Tooltip label="A tooltip, on hover and on focus">
              <span className="type-small text-ink-2">Hover or tab to any of these</span>
            </Tooltip>
          </div>
          <Button
            variant="primary"
            loading={loading}
            onClick={() => {
              setLoading(true)
              setTimeout(() => {
                setLoading(false)
                toast('Saved to board')
              }, 1200)
            }}
          >
            Try the loading state
          </Button>
        </Card>
      </Section>

      <Section title="Card and ListRow" note="Only an interactive card lifts on hover. A card that is just a container never moves.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Card as="section" interactive>
            <p className="type-card text-ink">Sample HR company</p>
            <p className="mt-1 type-small text-ink-2">5 files · 12 questions, 3 saved · Opened 2 hours ago</p>
          </Card>
          <Card flush>
            <ul>
              {[
                ['Salary Register 2025', '14,208 rows'],
                ['Employees master', '1,284 rows'],
                ['Exits FY25', '96 rows'],
              ].map(([name, meta]) => (
                <ListRow as="li" key={name} hover className="justify-between">
                  <span className="type-body text-ink">{name}</span>
                  <span className="type-small text-ink-2">{meta}</span>
                </ListRow>
              ))}
            </ul>
          </Card>
        </div>
      </Section>

      <Section title="Check, VerifiedList and StatTile" note="The answer's arrival: the figure counts up, then the checks pop in 90 ms apart.">
        <Button variant="secondary" size="sm" onClick={() => setTake((n) => n + 1)}>
          Play it again
        </Button>
        <div key={take} className="mt-3 grid gap-4 sm:grid-cols-2">
          <Card className="space-y-5">
            <StatTile value="₹20.40 Cr" label="Gross pay, Engineering, 2025" animate delta={{ text: '4.2% on 2024', direction: 'up', good: true }} />
            <StatTile value="12.4%" label="Attrition, FY25" delta={{ text: '1.8 points', direction: 'up', good: false }} />
            <StatTile value="1,284" label="People on the payroll" delta={{ text: 'No change', direction: 'flat' }} />
          </Card>
          <Card className="space-y-4">
            <VerifiedList items={VERIFIED} animate />
            <div className="flex items-center gap-3">
              <Check />
              <Check size={22} />
              <Check size={28} title="Verified" />
              <span className="type-small text-ink-2">Sizes 18, 22 and 28. The last is named, so it is read aloud.</span>
            </div>
          </Card>
        </div>
      </Section>

      <Section title="ProgressSteps" note="Thinking, made visible (§11). Six states: pending, active, done, warn, failed, waiting.">
        <Card>
          <ProgressSteps steps={STEPS} />
        </Card>
      </Section>

      <Section title="Tabs and SegmentedControl" note="Both slide: one Tab stop, arrows move, Home and End jump.">
        <Card className="space-y-5">
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
            <p className="py-3 type-body text-ink-2">
              {tab === 'files' && 'Seven tables read from five files. One needs a look.'}
              {tab === 'links' && 'employees ↔ salary register on employee code. 93% of employees have pay records.'}
              {tab === 'glossary' && '“Attrition” can be computed three ways. These are the definitions Verity uses.'}
            </p>
          </Tabs>
          <div className="flex flex-wrap items-center gap-4">
            <SegmentedControl
              label="Chart type"
              value={chart}
              onChange={setChart}
              options={[
                { value: 'bar', label: 'Bar' },
                { value: 'donut', label: 'Donut' },
                { value: 'line', label: 'Line' },
              ]}
            />
            <SegmentedControl
              label="Chart or table"
              size="sm"
              value={view}
              onChange={setView}
              options={[
                { value: 'chart', label: 'Chart' },
                { value: 'table', label: 'Table' },
              ]}
            />
            <ThemeToggle variant="full" />
          </div>
        </Card>
      </Section>

      <Section title="Dialog, Menu, Popover and What's this" note="The dialog is the native element, so Esc closes it and focus goes back. Popovers open on click and on keyboard, never on hover alone.">
        <Card className="flex flex-wrap items-center gap-4">
          <Button variant="secondary" onClick={() => setDialog(true)}>
            Open the dialog
          </Button>
          <Menu
            trigger={<MoreIcon size={18} />}
            triggerLabel="Actions for this tile"
            className="press inline-flex size-9 items-center justify-center rounded-pill bg-fill text-ink hover:bg-fill-hover"
            actions={[
              { id: 'ask', label: 'Ask about this', onSelect: () => toast('Sent to Ask') },
              { id: 'save', label: 'Save to board', onSelect: () => toast('Saved to board') },
              { id: 'sql', label: 'View table and SQL', onSelect: () => setDialog(true) },
              { id: 'csv', label: 'Download CSV', onSelect: () => toast('Nothing to download here', 'error'), disabled: false },
            ]}
          />
          <Popover trigger="Why this number?" title="Where the figure comes from" className="press rounded-input px-2 py-1 type-small font-semibold text-blue hover:bg-blue-soft">
            The database summed gross pay for every row dated in 2025 and grouped it by department. Engineering came first.
          </Popover>
          <span className="type-body text-ink">
            High confidence{' '}
            <WhatsThis
              title="What confidence means"
              body="Verity scores each answer on how cleanly it mapped your question to your columns. High means every term matched one column and a second model agreed."
            />
          </span>
        </Card>
        <Dialog
          open={dialog}
          onClose={() => setDialog(false)}
          title="Delete this project?"
          description="Deleting is immediate and cannot be undone."
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
            This removes “Salary Register 2025 and 5 more”, its 12 questions and its 3 saved answers from this browser. Your files are not stored on our
            server, so nothing else is deleted.
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

      <Section title="Chip and Badge" note="Chips are whole questions, or a computed insight when static. Badges are confidence and nothing else.">
        <Card className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {['Gross pay', 'Net pay', 'Cost to company'].map((label) => (
              <Chip key={label} selected={picked === label} onClick={() => setPicked(label)}>
                {label}
              </Chip>
            ))}
            <Chip disabled>Not available yet</Chip>
          </div>
          <div className="flex flex-wrap gap-2">
            <Chip static>Engineering is 34% of the total</Chip>
            <Chip static>Top 3 departments hold 71%</Chip>
          </div>
          <div className="flex flex-wrap gap-3">
            <Badge level="high" />
            <Badge level="medium" />
            <Badge level="low" />
          </div>
        </Card>
      </Section>

      <Section title="Skeleton and EmptyState" note="A skeleton is decorative; the sentence beside it is what gets announced.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Card role="status" className="space-y-2">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-5 w-1/2" />
            <Skeleton className="h-5 w-5/6" />
            <p className="type-small text-ink-2">Reading your files…</p>
          </Card>
          <EmptyState
            title="No saved answers yet"
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

      <Section title="NavItem" note="The rail itself is fixed to the window, so its items are shown here on their own: active, resting, and disabled outside a project.">
        <Card flush className="flex h-56 overflow-hidden">
          {/* NavRail positions itself against the window; only its items belong in a gallery card. */}
          <ul className="flex w-[72px] shrink-0 flex-col gap-1 border-r border-line-soft px-2 py-3">
            {NAV.slice(0, 4).map((item) => (
              <NavItem key={item.id} {...item} active={item.id === 'ask'} />
            ))}
          </ul>
          <div className="flex-1 p-4 type-small text-ink-2">The page sits here. Analyses is disabled, so it says why on hover.</div>
        </Card>
      </Section>

      <Section title="Focus" note={`Tab through this ${suffix} frame. Every control shows a 2px blue ring, 2px clear of its edge.`}>
        <Card className="flex flex-wrap items-center gap-3">
          <Button variant="primary" size="sm">
            First
          </Button>
          <Chip>Second</Chip>
          <a href="#/ui">A link</a>
          <input
            aria-label="A text field"
            placeholder="A text field"
            className="h-9 rounded-input bg-surface-2 px-3 type-body text-ink placeholder:text-ink-3"
          />
        </Card>
      </Section>
    </div>
  )
}

export default function Gallery() {
  return (
    <div className="min-h-full bg-wash">
      <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
        <h1 className="type-page text-ink">Primitives</h1>
        <p className="mt-1 measure type-body text-ink-2">
          Every primitive in components/ui, in every state it has, in both themes. Read README.md beside it for the props and the do/don&apos;t rules.
        </p>
      </div>
      <div className="grid grid-cols-1 items-start gap-px bg-line lg:grid-cols-2">
        <div data-theme="light" className="bg-wash">
          <p className="bg-surface px-4 py-2 type-micro text-ink-2 sm:px-6">Light</p>
          <Primitives suffix="light" />
        </div>
        <div data-theme="dark" className="bg-wash">
          <p className="bg-surface px-4 py-2 type-micro text-ink-2 sm:px-6">Dark</p>
          <Primitives suffix="dark" />
        </div>
      </div>
    </div>
  )
}
