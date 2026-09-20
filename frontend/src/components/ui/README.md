# Primitives

`import { Button, Card, StatTile } from '../ui'` — always from the folder, never a file.
Open `#/ui` to see every one in every state, in light and dark side by side. Tokens, type and motion live in `src/index.css`.

## Tokens

Colour: `wash surface surface-2 fill fill-hover line line-soft · ink ink-2 ink-3 · blue blue-hover blue-soft blue-ink · green amber red` (each with `-soft` and `-ink`) · `series-1…7`.
Use them as classes (`bg-wash`, `text-ink-2`, `border-line`) — never a raw hex. Charts read `var(--color-series-1)`.
Radius: `rounded-input` (6px) inputs and small buttons · `rounded-card` (8px) cards and dialogs · `rounded-hero` (12px) the big surfaces · `rounded-pill` chips, pills, icon buttons.
Shadow: `shadow-1` resting card · `shadow-2` hovered interactive card and the sticky composer · `shadow-3` dialogs, popovers, menus.
Type: `type-hero type-page type-card type-section type-body type-small type-micro type-code`, plus `measure` for a 66ch column and `tnum` for tabular figures.
Motion: `page-enter stagger-children card-hover press dialog-in popover-in toast-in check-pop shimmer` and `animate-breathe`. Reduced motion makes all of them instant and removes the transforms.

**Dark** is the same token names redefined under `[data-theme="dark"]`. `ThemeToggle` writes it to `<html>`; the inline script in `index.html` stamps it before first paint. Nothing in a component branches on the theme.


## The primitives

| Primitive | Props | One line |
|---|---|---|
| `Button` | `variant` `'primary'∣'secondary'∣'ghost'` · `size` `'md'∣'sm'` · `pill` · `loading` | `<Button variant="primary" loading={asking}>Ask</Button>` |
| `IconButton` | `label` (required) · `children` the glyph · `size` · `variant` `'fill'∣'ghost'` | `<IconButton label="Download CSV"><DownloadIcon /></IconButton>` |
| `Card` | `as` · `interactive` · `hero` · `flush` · all HTML attrs | `<Card as="article" interactive>…</Card>` |
| `ListRow` | `as` · `hover` · `divided` | `<ListRow as="li" hover>…</ListRow>` |
| `NavRail` / `NavItem` | `items: NavItemSpec[]` · `active` · `project` · `footer` | mounted once, in `App.tsx` |
| `Tabs` | `label` · `tabs: {id,label,buttonProps?}[]` · `active` · `onChange` · children = active panel | `<Tabs label="Your data" tabs={TABS} active={tab} onChange={setTab}>…</Tabs>` |
| `SegmentedControl` | `label` · `options: {value,label,name?}[]` · `value` · `onChange` · `size` | `<SegmentedControl label="Chart type" options={TYPES} value={t} onChange={setT} />` |
| `Dialog` | `open` · `onClose` · `title` · `description` · `footer` · `size` `'sm'∣'md'∣'lg'∣'xl'` | `<Dialog open={open} onClose={close} title="Delete this project?" footer={…}>…</Dialog>` |
| `Popover` | `trigger` · `triggerLabel` · `title` · `align` · `className` (on the trigger) | `<Popover trigger="Why this number?" title="…">…</Popover>` |
| `Menu` | `trigger` · `triggerLabel` · `actions: {id,label,onSelect,disabled?}[]` · `align` | `<Menu trigger={<MoreIcon/>} triggerLabel="Actions" actions={…} />` |
| `Tooltip` | `label` · one focusable child · `side` | `<Tooltip label="Stop"><button …/></Tooltip>` |
| `WhatsThis` | `title` · `body` · `align` | `<WhatsThis title={EXPLAIN.links.title} body={EXPLAIN.links.body} />` |
| `Banner` | `tone` `'info'∣'warn'∣'error'` · `nextStep` · `action` · `onDismiss` | `<Banner tone="error" nextStep="Re-attach them to ask new questions.">Your files are no longer loaded.</Banner>` |
| `Toaster` / `toast(text, tone?)` | mounted once in `App.tsx`; call `toast()` from anywhere | `toast('Saved to board')` |
| `Skeleton` | `className` (size it) | `<Skeleton className="h-5 w-40" />` |
| `EmptyState` | `title?` · children = one sentence · `action` | `<EmptyState action={<Button…/>}>Save an answer to build a report you can print.</EmptyState>` |
| `Chip` | `selected` · `static` (a computed fact, not a control) · all button attrs | `<Chip onClick={() => ask(q)}>{q}</Chip>` |
| `Badge` | `level` `'high'∣'medium'∣'low'` | `<Badge level={answer.confidence.level} />` |
| `Check` | `size=18` · `animate` · `delay` · `title` | `<Check animate delay={90} />` |
| `VerifiedList` | `items: ReactNode[]` · `animate` | `<VerifiedList items={verifiedLines(answer)} animate />` |
| `StatTile` | `value` (formatted string) · `label` · `delta` · `aside` · `animate` | `<StatTile value="₹20.40 Cr" label="Gross pay, 2025" animate />` |
| `ProgressSteps` | `steps: {id,label,detail?,state,meta?}[]` | `<ProgressSteps steps={thinking} />` |
| `ThemeToggle` | `variant` `'icon'∣'full'` | `<ThemeToggle />` |

Also exported: `cx(...)` joins class names and drops falsy ones · every icon from `icons.tsx` · `useTheme / getTheme / setTheme / resolveTheme` · `useCountUp(display, animate)`.
Every primitive takes `className`; utilities win over the primitive's own styles. React 19, so `ref` is a plain prop — no `forwardRef`.


## Do / don't

- **Hierarchy comes from elevation, type and space.** A white `Card` on the grey wash is the unit. Do not put a card inside a card to group two things — use space.
- **Only an `interactive` card moves.** No hover lift on a container, no entrance animation on an ordinary section. Motion explains a change; anything else is decoration (§4).
- **`StatTile` once per answer,** for a single value. Two hero figures side by side and neither is the headline.
- **`VerifiedList` lines are generated from the answer** (§6.4, §12), never hard-coded, and they are plain sentences — not pills, not badges.
- **`Badge` is confidence only.** A computed fact is a `static` `Chip`. Anything else that needs a colour is a `Banner` or a word.
- **`animate` only on the arriving answer,** and `stagger-children` only on a grid that has just mounted.
- **Never hover-only.** `Popover`, `Menu` and `WhatsThis` open on click and on keyboard. `Tooltip` is an echo of a control's `aria-label`, never the only place something is said.
- **Buttons say what happens.** "Save to board", "Re-attach files", "Remove link" — not "Submit", "OK", "Confirm". Sentence case, no arrow glyph appended.
- **Errors say what happened, then what to do.** `children` is the first, `nextStep` the second. No status codes, no apology.
- **No all-caps labels, no eyebrow above a heading, no meta joined by middle dots, no mono for a data label.** Mono is SQL.
- **Numerals in tables:** `text-right tnum`.
- **Give every control a name.** An icon-only button is an `IconButton`, whose `label` is required; `Popover` and `Menu` need `triggerLabel`.
- **Links are blue and underlined** in running text. That is wrong in a nav bar or on the wordmark — put `no-underline` there.
- **There is no destructive variant.** A confirm dialog gets `variant="primary"`; the title and the label carry the weight ("Delete this project?" / "Delete the project"). Red is for something that went wrong, not for something you are about to do.

## Printing (`#/p/<id>/board`)

The print stylesheet in `index.css` hides every `nav`, `button`, `input`, `textarea`, `select` and `[role=tab]` on its own, and keeps each `Card` on one page. Everything else that is chrome rather than report — header, sidebar, drawer, composer wrapper — needs `print-hide` or `data-print="hide"`. Use `print-keep` on any block you also want held together.
