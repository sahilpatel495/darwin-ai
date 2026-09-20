# Primitives — "Canvas" v3

`import { Button, Card, StatTile } from '../ui'` — always from the folder, never a file.
Open `#/ui` to see every one in every state. Tokens, type and motion live in `src/index.css`; the rules live in `docs/DESIGN_SYSTEM.md`.

**Light is the only theme.** There is no `ThemeToggle`, no `[data-theme]`, no `dark:` class and no `prefers-color-scheme` branch. Do not add one back.

## Tokens

Colour: `canvas surface-soft hairline hairline-soft` · `ink-deep ink charcoal slate steel stone` · `primary primary-deep primary-soft` · `purple` · `success attention critical` (each with `-soft`) · `warning` · `chart-1…6`, `heat-low`, `heat-high`.
Use them as classes (`bg-canvas`, `text-slate`, `border-hairline-soft`) — never a raw hex. Charts read `var(--color-chart-1)`.
One addition to §2: `attention-ink` (`#9A5205`), for **words on `attention-soft` only** — `attention` itself is 4.13:1 on its own tint. Everything else uses `attention` unchanged.

Radius: `rounded-lg` (8, inputs) · `rounded-xl` (16, small tiles and accordion items) · `rounded-xxl` (24, standard cards and the docked composer) · `rounded-xxxl` (32, hero frames and showcase cards) · `rounded-feature` (40) · `rounded-full` (100px, **every** button, chip, tab and badge) · `rounded-circle`.
Elevation: flat. A card is `border border-hairline-soft` and nothing else. `shadow-level-1` is the active pill tab; `shadow-level-2` is the sticky composer, drawers, menus and dialogs. Nothing else casts a shadow.
Type: `text-hero-display text-display-lg text-heading-lg text-heading-md text-heading-sm text-subtitle-lg text-subtitle-md text-body-md text-body-sm text-button-md text-caption text-code`, plus `measure` for a 64ch column and `tnum` for tabular figures. Each one already carries its size, weight, line height and tracking, and the five headings carry `ss01`/`ss02`. Colour is a separate utility: `text-heading-lg text-ink-deep`.
Motion: `page-enter stagger-children card-hover press rise-in dialog-in popover-in toast-in check-pop drawer-in shimmer shimmer-text caret` and `animate-breathe`. Durations and curves are `--dur-*` and `--ease-*`. Reduced motion makes all of them instant and removes the transforms.

## The primitives

| Primitive | Props | One line |
|---|---|---|
| `Button` | `variant` `'primary'∣'action'∣'secondary'∣'ghost'∣'quiet'` · `size` `'md'(44)∣'sm'(36)` · `loading` · `block` | `<Button variant="action" loading={asking}>Ask</Button>` |
| `IconButton` | `label` (required) · `children` the glyph · `size` `'md'(40)∣'sm'(32)` · `variant` `'soft'∣'ghost'∣'outline'` | `<IconButton label="Download CSV"><DownloadIcon /></IconButton>` |
| `PillTabs` | `label` · `tabs: {id,label,href?,props?}[]` · `active` · `onChange?` · `size` · children = active panel | `<PillTabs label="Chart type" tabs={TYPES} active={t} onChange={setT} />` |
| `Card` | `tone` `'canvas'∣'soft'∣'dark'` · `radius` `'xl'∣'xxl'∣'xxxl'` · `interactive` · `flush` · `as` | `<Card as="article" tone="dark" radius="xxxl">…</Card>` |
| `Input` / `Textarea` / `Select` | `label` (required) · `labelHidden` · `hint` · `error` · every native attr | `<Input label="Work email" error={problem} />` |
| `Badge` | `tone` `'success'∣'attention'∣'critical'∣'neutral'∣'promo'` · `level` `'high'∣'medium'∣'low'` · `dot` | `<Badge level={answer.confidence.level} />` · `<Badge tone="success">No AI involved</Badge>` |
| `Chip` | `selected` · `static` (a computed fact, not a control) · `leading` · all button attrs | `<Chip leading={<Glyph name="bars" size={18} />} onClick={…}>{q}</Chip>` |
| `Drawer` | `open` · `onClose` · `title` · `description` · `footer` | `<Drawer open={open} onClose={close} title="Your data">…</Drawer>` |
| `Dialog` | `open` · `onClose` · `title` · `description` · `footer` · `size` `'sm'∣'md'∣'lg'∣'xl'` | `<Dialog open={open} onClose={close} title="Delete this project?">…</Dialog>` |
| `Menu` | `trigger` · `triggerLabel` · `actions: {id,label,onSelect,disabled?}[]` · `align` | `<Menu trigger={<MoreIcon/>} triggerLabel="Actions" actions={…} />` |
| `Popover` | `trigger` · `triggerLabel` · `title` · `align` · `className` (on the trigger) | `<Popover trigger="Why this number?" title="…">…</Popover>` |
| `Tooltip` | `label` · one focusable child · `side` · `align` | `<Tooltip label="Stop"><button …/></Tooltip>` |
| `Toaster` / `toast(text, tone?)` | mounted once in `App.tsx`; call `toast()` from anywhere | `toast('Saved to board')` |
| `Accordion` | `items: {id,question,answer}[]` · `defaultOpenId` | `<Accordion items={FAQ} />` |
| `Skeleton` | `className` (size it) · `shape` `'pill'∣'card'` | `<Skeleton className="h-9 w-40" />` |
| `EmptyState` | `glyph` · `title?` · children = one sentence · `action` | `<EmptyState glyph="receipt" action={…}>Save an answer to build a report you can print.</EmptyState>` |
| `StatTile` | `value` (formatted string) · `label` · `delta` · `aside` · `animate` | `<StatTile value="₹20.40 Cr" label="Gross pay, 2025" animate />` |
| `Check` / `VerifiedList` | `items: ReactNode[]` · `animate` | `<VerifiedList items={verifiedLines(answer)} animate />` |
| `ProgressSteps` | `steps: {id,label,detail?,state,meta?}[]` | the running step's own words shimmer |
| `ProgressRing` | `value` 0–1 · `size` · `label` (required) · children = the middle | `<ProgressRing value={2/3} label="Reading your files">2 of 3</ProgressRing>` |
| `Banner` | `tone` `'info'∣'warn'∣'error'` · `nextStep` · `action` · `onDismiss` | `<Banner tone="error" nextStep="Re-attach them to ask new questions.">Your files are no longer loaded.</Banner>` |
| `Tip` | `id` · `seen` · `onDismiss` · children = **one line** | `<Tip id="data-button" seen={project.tipsSeen} onDismiss={markSeen}>…</Tip>` |
| `Kbd` | children = one key | `<Kbd>⌘K</Kbd>` |
| `Avatar` | `name` · `guest` · `size` `'sm'∣'md'∣'lg'` | `<Avatar name={user.name} guest={user.kind === 'guest'} />` |
| `UsageMeter` | `label` · `used` · `limit` · `note` | `<UsageMeter label="Questions this hour" used={u.asks_this_hour} limit={u.asks_per_hour} />` |
| `WhatsThis` | `title` · `body` · `align` | `<WhatsThis title={EXPLAIN.links.title} body={EXPLAIN.links.body} />` |
| `ListRow` | `as` · `hover` · `divided` | `<ListRow as="li" hover>…</ListRow>` |

Also exported: `cx(...)` joins class names and drops falsy ones · every icon from `icons.tsx` · `useCountUp(display, animate)`.
Every primitive takes `className`; utilities win over the primitive's own styles. React 19, so `ref` is a plain prop — no `forwardRef`.

## Graphics (`../graphics`)

`AuroraBackdrop` (`intensity` `'hero'∣'panel'`) — the signature background for heroes, auth and onboarding. Put it inside a `relative isolate overflow-hidden` parent and your content in a `relative` sibling.
`AppPreview` — the landing hero's photograph. It loops on its own, pauses off-screen, and parks on the finished answer under reduced motion.
`Glyph` (`name`, `size`, `accent`) — 14 duotone line illustrations: `bars trend donut table shield link sparkles upload lock receipt people rupee calendar compare`. `currentColor` for the line, one accent underneath.

## Temporary aliases — delete on sight

These exist only so unmigrated screens compile. Nothing new may use them.

- **Colour and radius names from v2** (`bg-wash`, `text-ink-2`, `rounded-card`, `shadow-3`, `bg-blue`, `bg-amber-soft`, `series-1…7`, …) are re-pointed at their v3 replacement in the alias block at the end of `@theme` in `index.css`. `shadow-1` is now `none`, because nothing rests on a shadow.
- **`type-*` classes** (`type-hero type-page type-card type-section type-body type-small type-micro type-code`) are re-pointed at their §3 role in the alias block at the end of `index.css`.
- **`Tabs`** and **`SegmentedControl`** are thin wrappers that render `PillTabs`. Call `PillTabs` directly and delete the file.
- **`Button`'s `pill` prop** does nothing. Every button is a pill.
- **`Card`'s `hero` prop** means `radius="xxxl"`; **`IconButton`'s `fill` variant** means `soft`.

The job is done when `grep -rn 'type-body\|bg-wash\|text-ink-2\|rounded-card\|shadow-3' src` comes back empty and the alias block is deleted.

## Do / don't

- **Hierarchy comes from type, space and a hairline** — never a shadow, never a grey page. A card inside a card is a mistake; use space.
- **Every button is a pill.** Black (`primary`) for anything you can do. Cobalt (`action`) **only** for Ask, Run, Continue and Create account — one per screen at most.
- **Only an `interactive` card moves.** No hover lift on a container, no entrance animation on an ordinary section. Motion explains a change; anything else is decoration.
- **`StatTile` once per answer.** Two hero figures side by side and neither is the headline.
- **`VerifiedList` lines are generated from the answer**, never hard-coded, and they are plain sentences — not pills, not badges.
- **`Badge` states a fact.** Confidence, "No AI involved", "Sample company". Anything longer is a `Banner` or a sentence.
- **`Tip` replaces the tour.** One line, once, beside the thing it explains. Three exist in the whole product. There is no coach-mark tour and no modal walkthrough.
- **Never hover-only.** `Popover`, `Menu` and `WhatsThis` open on click and on keyboard. `Tooltip` is an echo of a control's `aria-label`.
- **Buttons say what happens.** "Save to board", "Re-attach files" — not "Submit", "OK", "Confirm". Sentence case, no arrow glyph appended.
- **Errors say what happened, then what to do.** `children` is the first, `nextStep` the second. No status codes, no apology.
- **Banned:** all-caps labels, eyebrow labels above a heading, squared buttons, shadows on cards, grey-on-grey, walls of helper text, meta joined by middle dots, mono for a data label. Mono is SQL.
- **Numerals in tables:** `text-right tnum`.
- **Give every control a name.** An icon-only button is an `IconButton`, whose `label` is required; `Popover` and `Menu` need `triggerLabel`; `Input` and friends require `label`.
- **A grid needs a base `grid-cols-1`.** Without it the single implicit column sizes to max-content and one wide child pushes a phone sideways.
- **There is no destructive variant.** A confirm dialog gets `variant="primary"`; the title and the label carry the weight ("Delete this project?" / "Delete the project").

## Printing (`#/p/<id>/board`)

The print stylesheet in `index.css` hides every `nav`, `button`, `input`, `textarea`, `select` and `[role=tab]` on its own, and keeps each `Card` on one page. Everything else that is chrome rather than report — the top bar, a drawer, the composer wrapper — needs `print-hide` or `data-print="hide"`. Use `print-keep` on any block you also want held together.
