// The design system's own page, at `#/ui`. Every token, type role, glyph and primitive in every
// state, on one scroll, so a disagreement about what a Button looks like is settled by opening a
// URL rather than by reading two files.
//
// It is not a product screen: no top bar, no project, no chrome. Just the parts.

import { useState } from 'react'
import { AppPreview, AuroraBackdrop, Glyph } from '../graphics'
import type { GlyphName } from '../graphics/Glyph'
import {
  Accordion,
  Avatar,
  Badge,
  Banner,
  Button,
  Card,
  Check,
  Chip,
  Dialog,
  Drawer,
  EmptyState,
  IconButton,
  Input,
  Kbd,
  Menu,
  PillTabs,
  Popover,
  ProgressRing,
  ProgressSteps,
  Select,
  Skeleton,
  StatTile,
  Textarea,
  Tip,
  toast,
  Toaster,
  Tooltip,
  UsageMeter,
  VerifiedList,
  WhatsThis,
  cx,
} from './index'
import { CloseIcon, MoreIcon, SearchIcon } from './icons'

/* --- The page's own furniture -------------------------------------------- */

function Section({ id, title, note, children }: { id: string; title: string; note?: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 border-t border-hairline-soft py-16 first:border-t-0 first:pt-0">
      <h2 className="text-heading-md text-ink-deep">{title}</h2>
      {note && <p className="mt-2 measure text-body-md text-slate">{note}</p>}
      <div className="mt-8">{children}</div>
    </section>
  )
}

/** A labelled specimen. The label is below the thing, so the eye meets the thing first. */
function Slot({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cx('min-w-0', className)}>
      <div className="flex min-h-14 flex-wrap items-center gap-3">{children}</div>
      <p className="mt-2 text-caption text-steel">{label}</p>
    </div>
  )
}

const Row = ({ children }: { children: React.ReactNode }) => (
  <div className="flex flex-wrap items-start gap-x-8 gap-y-6">{children}</div>
)

/* --- Data for the specimens ---------------------------------------------- */

const COLOURS: { group: string; swatches: { name: string; className: string; onDark?: boolean }[] }[] = [
  {
    group: 'Surfaces and lines',
    swatches: [
      { name: 'canvas', className: 'bg-canvas' },
      { name: 'surface-soft', className: 'bg-surface-soft' },
      { name: 'hairline', className: 'bg-hairline' },
      { name: 'hairline-soft', className: 'bg-hairline-soft' },
    ],
  },
  {
    group: 'Ink',
    swatches: [
      { name: 'ink-deep', className: 'bg-ink-deep', onDark: true },
      { name: 'ink', className: 'bg-ink', onDark: true },
      { name: 'charcoal', className: 'bg-charcoal', onDark: true },
      { name: 'slate', className: 'bg-slate', onDark: true },
      { name: 'steel', className: 'bg-steel', onDark: true },
      { name: 'stone', className: 'bg-stone' },
    ],
  },
  {
    group: 'Action and accent',
    swatches: [
      { name: 'primary', className: 'bg-primary', onDark: true },
      { name: 'primary-deep', className: 'bg-primary-deep', onDark: true },
      { name: 'primary-soft', className: 'bg-primary-soft' },
      { name: 'purple', className: 'bg-purple', onDark: true },
    ],
  },
  {
    group: 'Meaning',
    swatches: [
      { name: 'success', className: 'bg-success', onDark: true },
      { name: 'success-soft', className: 'bg-success-soft' },
      { name: 'attention', className: 'bg-attention', onDark: true },
      { name: 'attention-soft', className: 'bg-attention-soft' },
      { name: 'warning', className: 'bg-warning' },
      { name: 'critical', className: 'bg-critical', onDark: true },
      { name: 'critical-soft', className: 'bg-critical-soft' },
    ],
  },
  {
    group: 'Chart series, in order',
    swatches: [
      { name: 'chart-1', className: 'bg-chart-1', onDark: true },
      { name: 'chart-2', className: 'bg-chart-2', onDark: true },
      { name: 'chart-3', className: 'bg-chart-3', onDark: true },
      { name: 'chart-4', className: 'bg-chart-4', onDark: true },
      { name: 'chart-5', className: 'bg-chart-5', onDark: true },
      { name: 'chart-6', className: 'bg-chart-6', onDark: true },
    ],
  },
]

const TYPE_ROLES: { role: string; use: string }[] = [
  { role: 'text-hero-display', use: 'The landing hero, and nothing else' },
  { role: 'text-display-lg', use: 'Section openers, the Ask greeting' },
  { role: 'text-heading-lg', use: 'Page titles, hero figures' },
  { role: 'text-heading-md', use: 'Editorial subheads — the light weight is the rhythm' },
  { role: 'text-heading-sm', use: 'Card titles, the answer headline' },
  { role: 'text-subtitle-lg', use: 'Callouts, FAQ questions' },
  { role: 'text-subtitle-md', use: 'Lead paragraphs' },
  { role: 'text-body-md', use: 'Body' },
  { role: 'text-body-sm', use: 'Secondary text, pill tabs, buttons' },
  { role: 'text-caption', use: 'Badges, axis labels, fine print' },
]

const RADII = [
  { name: 'lg', px: 8, className: 'rounded-lg', use: 'Inputs' },
  { name: 'xl', px: 16, className: 'rounded-xl', use: 'Small tiles' },
  { name: 'xxl', px: 24, className: 'rounded-xxl', use: 'Standard cards' },
  { name: 'xxxl', px: 32, className: 'rounded-xxxl', use: 'Hero frames' },
  { name: 'feature', px: 40, className: 'rounded-feature', use: 'Showcase' },
  { name: 'full', px: 100, className: 'rounded-full', use: 'Every button' },
]

const GLYPHS: GlyphName[] = [
  'bars', 'trend', 'donut', 'table', 'shield', 'link', 'sparkles',
  'upload', 'lock', 'receipt', 'people', 'rupee', 'calendar', 'compare',
]

const STEPS = [
  { id: 'a', label: 'Read your files', state: 'done' as const, detail: '3 files, 1,284 rows' },
  { id: 'b', label: 'Checking the query is safe', state: 'active' as const, detail: 'Read-only, 2 files' },
  { id: 'c', label: 'Asking a second model', state: 'waiting' as const, meta: 'busy, 12s' },
  { id: 'd', label: 'Drawing the chart', state: 'pending' as const },
]

const FAQ = [
  { id: 'privacy', question: 'Does the AI see my rows?', answer: 'No. It writes the query and phrases the result; the database does every calculation on your machine.' },
  { id: 'files', question: 'Which files can I bring?', answer: 'CSV and Excel exports, including the messy ones with title rows, merged headers and totals at the bottom.' },
  { id: 'free', question: 'Is it free?', answer: 'Yes, with a limit on how many questions you can ask in an hour, so one person cannot use up everyone else’s.' },
]

/* --- The page ------------------------------------------------------------- */

export default function Gallery() {
  const [tab, setTab] = useState('bars')
  const [dialog, setDialog] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [seen, setSeen] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  return (
    <div className="min-h-full bg-canvas">
      <div className="relative isolate overflow-hidden border-b border-hairline-soft">
        <AuroraBackdrop />
        <div className="relative mx-auto w-full max-w-[1120px] px-4 py-16 sm:px-6 sm:py-24">
          <h1 className="text-hero-display text-ink-deep">Canvas</h1>
          <p className="mt-4 measure text-subtitle-md text-slate">
            DarwinLens’s design system, v3. Every token, type role, glyph and primitive, in every state. Tokens live in{' '}
            <code className="text-code">src/index.css</code>; the rules live in <code className="text-code">docs/DESIGN_SYSTEM.md</code>.
          </p>
        </div>
      </div>

      <div className="mx-auto w-full max-w-[1120px] px-4 py-12 sm:px-6">
        <Section id="colour" title="Colour" note="Use the names, never the hex: bg-canvas, text-slate, border-hairline-soft. Charts read var(--color-chart-1).">
          <div className="space-y-8">
            {COLOURS.map((group) => (
              <div key={group.group}>
                <h3 className="text-subtitle-lg text-ink-deep">{group.group}</h3>
                <div className="mt-4 flex flex-wrap gap-3">
                  {group.swatches.map((swatch) => (
                    <div key={swatch.name} className="w-[150px]">
                      <div
                        className={cx(
                          'flex h-20 items-end rounded-xl border border-hairline-soft p-3 text-caption font-bold',
                          swatch.className,
                          swatch.onDark ? 'text-white' : 'text-ink-deep',
                        )}
                      >
                        {swatch.name}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>

        <Section id="type" title="Type" note="Montserrat variable, self-hosted. Sentence case everywhere. No all-caps labels, no eyebrows.">
          <div className="space-y-6">
            {TYPE_ROLES.map((role) => (
              <div key={role.role} className="border-b border-hairline-soft pb-6 last:border-b-0">
                <p className={cx(role.role, 'text-ink-deep')}>Salary cost rose ₹1.4 Cr</p>
                <p className="mt-2 text-body-sm text-steel">
                  <code className="text-code">{role.role}</code> — {role.use}
                </p>
              </div>
            ))}
            <div>
              <p className="text-code rounded-lg bg-surface-soft px-4 py-3 text-ink">select department, sum(annual_ctc) from salary group by 1</p>
              <p className="mt-2 text-body-sm text-steel">
                <code className="text-code">text-code</code> — SQL only. Never a data label.
              </p>
            </div>
          </div>
        </Section>

        <Section id="shape" title="Shape and elevation" note="Flat by default: a hairline, never a shadow. Two shadows exist in the whole product.">
          <Row>
            {RADII.map((radius) => (
              <Slot key={radius.name} label={`${radius.name} — ${radius.px}px · ${radius.use}`}>
                <div className={cx('size-16 border border-hairline bg-surface-soft', radius.className)} />
              </Slot>
            ))}
          </Row>
          <div className="mt-10 flex flex-wrap gap-8">
            <Slot label="Flat — every card">
              <div className="size-20 rounded-xxl border border-hairline-soft bg-canvas" />
            </Slot>
            <Slot label="Level 1 — the active pill tab only">
              <div className="size-20 rounded-xxl bg-canvas shadow-level-1" />
            </Slot>
            <Slot label="Level 2 — composer, drawers, menus, dialogs">
              <div className="size-20 rounded-xxl bg-canvas shadow-level-2" />
            </Slot>
          </div>
        </Section>

        <Section id="buttons" title="Buttons" note="Every button is a pill. Black for anything you can do; cobalt only for Ask, Run, Continue and Create account.">
          <Row>
            <Slot label="primary — the black pill">
              <Button variant="primary">Save to board</Button>
              <Button variant="primary" size="sm">Save</Button>
              <Button variant="primary" disabled>Save to board</Button>
            </Slot>
            <Slot label="action — cobalt, the core action">
              <Button variant="action">Ask</Button>
              <Button variant="action" size="sm">Run</Button>
            </Slot>
          </Row>
          <div className="mt-8">
            <Row>
              <Slot label="secondary · ghost · quiet">
                <Button variant="secondary">Use the sample company</Button>
                <Button variant="ghost">See what’s inside</Button>
                <Button variant="quiet">More ideas</Button>
              </Slot>
              <Slot label="loading — the width does not change">
                <Button variant="action" loading={loading} onClick={() => { setLoading(true); setTimeout(() => setLoading(false), 1600) }}>
                  Run this analysis
                </Button>
              </Slot>
            </Row>
          </div>
          <div className="mt-8">
            <Row>
              <Slot label="IconButton — soft · ghost · outline">
                <IconButton label="Download CSV" variant="soft"><MoreIcon /></IconButton>
                <IconButton label="Close" variant="ghost"><CloseIcon /></IconButton>
                <IconButton label="Search" variant="outline"><SearchIcon /></IconButton>
              </Slot>
              <Slot label="Kbd">
                <Kbd>⌘K</Kbd>
                <Kbd>↵</Kbd>
                <Kbd>Esc</Kbd>
              </Slot>
              <Slot label="Avatar — member and guest">
                <Avatar name="Sahil Patel" guest={false} />
                <Avatar name="Guest" guest />
              </Slot>
            </Row>
          </div>
        </Section>

        <Section id="tabs" title="Pill tabs" note="One tab shape in the product. The indicator slides, which is what says the pills are one control.">
          <PillTabs
            label="Chart type"
            active={tab}
            onChange={setTab}
            tabs={[{ id: 'bars', label: 'Bars' }, { id: 'line', label: 'Over time' }, { id: 'share', label: 'Share' }, { id: 'table', label: 'Table' }]}
          >
            <p className="mt-6 text-body-md text-slate">Showing: {tab}</p>
          </PillTabs>
          <div className="mt-8">
            <PillTabs
              label="Small"
              size="sm"
              active={tab}
              onChange={setTab}
              tabs={[{ id: 'bars', label: 'Bars' }, { id: 'line', label: 'Over time' }, { id: 'share', label: 'Share' }]}
            />
          </div>
        </Section>

        <Section id="cards" title="Cards" note="Three tones, three radii, and never a shadow.">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
            <Card>
              <h3 className="text-heading-sm text-ink-deep">Canvas</h3>
              <p className="mt-2 text-body-md text-slate">The standard card: white, hairline, 24px corners.</p>
            </Card>
            <Card tone="soft" radius="xl">
              <h3 className="text-heading-sm text-ink-deep">Soft</h3>
              <p className="mt-2 text-body-md text-slate">A tile inside a page that is already white.</p>
            </Card>
            <Card tone="dark" radius="xxxl">
              <h3 className="text-heading-sm">Dark</h3>
              <p className="mt-2 text-body-md text-white/80">The showcase card. One per marketing page.</p>
            </Card>
          </div>
        </Section>

        <Section id="badges" title="Badges, chips and checks">
          <Row>
            <Slot label="Badge — confidence">
              <Badge level="high" />
              <Badge level="medium" />
              <Badge level="low" />
            </Slot>
            <Slot label="Badge — tones">
              <Badge tone="success">No AI involved</Badge>
              <Badge tone="neutral">Sample company</Badge>
              <Badge tone="promo">New</Badge>
            </Slot>
          </Row>
          <div className="mt-8">
            <Row>
              <Slot label="Chip — a question you can ask">
                <Chip leading={<Glyph name="bars" size={18} />}>What is the average salary by department?</Chip>
                <Chip selected>Only 2025</Chip>
              </Slot>
              <Slot label="Chip static — a computed fact">
                <Chip static>Engineering is 42% of payroll</Chip>
              </Slot>
            </Row>
          </div>
          <div className="mt-8 max-w-md">
            <VerifiedList
              animate
              items={['Read 1,284 rows from 3 files', 'The query only reads, never writes', 'A second model agreed with the number']}
            />
          </div>
          <div className="mt-6 flex items-center gap-3">
            <Check title="Done" />
            <span className="text-body-md text-slate">Check, on its own</span>
          </div>
        </Section>

        <Section id="figures" title="Figures and progress">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <Card>
              <StatTile value="₹20.40 Cr" label="Total salary cost, 2025" delta={{ text: '+7.4%', direction: 'up', good: false }} animate />
            </Card>
            <Card>
              <div className="flex items-center gap-6">
                <ProgressRing value={0.66} size={72} label="Reading your files">2 of 3</ProgressRing>
                <UsageMeter label="Questions this hour" used={34} limit={40} note="Resets at the top of the hour." className="min-w-0 flex-1" />
              </div>
            </Card>
          </div>
          <Card className="mt-6">
            <ProgressSteps steps={STEPS} />
          </Card>
        </Section>

        <Section id="fields" title="Fields" note="44px, radius 8, a hairline that firms up on hover, a 2px cobalt ring on focus.">
          <div className="grid max-w-xl grid-cols-1 gap-6">
            <Input label="Work email" placeholder="you@company.com" />
            <Input label="Password" type="password" hint="At least 10 characters." />
            <Input label="Work email" defaultValue="not-an-email" error="That does not look like an email address." />
            <Select label="What do you do?" defaultValue="analyst">
              <option value="analyst">HR analyst</option>
              <option value="partner">HR business partner</option>
              <option value="payroll">Payroll</option>
            </Select>
            <Textarea label="Your agreed definition of attrition" placeholder="Leavers in the period ÷ average headcount" />
          </div>
        </Section>

        <Section id="overlays" title="Overlays and messages">
          <Row>
            <Slot label="Dialog · Drawer">
              <Button onClick={() => setDialog(true)}>Open a dialog</Button>
              <Button onClick={() => setDrawer(true)}>Open the data drawer</Button>
            </Slot>
            <Slot label="Menu · Popover · Tooltip · WhatsThis">
              <Menu
                triggerLabel="Actions"
                className="press inline-flex size-10 items-center justify-center rounded-circle bg-surface-soft"
                trigger={<MoreIcon />}
                actions={[
                  { id: 'ask', label: 'Ask about this', onSelect: () => toast('Asked') },
                  { id: 'csv', label: 'Download CSV', onSelect: () => toast('Downloaded') },
                  { id: 'del', label: 'Remove from board', onSelect: () => toast('Removed'), disabled: true },
                ]}
              />
              <Popover
                trigger="Why this number?"
                title="Why this number?"
                className="press rounded-full border border-hairline-soft px-4 py-2 text-body-sm text-ink-deep"
              >
                It came from 1,284 rows in Salary Register 2025, summed by the database — not written by a model.
              </Popover>
              <Tooltip label="Save to board">
                <button type="button" aria-label="Save to board" className="press rounded-circle bg-surface-soft p-2.5">
                  <Glyph name="receipt" size={20} />
                </button>
              </Tooltip>
              <WhatsThis title="Links between files" body="A link is a column two files share, so a question can reach across both." />
            </Slot>
            <Slot label="Toast">
              <Button onClick={() => toast('Saved to board')}>Raise a toast</Button>
              <Button onClick={() => toast('That file could not be read.', 'error')}>Raise an error</Button>
            </Slot>
          </Row>

          <div className="mt-8 space-y-3">
            <Banner tone="info">Your files stay in this browser for two hours.</Banner>
            <Banner tone="warn" nextStep="Check the date column and ask again.">Two dates could be read either way round.</Banner>
            <Banner tone="error" nextStep="Restart the server, then reload the page." onDismiss={() => {}}>
              DarwinLens could not reach the server.
            </Banner>
          </div>

          <div className="mt-8 max-w-xl">
            <Tip id="data-button" seen={seen} onDismiss={(id) => setSeen((was) => [...was, id])}>
              Everything DarwinLens read from your files is behind the Data button.
            </Tip>
            {seen.includes('data-button') && (
              <button type="button" onClick={() => setSeen([])} className="text-body-sm underline">
                Show the tip again
              </button>
            )}
          </div>
        </Section>

        <Section id="accordion" title="Accordion">
          <div className="max-w-2xl">
            <Accordion items={FAQ} defaultOpenId="privacy" />
          </div>
        </Section>

        <Section id="empty" title="Empty and loading">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <EmptyState glyph="receipt" title="Nothing saved yet" action={<Button variant="primary">Ask your first question</Button>}>
              Save an answer to build a report you can print.
            </EmptyState>
            <Card flush className="p-8">
              <div role="status" className="space-y-4">
                <Skeleton className="h-9 w-2/3" />
                <Skeleton className="h-5 w-1/2" />
                <Skeleton shape="card" className="h-40 w-full" />
              </div>
            </Card>
          </div>
        </Section>

        <Section id="glyphs" title="Glyphs" note="Duotone line illustrations, 24–64px. currentColor for the line, one accent underneath.">
          <div className="grid grid-cols-3 gap-6 sm:grid-cols-5 lg:grid-cols-7">
            {GLYPHS.map((name, i) => (
              <div key={name} className="flex flex-col items-center gap-2">
                <Glyph name={name} size={44} accent={i % 2 ? 'var(--color-purple)' : 'var(--color-primary)'} className="text-ink-deep" />
                <span className="text-caption text-steel">{name}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section id="graphics" title="Generated graphics" note="No stock photos and no external assets: the hero art is CSS and inline SVG built from the tokens.">
          <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-2">
            <div className="relative isolate overflow-hidden rounded-xxxl border border-hairline-soft">
              <AuroraBackdrop />
              <div className="relative px-8 py-16">
                <p className="text-heading-md text-ink-deep">AuroraBackdrop</p>
                <p className="mt-2 text-body-md text-slate">Three drifting radial gradients and a fine grain, over white.</p>
              </div>
            </div>
            <div className="flex justify-center">
              <AppPreview />
            </div>
          </div>
        </Section>
      </div>

      <Dialog
        open={dialog}
        onClose={() => setDialog(false)}
        title="Delete this project?"
        description="Its files, questions and saved answers go with it."
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialog(false)}>Keep it</Button>
            <Button variant="primary" onClick={() => setDialog(false)}>Delete the project</Button>
          </>
        }
      >
        <p className="text-body-md text-slate">Projects live in this browser, so there is no copy anywhere else to restore from.</p>
      </Dialog>

      <Drawer open={drawer} onClose={() => setDrawer(false)} title="Your data" description="3 files · 1,284 rows">
        <p className="text-body-md text-slate">Files, links between files and your agreed definitions live here.</p>
      </Drawer>

      <Toaster />
    </div>
  )
}
