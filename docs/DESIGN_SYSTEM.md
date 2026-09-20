# Verity — UX and design system ("Clarity")

The contract for everyone touching the frontend. Read it before writing UI. `docs/DESIGN.md` says what the product does; this says how it feels and how a person moves through it.

> **Direction changed on 2026-09-20.** The first direction ("Ledger": warm paper, serif figures, ruled rows) read as a copy of Claude's own interface, so it was dropped. Sections 1 to 5 below replace it. The journey, storage contract and component seams (sections 6, 7, 10) still hold, with the amendments marked **v2**. Where an older sentence mentions paper, serif figures, ruled rows, the auditor's tick or the double rule, the rules in sections 1 to 5 win.

## 1. Who, and the idea

**Who:** an HR analyst who must put a number in front of their CHRO, and a hiring panel watching over their shoulder. Neither reads documentation.

**The idea:** it should feel like the consumer-grade apps people already use all day, so nobody needs training: a bright grey wash, white cards that lift off it, one confident blue, pill-shaped chips, system type, and motion that is quick and purposeful. The visual language is inspired by the design tokens visible in Facebook's public web CSS (surfaces, blue, radii, shadows, easing curves). No Meta names, logos or trademarks appear anywhere; in code the language is called Clarity.

**Where the boldness goes:** two moments. (1) **Thinking, made visible**: while a question runs the analyst watches each check happen. (2) **The answer card**: a headline, a hero figure, green verified checks, computed insight chips and a chart you can switch. Everything else stays calm so those two carry the product.

**This is a whole product, not a chat box:** Home (projects), Ask, Overview (an automatic dashboard computed with no AI), Analyses (guided, no AI), Saved (a printable board), Trust.

## 2. Tokens

Defined once in `frontend/src/index.css` under `@theme`; components use the token classes, never raw hex. Light is the default; dark is the same names under `[data-theme="dark"]`.

| Token | Light | Dark | Use |
|---|---|---|---|
| `wash` | `#F0F2F5` | `#18191A` | page background |
| `surface` | `#FFFFFF` | `#242526` | cards, dialogs, nav |
| `surface-2` | `#F7F8FA` | `#3A3B3C` | inset areas, table header, code, inputs |
| `fill` | `#E4E6EB` | `#3A3B3C` | secondary buttons, chips, icon buttons |
| `fill-hover` | `#D8DADF` | `#4E4F50` | their hover |
| `line` | `#CED0D4` | `#3E4042` | dividers, input borders |
| `line-soft` | `#E4E6EB` | `#2F3031` | card hairlines |
| `ink` | `#050505` | `#E4E6EB` | text |
| `ink-2` | `#65676B` | `#B0B3B8` | secondary text |
| `ink-3` | `#8A8D91` | `#8A8D91` | hints, disabled |
| `blue` | `#0866FF` | `#2D88FF` | primary action, links, focus, first series |
| `blue-hover` | `#0756D6` | `#4599FF` | |
| `blue-soft` | `#EBF5FF` | `#263951` | selected, the analyst's question bubble |
| `blue-ink` | `#0064D1` | `#75B6FF` | text on blue-soft |
| `green` / `-soft` / `-ink` | `#31A24C` / `#E6F4EA` / `#1F7A37` | `#45BD62` / `#1D3A25` / `#7BD88F` | verified, high confidence |
| `amber` / `-soft` / `-ink` | `#F7B928` / `#FFF4D6` / `#8A5A00` | `#F7B928` / `#3D3218` / `#FFD772` | needs a look, medium, caveats, waiting |
| `red` / `-soft` / `-ink` | `#E41E3F` / `#FDE7EA` / `#B3152F` | `#F3425F` / `#3F1D24` / `#FF8A9B` | errors, low confidence, disagreement |
| chart series | `#0866FF` `#00A7B5` `#7B61FF` `#F5803E` `#E5468F` `#2FA24B` `#8A8D91` | same | in this order; sequential scale for heatmaps = blue-soft → blue |

Radius: `6px` inputs and small buttons, `8px` cards and dialogs, `12px` the large hero surfaces, `999px` chips, pills and icon buttons. Elevation: `shadow-1: 0 1px 2px rgb(0 0 0 / .10)` resting cards; `shadow-2: 0 2px 12px rgb(0 0 0 / .12)` hovered interactive cards, sticky composer; `shadow-3: 0 12px 28px rgb(0 0 0 / .20), 0 2px 4px rgb(0 0 0 / .10)` dialogs, popovers, menus. Spacing on a 4px grid; cards pad 16 (phone) / 20 (desktop); page gutters 16 / 24 / 32.

## 3. Type

The system stack, exactly as the apps people use daily: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`; code: `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`. No web fonts: delete `frontend/public/fonts` and its preloads (236 KB saved, no layout shift). The ₹ sign renders in every system face.

| Role | Size / line / weight |
|---|---|
| Hero figure | 40/44, 700, `tabular-nums`, `-0.02em` |
| Page title | 28/34, 700, `-0.01em` (22/28 on phones) |
| Card title / answer headline | 20/26, 700 |
| Section heading | 17/22, 600 |
| Body | 15/22, 400 |
| Small | 13/18, 400 |
| Micro (chips, badges, axis) | 12/16, 500 |

Sentence case everywhere; no all-caps labels; no eyebrow labels; numerals right-aligned and `tabular-nums` in tables; measure under 72 characters.

## 4. Motion

Motion is part of this direction, and every piece of it explains something. Tokens: `--ease-standard: cubic-bezier(.08,.52,.52,1)`, `--ease-enter: cubic-bezier(.14,1,.34,1)`, `--ease-exit: cubic-bezier(.45,.1,.2,1)`; durations `100ms` (press, hover), `200ms` (popovers, small moves), `280ms` (cards, routes), `400ms` (charts, count-up).

- **Route change:** the incoming page fades in and rises 8px (280ms, enter); no exit animation (it must feel instant).
- **Lists and grids:** children rise 8px and fade in with a 40ms stagger, first 8 items only, once per mount (Overview tiles, project cards, analysis gallery).
- **Interactive cards:** `shadow-1` → `shadow-2` and a 1px lift on hover (200ms). Non-interactive cards never move.
- **Buttons and chips:** press scales to `.97` (100ms). Tabs and segmented controls have a sliding indicator (200ms).
- **Dialogs** scale `.96 → 1` and fade (200ms enter, 100ms exit); **popovers and menus** slide 6px and fade.
- **Thinking:** the active step has a breathing dot and a shimmer sweep across its row; a finished step's check pops (`scale .6 → 1`, 200ms); the waiting state turns amber with a countdown.
- **Answer arrival:** skeleton cross-fades to the card; headline first, then the hero figure counts up (400ms), verified checks pop in sequence (90ms stagger), the chart draws (Recharts animation 400ms, first render only).
- **Skeletons** shimmer at 1.2s linear. **Toasts** slide up 12px.
- `prefers-reduced-motion`: every duration becomes 0 and transforms are removed; nothing depends on animation to be understood.

## 5. Primitives (`frontend/src/components/ui/`)

Small, typed, accessible, no dependencies. Restyle the existing ones; keep their props where possible so screens keep compiling.

- `Button` (`primary` blue fill, white text · `secondary` `fill` background · `ghost`; sizes `md` 36px, `sm` 28px; optional `pill`; loading keeps width), `IconButton` (36px circle on `fill`, tooltip required)
- `Card` (surface, 8px, `shadow-1`; `interactive` adds hover lift and focus ring; `as` prop), `ListRow` (full-width row, `fill` on hover)
- `NavRail` + `NavItem` (section 6 v2), `Tabs` (sliding underline, roving tabindex), `SegmentedControl` (chart type, chart/table, options)
- `Dialog` (native `<dialog>`, labelled, focus returns, Esc), `Popover`, `Menu`, `Tooltip`, `WhatsThis`, `Toast`
- `Banner` (`info`, `warn`, `error`: message, next step, optional action), `Skeleton`, `EmptyState` (one sentence, one action)
- `Chip` (pill; suggested questions, follow-ups, insight chips; `selected` state), `Badge` (confidence: coloured dot + words; reasons in a Popover)
- `Check` (animated check in a green circle; replaces the old Tick) and `VerifiedList` (replaces ProofList: checked statements, plain text)
- `StatTile` (label, hero figure with count-up, optional delta chip and sparkline slot; replaces Figure)
- `ProgressSteps` (the thinking timeline: step label, live detail, state `pending | active | done | warn | failed | waiting`)
- `ThemeToggle` (light / dark / system, stored in `localStorage`; ships only if dark passes QA on every screen, otherwise it is removed, not hidden behind a bug)

A gallery at `#/ui` shows every primitive in every state, in light and dark.

## 6. The journey

Hash routes, no router library: `#/` home · `#/p/<id>` ask · `#/p/<id>/overview` · `#/p/<id>/analyses` · `#/p/<id>/board` saved · `#/trust` Trust Report · `#/ui` gallery.

**v2 navigation.** A left **nav rail** on desktop (72px: icon above a micro label, active item on `blue-soft` with a blue icon) and a **bottom tab bar** on phones: Home, Ask, Overview, Analyses, Saved, Trust. Inside a project the rail shows the project's name at the top; outside one, only Home and Trust are enabled. The files / links / glossary panel stays beside the Ask page as a collapsible side panel (a drawer on phones), opened by a "Data" button in the page header.

### 6.1 Home (`#/`)
- **First visit (no projects):** the landing. Left: headline "Ask your spreadsheets. Verify every answer.", two lines of plain description, the drop zone, "Try with sample HR data". Right: a **static sample answer statement built from the real demo numbers** ("Engineering had the highest gross pay in 2025", ₹20.40 Cr, three ticks, three bars). The hero is the product's promise, shown, not described. Below: "How it works" as three numbered steps (it is a real sequence): Upload as-is → Ask in plain English → Check the working.
- **Returning (projects exist):** "Your projects" as ruled rows: name, file names, "12 questions, 3 saved", last opened. Row actions: open, rename, delete (confirm dialog says exactly what is deleted). Above the list: "New project" (opens the drop zone) and "Try with sample HR data". One quiet line under the list: "Projects are saved in this browser. Your files are never stored on our server."

### 6.2 Creating a project
Upload (or sample) → the project is created with a name taken from the first file ("Salary Register 2025 and 5 more"; sample = "Sample HR company"), renameable inline → workspace opens on the **briefing**.

### 6.3 Workspace (`#/p/<id>`)
- **Header:** brand (links home), project name (click to rename), "Saved answers (n)", privacy shield, Trust Report. On phones the secondary items collapse into one menu.
- **Sidebar (drawer under 768px):** an overview line ("7 tables, 5 links, 1 combined view, 4 personal-data columns hidden") then **tabs: Files · Links · Glossary**.
  - *Files:* ruled rows; each opens to the Data Health receipt as **itemised lines with right-aligned counts** ("Title rows skipped 3", "Total rows dropped 1", "Duplicate rows removed 6", "Unreadable amounts left empty 3"), plus "Preview rows" and the column list. A file that needs a look carries an amber mark and says why in one sentence.
  - *Links:* each as a sentence, "employees ↔ salary register on employee code. 93% of employees have pay records." with Keep / Remove; combined views listed the same way. A `WhatsThis` explains why links matter (wrong links double-count).
  - *Glossary:* intro sentence ("'Attrition' can be computed three ways. These are the definitions Verity uses. Change them to match your company."), then entries with editable definition and other names; Save says "Saved" and nothing else.
- **Main, empty thread = the briefing:** a sheet titled "Here's what I found in your files": four ticked lines (files read and cleaned, links found, files combined, personal data hidden from the AI) each expandable to the detail, then "Questions to start with" grouped by kind (Totals and breakdowns · Trends · Across files · HR measures). This is the product's strongest moment: do not bury it.
- **Thread:** the user's question right-aligned on `indigo-soft`; then the step list (collapses to "Worked through 8 steps" when done); then the answer statement.
- **Composer:** sticky at the bottom, one line growing to four, Enter to ask, Shift+Enter for a new line, `/` focuses it, Stop while running.

### 6.4 The answer statement
Order, top to bottom: headline sentence (Plex Serif 22) → `Figure` when the result is a single value → `ProofList` → chart / table toggle with "Download CSV" → "Keep in mind" (marginal notes with an amber left rule; plain sentences) → follow-up chips → actions row: "Save to board" (toggles to "Saved"), "How I got this".

`ProofList` lines are generated from the answer, never hard-coded:
- always: "Computed by a database from your files"
- `cross_check.agreed`: "A second AI model wrote its own query and got the same result" · `disagreed`: shown as a red `Banner` above the chart with the detail, not as a tick · `unavailable`/`skipped`: line omitted
- `metrics_used` non-empty: "Used your agreed definition of <metric name>"
- always, last: "No rows or personal data were sent to the AI", with a link "See exactly what was sent" that opens How I got this at that section
Confidence sits beside the headline as a `Badge`; its reasons open in a Popover.

Other kinds: **clarify** = the question, then option buttons, with a `WhatsThis`: "Why am I asking? 'Salary' matches three columns. Guessing would give you a confident wrong number." · **refusal** = what is missing and "What would make this answerable" · **error** = the server's sentence and nothing added to it, then Retry; when `retry_after_s` is set the button reads "Try again in 12 s", counts down, and enables itself at zero · **cached** = a quiet note "Same question, same data: answered from memory."

### 6.5 Saved answers board (`#/p/<id>/board`)
A printable report: project name and date as the title, then saved answers as full-width statements (headline, figure, chart, keep-in-mind; no controls). Reorder with up/down buttons, remove, "Print or save as PDF" (`window.print()` with a print stylesheet: paper white, no header/sidebar, charts kept together). Empty state: "Save an answer to build a report you can print."

### 6.6 Coming back (the re-attach flow)
Projects live in the browser; data lives in server memory and is dropped after two hours or a restart. On opening a project: `getCatalog`. If the session is gone (404):
- the thread and board still render from the saved record (read-only, fully viewable);
- a `Banner` explains: "Your files are no longer loaded. We never keep them. Re-attach them to ask new questions." with the expected file names listed and a drop zone; the sample project shows "Reload sample data" instead;
- after re-attaching: create a session, upload, re-apply the saved glossary (`saveGlossary`) and removed links (`setLinkStatus`), and carry on in the same thread.

### 6.7 Learning the product (all dismissible, all remembered)
- **First-run tour** (four steps, only in a workspace, only once): the Files tab ("What we cleaned and what we hid"), the composer ("Ask the way you would ask a colleague"), the first answer's How I got this ("Every answer shows its working"), Trust Report ("How often it is right, measured"). Skip at any step; re-run from the help menu.
- **"How Verity works"** dialog from the privacy shield: five numbered steps (a real sequence) and two columns: *What the AI sees* (column names, types, counts, ranges, short category labels such as "Bengaluru") and *What it never sees* (rows, names, emails, phone numbers, PAN, anyone's salary). Ends with "Check it yourself: open How I got this under any answer."
- **`WhatsThis`** on: confidence, cross-check, agreed definition, Data Health, links, combined views, the clarify question.
- **Writing good questions:** three examples under the composer when the thread is empty ("Name the period: 'in 2025', 'in FY25'", "Name the measure: 'gross pay', not 'pay'", "Ask a follow-up: 'now split that by location'").

## 7. Storage contract (`frontend/src/lib/projects.ts`)

```ts
interface ProjectRecord {
  id: string; name: string; createdAt: string; lastOpenedAt: string
  isSample: boolean
  fileNames: string[]            // what to re-attach
  sessionId: string | null       // server session, may have expired
  glossary: Metric[] | null      // only when edited
  removedLinkIds: string[]
  turns: { id: string; question: string; answer: Answer; askedAt: string }[]   // newest last, max 60
  savedAnswerIds: string[]       // order = board order
  tourDone?: boolean
}
```
`localStorage` key `verity.projects.v1`. Every read and write is wrapped in try/catch; the app works (without history) when storage is unavailable. To stay under the quota, a stored answer keeps at most 200 table rows (`table.truncated = true`) and drops `work.payloads[].messages` beyond the first payload. On quota error: drop the oldest turns of the largest project, then retry once. Deleting a project also calls `resetSession`-style `DELETE /api/sessions/{id}`.
`// ponytail: localStorage, ~5 MB. Move to IndexedDB if a project needs more than 60 turns.`

Nothing here touches the backend. The server keeps no record of projects, by design.

## 8. Words

Plain verbs, sentence case, no filler. Name things the way the analyst would: "files", "links between files", "combined view", "your agreed definition", "the working". Never: schema, join, fan-out, guard, payload, pipeline, LLM, token, session (say "your files are no longer loaded"). Table names appear as the file's name when one is known ("Salary Register 2025, sheet Register"), with the technical name only inside How I got this. Buttons say what happens ("Save to board", "Re-attach files", "Remove link"). Errors: what happened, then what to do.

## 9. Quality floor

Works at 390, 768 and 1280 wide. Keyboard-only use is complete; focus is always visible (2px indigo ring, 2px offset). Every control has a name. Contrast at least 4.5:1 for text. Charts have a table alternative one click away. No layout shift when an answer arrives. `pnpm typecheck` clean, no console errors, no CSP violations. The 30-second path (land → sample data → click a question → read the answer) must never get slower or longer.

## 10. Component seams (who owns what during the revamp)

Four engineers restyle in parallel after the primitives exist. These interfaces are fixed so the halves meet. Behaviour that works today (upload, links, glossary, preview rows, CSV download, clarify, follow-ups, How I got this, abort) must keep working.

```ts
// frontend/src/lib/projects.ts                      owner: journey
export interface Turn { id: string; question: string; answer: Answer; askedAt: string }
// ProjectRecord as in section 7. Exposes: listProjects, getProject, createProject, updateProject,
// deleteProject, and a useProject(id) hook returning [record, update].

// frontend/src/components/thread/Thread.tsx          owner: answers
export interface ThreadProps {
  sessionId: string | null            // null = files not loaded: history is readable, asking is off
  catalog: Catalog | null
  turns: Turn[]                       // controlled: the project record is the source of truth
  onTurnsChange: (turns: Turn[]) => void   // called when a turn completes (running turns stay local)
  savedAnswerIds: string[]
  onToggleSaved: (answerId: string) => void
  onSessionExpired: () => void
  emptyState: React.ReactNode         // the briefing, supplied by the workspace
  notice?: React.ReactNode            // e.g. the re-attach banner, rendered above the composer
}

// frontend/src/components/answer/AnswerStatement.tsx  owner: answers (replaces AnswerCard)
export interface AnswerStatementProps {
  answer: Answer
  mode: 'thread' | 'board'            // board: no controls, print-friendly
  saved?: boolean
  onToggleSaved?: () => void
  onAsk?: (question: string, clarification?: Record<string, string>) => void
}

// frontend/src/components/sidebar/Sidebar.tsx        owner: workspace
export interface SidebarProps {
  sessionId: string | null
  catalog: Catalog | null
  readOnly: boolean                   // files not loaded
  fileNames: string[]                 // from the project record, shown when catalog is null
  onCatalogChange: (catalog: Catalog) => void
  onGlossaryEdited: (glossary: Metric[]) => void
  onLinkStatusChanged: (linkId: string, status: 'active' | 'rejected') => void
  onAddFiles: () => void
}

// frontend/src/components/workspace/Briefing.tsx     owner: workspace
export interface BriefingProps { catalog: Catalog; onAsk: (question: string) => void }

// frontend/src/components/education/                 owner: education
//   Tour.tsx              <Tour run onDone />  anchors by data-tour="files|composer|working|trust"
//   HowItWorksDialog.tsx  <HowItWorksDialog open onClose />
//   explain.ts            export const EXPLAIN: Record<'confidence'|'crossCheck'|'definition'|
//                         'dataHealth'|'links'|'combined'|'clarify', { title: string; body: string }>
//   (WhatsThis itself is a primitive in components/ui; everyone imports the copy from explain.ts)
```

| Owner | Files |
|---|---|
| foundation (runs first, alone) | `src/index.css`, `src/components/ui/**`, `public/fonts` wiring, print stylesheet |
| journey | `src/App.tsx`, `src/lib/projects.ts`, `src/lib/route.ts`, `src/components/home/**`, `src/components/board/**`, `src/components/shell/**`, `src/components/upload/**` except `Landing.tsx` |
| answers | `src/components/thread/**`, `src/components/answer/**`, `src/components/charts/**`, `src/lib/format.ts`, `src/lib/csv.ts`, `src/lib/tables.ts` |
| workspace | `src/components/sidebar/**`, `src/components/workspace/**` |
| education | `src/components/education/**`, `src/components/upload/Landing.tsx` (the hero), `src/pages/TrustReport.tsx` |

Anchors other owners must place: `data-tour="files"` on the Files tab (workspace), `data-tour="composer"` on the composer and `data-tour="working"` on the first How I got this (answers), `data-tour="trust"` on the Trust Report link (journey). `api.ts` and `types.ts` stay Lead-owned.


## 11. v2: Thinking, made visible (owner: answers)

While a question runs, under the analyst's question bubble: a card titled "Working on it" with `ProgressSteps` using these labels: Understanding the question · Writing the query · Checking the query is safe · Running it on your data · Fixing the query (only when a repair happens) · Double-checking with a second AI model · Choosing a chart · Writing the answer. Each active step shows the server's live detail text under its label ("Read-only, 2 tables, 3 columns"), an elapsed timer runs in the card header, and the model's name appears as a chip once known. A `warn` step event whose detail starts with "All the free AI models are busy" puts the step into the amber `waiting` state with the countdown. Stop sits in the card. Below it, a skeleton of the answer card. When the answer arrives the card collapses into one line, "Answered in 3.2 s, 7 checks", which expands to the full timeline.

## 12. v2: The answer card (owner: answers)

Top to bottom: headline sentence (card title style) with the confidence `Badge` beside it → `StatTile` hero figure when the result is one value → `VerifiedList` (lines generated from the answer exactly as in 6.4) → **insight chips** from `answer.insights` (computed by the server, never by a model) → the visual: a `SegmentedControl` of the chart types that fit the result's shape (category + measure: bar, donut when ≤ 6 groups, table · date + measure: line, area, bar, table · two categories + measure: grouped, stacked, heatmap, table · two measures: scatter, table), plus Download CSV and an expand-to-dialog button → "Keep in mind" as an amber-soft banner list → follow-up chips → actions: Save, Copy answer, How I got this.

**How I got this** opens with a small **flow**: Question → Query written by `<model>` → Safety check → Your data (DuckDB) → Second model check → Answer, each node a pill with its status colour and a connecting line; attempts that were repaired show as a loop back on the query node. Under it, the sections that exist today (how I read your question, plan, data used, assumptions, SQL with copy, attempts, what the model saw).

**Charts** (Recharts; load the `dataviz` skill): bars go horizontal when any label is longer than 10 characters; area charts fill from the series colour at 24% to 0%; donut shows the total in the centre and at most 6 slices (the rest as "Other"); histogram bars touch; heatmap is a CSS grid on the `blue-soft → blue` scale with a legend and values on hover; one tooltip card style everywhere (`surface`, `shadow-3`, micro text, tabular numerals); legend as chips; Indian number formatting through `lib/format.ts`; first-render animation only. Every chart has the table one click away.

## 13. v2: Overview, the automatic dashboard (owner: overview)

`#/p/<id>/overview`, data from `getDashboard(sessionId)` (`Dashboard` in `types.ts`; fixture `dashboard.json`). Computed on the server by templates: no AI, instant, identical every time, and it works while the models are rate limited. Say so once, in a quiet line under the title: "Computed from your files. No AI involved."

Layout: page title "Overview", then each `DashboardSection` as a heading with its description and a responsive grid: KPI tiles four across (two on phones), chart tiles two across (one on phones), two-way tiles full width. A tile is a `Card`: title, statement (small, `ink-2`), chart, insight chips, and a menu: "Ask about this" (sends `tile.ask` to the Ask page and navigates there), "Save to board", "View table and SQL" (dialog), "Download CSV". The quality tile is a checklist, not a chart. Loading = a skeleton grid; then tiles stagger in. Files not loaded = the re-attach banner. Empty = "Upload files to see an overview."

## 14. v2: Analyses, guided and AI-free (owner: analyses)

`#/p/<id>/analyses`, data from `getAnalyses` and `runAnalysis` (fixtures `analyses.json`, `tile.json`). Left (top on phones): a gallery of analysis kinds as interactive cards (icon, name, one-line description, example in `ink-2`). Choosing one opens its form: one picker per input (native `<select>` with `<optgroup>` per file, only columns whose kind the input accepts), options as `SegmentedControl`s, a live sentence preview of what will run ("Average Annual CTC by Department"), and Run. The result renders as the same tile card as Overview, with Save to board, Download CSV and "Continue in chat" (sends `tile.ask`). Runs made in this visit are listed under the result as chips to reopen. A 422 from the server shows its sentence in a `Banner` beside the offending picker. A quiet line: "No AI needed: you choose the columns, the database does the rest."

## 15. v2: Home, Saved, sample data (owner: journey)

Home lists projects as interactive cards (name, file chips, "12 questions, 3 saved", last opened) with a primary "New project" button; the sample project card carries "See what's inside" (a dialog listing the files from `GET /api/sample/files` with their one-line descriptions and a download link each) and "Download all (zip)" (`/api/sample/download`). The Saved board accepts both saved answers and saved tiles, reorders with up/down buttons, and prints (`window.print()`): the print stylesheet removes the rail, header and controls and keeps each card whole.
