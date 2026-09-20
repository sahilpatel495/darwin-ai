# Verity — UX and design system ("Ledger")

The contract for everyone touching the frontend. Read it before writing UI. `docs/DESIGN.md` says what the product does; this says how it feels and how a person moves through it.

## 1. Who, and the one idea

**Who:** an HR analyst who must put a number in front of their CHRO, and the hiring panel watching over their shoulder. Neither reads documentation.

**The idea:** the subject is a payroll ledger, so the interface borrows the vocabulary of accounts: ruled lines, right-aligned tabular figures, the auditor's tick, and the **double rule under a total**. An answer is presented as an *audited statement*: a sentence, a figure, and ticked proof.

**Where the boldness goes (one place only):** the answer statement: large serif figure, double rule beneath it, ticks that draw in when the answer arrives. Everything else is quiet.

## 2. Tokens

Defined once in `frontend/src/index.css` under `@theme`; components use the token classes, never raw hex.

| Token | Hex | Use |
|---|---|---|
| `paper` | `#FAF8F3` | page background |
| `sheet` | `#FFFFFF` | the answer statement, dialogs, the composer |
| `wash` | `#F3EFE6` | code, table header, hover on paper |
| `rule` | `#E4DFD3` | hairlines, borders |
| `rule-strong` | `#C9C2B2` | the double rule, table header rule |
| `ink` | `#1B1B2F` | text |
| `ink-soft` | `#54546B` | secondary text |
| `ink-faint` | `#8C8CA1` | hints, disabled |
| `indigo` | `#2F3A8F` | actions, links, focus, first chart series |
| `indigo-soft` | `#E9EBF7` | selected, user's question bubble |
| `indigo-ink` | `#1F2766` | hover/pressed |
| `audit` | `#1F7A4D` | ticks, verified, high confidence |
| `audit-soft` | `#E3F2EA` | |
| `amber` | `#9A5B00` | needs a look, medium confidence, caveats |
| `amber-soft` | `#FBF0D9` | |
| `red` | `#A32A2A` | errors, low confidence, disagreement |
| `red-soft` | `#F9E3E3` | |
| chart series | `#2F3A8F` `#1B7F79` `#B07A1E` `#7A3B8F` `#B0435E` | in this order |

Radius: `4px` controls and sheets, `2px` chips, `999px` never. Shadows: none on paper; dialogs and popovers only (`0 12px 32px rgb(27 27 47 / 0.14)`). Hierarchy comes from rules and whitespace, not from cards: sidebar items are **ruled rows**, not boxes. The answer statement is the only white sheet in the thread.

## 3. Type

Self-hosted in `frontend/public/fonts` (the app's CSP blocks font CDNs). Declare **both** `latin` and `latin-ext` files with `unicode-range`; the ₹ sign lives only in `latin-ext`.

| Role | Face | Size / line / weight |
|---|---|---|
| Figure (the number) | IBM Plex Serif | 48/52, 600, `tabular-nums lining-nums`, `letter-spacing: -0.01em` |
| Page headline | IBM Plex Serif | 40/46, 600 (28/34 on phones) |
| Statement headline | IBM Plex Serif | 22/30, 500 |
| Section title | IBM Plex Sans | 15/22, 600 |
| Body | IBM Plex Sans | 15/24, 400 |
| Small | IBM Plex Sans | 13/20, 400 |
| SQL and code only | IBM Plex Mono | 13/20, 400 |

Rules: sentence case everywhere; no all-caps labels; no eyebrow labels above headings; no monospace for data labels; no single accented word in a headline; text left-aligned; numerals in tables right-aligned with `tabular-nums`; measure under 72 characters.

## 4. Motion

One orchestrated moment: when an answer arrives, its ticks draw in one after another (SVG `stroke-dashoffset`, 160 ms each, 90 ms stagger) and the double rule extends left to right (240 ms). Step-list items swap their spinner for the same tick. Dialogs and popovers fade in 120 ms. Nothing else animates on its own: no entrance animations on sections, no hover lifts. `prefers-reduced-motion`: everything is instant.

## 5. Primitives (`frontend/src/components/ui/`)

Built first, used by every screen. Small, typed, accessible, no dependencies.

- `Button` (`primary` indigo fill · `secondary` rule border on sheet · `quiet` text only; sizes `md`, `sm`; loading state keeps its width)
- `Tick` (the hand-drawn auditor's tick as an SVG path; `animate` prop) and `ProofList` (ticked statements, plain text, not pills)
- `Figure` (big serif number + the double rule; takes the display string and an optional label under it)
- `Sheet` (white surface with a 1px rule; `as` prop), `RuledRow` (row on paper with a bottom rule)
- `Tabs` (roving tabindex, arrow keys), `Dialog` (native `<dialog>`, focus trapped, Esc closes, labelled), `Popover` / `WhatsThis` (a small "?" button that opens a two-sentence explanation; click and keyboard, not hover-only)
- `Banner` (`info`, `warn`, `error`: message + next step + optional action), `Skeleton`, `EmptyState` (one sentence + one action), `Chip` (suggested questions, follow-ups)
- `Badge` for confidence only: a small square of colour + the words "High confidence"; the reasons open in a Popover

## 6. The journey

Hash routes, no router library: `#/` home · `#/p/<projectId>` workspace · `#/p/<projectId>/board` saved answers · `#/trust` Trust Report.

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
