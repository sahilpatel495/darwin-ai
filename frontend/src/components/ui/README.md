# Primitives

`import { Button, Figure, ProofList } from '../ui'` — always from the folder, never a file.
Open `#/ui` to see every one in every state. Tokens, type and motion live in `src/index.css`.

## Tokens

Colour: `paper sheet wash rule rule-strong · ink ink-soft ink-faint · indigo indigo-soft indigo-ink · audit amber red` (each with a `-soft`) · `series-1…5`.
Use them as classes (`bg-paper`, `text-ink-soft`, `border-rule`) — never a raw hex. Charts read `var(--color-series-1)`.
Radius: `rounded-control` (4px) for buttons, inputs, sheets; `rounded-chip` (2px) for chips and badges. Nothing is a pill.
Shadow: `shadow-float`, and only on things that float. Paper casts none.
Type: `type-figure type-headline type-statement type-title type-body type-small type-code`, plus `measure` for a 64ch reading column.
Motion: `animate-tick` `animate-rule` `animate-fade`. Reduced motion makes all three instant.

The old names (`canvas surface sunken line accent good warn bad radius-card`) still resolve, as aliases onto the palette above. They are temporary — migrate your files, then the alias block in `index.css` goes.

## The primitives

| Primitive | Props | One line |
|---|---|---|
| `Button` | `variant` `'primary'∣'secondary'∣'quiet'` · `size` `'md'∣'sm'` · `loading` · all button attrs | `<Button variant="primary" loading={asking}>Ask</Button>` |
| `Tick` | `size=16` · `animate` · `delay` · `title` | `<Tick animate delay={90} />` |
| `ProofList` | `items: ReactNode[]` · `animate` | `<ProofList items={proofLines(answer)} animate />` |
| `Figure` | `value: string` · `caption` · `animate` | `<Figure value="₹20.40 Cr" caption="Gross pay, 2025" animate />` |
| `Sheet` | `as` `'div'∣'section'∣'article'∣'li'` · all HTML attrs | `<Sheet as="section" className="p-5">…</Sheet>` |
| `RuledRow` | `as` `'div'∣'li'` · `hover` | `<RuledRow as="li" hover>…</RuledRow>` |
| `Tabs` | `label` · `tabs: {id,label,buttonProps?}[]` · `active` · `onChange` · children = active panel | `<Tabs label="Your data" tabs={TABS} active={tab} onChange={setTab}>…</Tabs>` |
| `Dialog` | `open` · `onClose` · `title` · `footer` · `size` `'sm'∣'md'∣'lg'` | `<Dialog open={open} onClose={close} title="Delete this project?" footer={…}>…</Dialog>` |
| `Popover` | `trigger` · `triggerLabel` · `title` · `align` `'left'∣'right'` · `className` (on the trigger) | `<Popover trigger="Why this number?" title="…">…</Popover>` |
| `WhatsThis` | `title` · `body` · `align` | `<WhatsThis title={EXPLAIN.links.title} body={EXPLAIN.links.body} />` |
| `Banner` | `tone` `'info'∣'warn'∣'error'` · `nextStep` · `action` · `onDismiss` | `<Banner tone="error" nextStep="Re-attach them to ask new questions.">Your files are no longer loaded.</Banner>` |
| `Skeleton` | `className` (size it) | `<Skeleton className="h-5 w-40" />` |
| `EmptyState` | children = one sentence · `action` | `<EmptyState action={<Button…/>}>Save an answer to build a report you can print.</EmptyState>` |
| `Chip` | `selected` · all button attrs | `<Chip onClick={() => ask(q)}>{q}</Chip>` |
| `Badge` | `level` `'high'∣'medium'∣'low'` | `<Badge level={answer.confidence.level} />` |

`cx(...)` joins class names and drops falsy ones. Every primitive takes `className`; utilities win over the primitive's own styles. React 19, so `ref` is a plain prop on `Button`, `Chip`, `Sheet` and `RuledRow` — no `forwardRef`.

## Do / don't

- **Hierarchy comes from rules, whitespace and type.** Not from cards. A list is `RuledRow`s; the only `Sheet` in a thread is the answer statement, which is what makes it read as the statement.
- **`Figure` once per answer,** for a single value. Two figures side by side and neither is the headline.
- **`ProofList` lines are generated from the answer** (§6.4), never hard-coded, and they are plain sentences — not pills, not badges.
- **`Badge` is confidence only.** Anything else that needs a colour is a `Banner` or a word.
- **`animate` only on the arriving answer.** Nothing animates on its own: no entrance on a section, no hover lift.
- **Never hover-only.** `WhatsThis` and `Popover` open on click and on keyboard, because a phone has no hover and a keyboard has no pointer.
- **Buttons say what happens.** "Save to board", "Re-attach files", "Remove link" — not "Submit", "OK", "Confirm". Sentence case, no arrow glyph appended.
- **Errors say what happened, then what to do.** `children` is the first, `nextStep` the second. No status codes, no apology.
- **No all-caps labels, no eyebrow above a heading, no meta joined by middle dots, no mono for a data label.** Mono is SQL.
- **Numerals in tables:** `text-right tabular-nums`.
- **Give every control a name.** An icon-only button needs `aria-label`; `Popover` needs `triggerLabel`.
- **Links are underlined by default** with a `rule-strong` hairline that goes solid on hover. That is right in a sentence and wrong in a nav bar or on the wordmark — put `no-underline` on those.
- **There is no destructive variant.** A confirm dialog gets `variant="primary"`; the title and the label carry the weight ("Delete this project?" / "Delete the project"). Red is for something that went wrong, not for something you are about to do.

## Printing (`#/p/<id>/board`)

The print stylesheet in `index.css` hides every `button`, `input`, `textarea`, `select` and `[role=tab]` on its own, and keeps each `Sheet` on one page. Everything that is chrome rather than report — header, sidebar, drawer, composer wrapper — needs `print-hide` or `data-print="hide"`. Use `print-keep` on any block you also want held together.
