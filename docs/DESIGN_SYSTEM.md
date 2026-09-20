# Verity — UX and design system v3 ("Canvas")

The contract for everyone touching the frontend. Read all of it before writing UI.

> **Why v3.** v1 ("Ledger": warm paper, serif) looked like another product's interface. v2 ("Clarity") fixed that and still read as a 2010 admin panel: small system type, dense grey chrome, a left rail plus a left data panel, a composer nobody noticed with a paragraph of tips under it, a coach-mark tour that annoyed people, low-contrast dark mode. v3 adopts the owner's supplied token language (a stark white canvas, big confident geometric type, pills everywhere, 24 to 32px radii, hairlines instead of shadows, a black pill for general calls to action with cobalt reserved for the core action) and rebuilds the flow around it. The behaviour, storage and data contracts from earlier passes stay; the skin, the information architecture and the first five minutes change completely.

## 1. Who it is for, and how it should feel

An HR analyst who has to put a number in front of their CHRO, and a hiring panel judging it in a short demo. It should feel like the best consumer-grade AI products of 2026, not like an internal tool: **one obvious thing to do on every screen, huge legible type, lots of air, generated graphics where a marketing site would use photography, and motion that makes the product feel alive.** Reference class: Perplexity, Linear, Arc, Granola, v0. Test for every screen: would a design-literate person screenshot this because it looks good?

Three moments carry the product and get the boldness: **the composer** (asking is the product), **the answer** (a headline number you can trust, with its proof), and **the first five minutes** (landing → account or guest → onboarding that teaches by doing).

## 2. Tokens (`frontend/src/index.css`, `@theme`; light only)

Light is the only theme in v3: remove dark tokens, the ThemeToggle and any `prefers-color-scheme` branch, and set `color-scheme: light`. One theme, designed properly.

| Token | Value | Use |
|---|---|---|
| `canvas` | `#FFFFFF` | page and card surface |
| `surface-soft` | `#F1F4F7` | soft tiles, search pill, input rest, code |
| `hairline` | `#CBD2D9` | input borders |
| `hairline-soft` | `#DEE3E9` | card borders, dividers |
| `ink-deep` | `#0A1317` | headlines, primary text, black pill buttons |
| `ink` | `#1C2B33` | body |
| `charcoal` | `#344854` | tertiary text |
| `slate` | `#465A69` | supporting copy |
| `steel` | `#5D6C7B` | captions |
| `stone` | `#8595A4` | disabled, separators |
| `primary` | `#0064E0` | **the core action only**: Ask, Run, Continue in onboarding; focus ring; first chart series |
| `primary-deep` | `#0143B5` | pressed, selected borders, links |
| `primary-soft` | `rgb(0 100 224 / .12)` | informational tint, the analyst's question bubble |
| `purple` | `#7B3FE4` | second accent in graphics and charts |
| `success` | `#007D1E` · soft `#E1F5E5` | verified, high confidence |
| `attention` | `#B45F06` · soft `#FFF1DF` | medium confidence, caveats, waiting |
| `warning` | `#FFD60A` | the promo strip only |
| `critical` | `#C80A28` · soft `#FDE8EB` | errors, low confidence, disagreement |
| chart series | `#0064E0` `#7B3FE4` `#00A38D` `#F2781F` `#E0457B` `#5D6C7B` | in order; heatmap scale `#E8F1FD → #0064E0` |

Radius: `xs 2` · `sm 4` · `md 6` · `lg 8` (inputs) · `xl 16` (small tiles, accordion items) · `xxl 24` (standard cards, the docked composer) · `xxxl 32` (hero frames, showcase cards, the hero composer) · `feature 40` · `full 100px` (every button, chip, tab and badge: a squared button is a bug) · `circle 50%`.
Elevation: flat by default (`1px solid hairline-soft`, no shadow). Level 1 `1px 1px 0 rgb(0 0 0 / .2)` for the active pill tab. Level 2 `0 1px 4px rgb(20 22 26 / .3)` for the sticky composer, drawers and menus. Dialogs: level 2 plus a `rgb(10 19 23 / .4)` scrim. Nothing else casts a shadow.
Spacing (4px grid): `4 8 10 12 16 20 24 32 40 48 64 80 120`. Card padding 32 (24 on phones). Sections 64 to 80 apart on marketing pages, 32 to 48 in the app. Content max width 1200 on marketing, 1120 in the app, 820 for the conversation column.

## 3. Type

**Montserrat variable** (self-hosted: `frontend/public/fonts/montserrat-latin-wght.woff2` and `montserrat-latin-ext-wght.woff2`; declare BOTH with `unicode-range`, the ₹ sign lives only in latin-ext; `font-display: swap`; preload the latin file). It stands in for the owner's reference face, which is proprietary. Fallbacks: `Helvetica, Arial, "Noto Sans", sans-serif`. Headings set `font-feature-settings: "ss01", "ss02"`. Code only: `ui-monospace, SFMono-Regular, Menlo, monospace`. Delete every other font file and preload.

| Role | Size / line | Weight | Tracking | Use |
|---|---|---|---|---|
| `hero-display` | 64 / 1.16 | 500 | 0 | landing hero (36 under 768, 28 under 480) |
| `display-lg` | 48 / 1.17 | 500 | 0 | section openers, the Ask empty-state greeting (32 on phones) |
| `heading-lg` | 36 / 1.28 | 500 | 0 | page titles, hero figures in tiles and answers (tabular numerals) |
| `heading-md` | 28 / 1.21 | 300 | 0 | editorial subheads (the light weight is the rhythm) |
| `heading-sm` | 24 / 1.25 | 500 | 0 | card titles, the answer headline |
| `subtitle-lg` | 18 / 1.44 | 700 | 0 | callouts, FAQ questions |
| `subtitle-md` | 18 / 1.44 | 400 | 0 | lead paragraphs |
| `body-md` | 16 / 1.5 | 400 | -0.16px | body |
| `body-sm` | 14 / 1.43 | 400 · bold 700 | -0.14px | secondary text, pill tabs, buttons (`button-md` = 14/700) |
| `caption` | 12 / 1.33 | 400 · bold 700 | 0 | badges, axis labels, fine print |

Sentence case. No all-caps labels, no eyebrow labels. Numerals in tables right-aligned with `tabular-nums`.

## 4. Motion and graphics

Durations `150–250ms` ease-out for surface changes, `300ms` ease-in-out for accordions and drawers, `400–600ms` for charts and count-ups; one spring-like curve for presses and reveals: `cubic-bezier(.2,.8,.2,1)`. Everything vanishes under `prefers-reduced-motion`.
- Page change: incoming content fades and rises 12px. Bento and card grids stagger in (50ms apart, first 9, once). Press = scale `.97`. Pill-tab indicator slides. Drawer slides from the right with the scrim fading.
- The composer: focus grows its ring and lifts it; the placeholder cycles through real example questions with a typewriter effect when empty and unfocused.
- Thinking: a shimmering gradient sweeps the active step's text; finished steps check with a pop; the waiting state pulses amber with a countdown.
- Answer: skeleton cross-fades; the hero figure counts up; verified lines check in sequence; the chart draws.
- Onboarding "reading your files": each stage ticks in turn with its count rolling up; a progress ring closes; the workspace reveal scales in.
**Graphics kit (`components/graphics/`, no stock photos, no external assets):** `AuroraBackdrop` (slow-drifting radial gradients in cobalt, purple and ice at low alpha over white, with a fine grain overlay: the signature background for heroes, auth and onboarding), `AppPreview` (a live miniature of a real answer card that animates in a loop: question types itself, steps check, figure counts up, bars grow; it is the landing hero "photograph"), `Glyph` set (24 to 64px duotone line illustrations: bars, trend, donut, table, shield, link, sparkles, upload, lock, receipt) used in feature tiles, empty states and the analysis gallery.

## 5. Primitives (`components/ui/`)

`Button` variants: `primary` (black pill: `ink-deep` fill, white text, 14/700, padding 14×30), `action` (cobalt pill, same metrics, **only** for Ask / Run / Continue / Create account), `secondary` (2px `ink-deep` outline), `ghost` (2px `rgb(10 19 23 / .12)` outline), `quiet` (text only); sizes `md` 44px, `sm` 36px; loading keeps width. `IconButton` (40px circle). `PillTabs` (inactive: canvas + hairline border; active: `ink-deep` fill, white text, level-1 shadow; sliding indicator). `Card` (`tone`: canvas | soft | dark; `radius`: xl | xxl | xxxl; hairline-soft border; never a shadow). `Input`, `Select`, `Textarea` (44px, radius lg, hairline; focus = 2px primary; error = critical border + message). `Badge` (pill, caption-bold: success / attention / critical / neutral / promo). `Chip` (pill; suggestions, follow-ups, insights). `Drawer` (right slide-over, 480px, full width on phones), `Dialog`, `Menu`, `Popover`, `Tooltip`, `Toast`, `Accordion`, `Skeleton`, `EmptyState` (glyph + one sentence + one action), `StatTile` (count-up), `Check` + `VerifiedList`, `ProgressSteps`, `ProgressRing`, `Banner`, `Kbd`, `Avatar`, `UsageMeter`, `Tip` (a one-line contextual hint that appears once beside the thing it explains and is dismissed forever; this replaces the tour). Gallery at `#/ui`.

## 6. Information architecture

Hash routes: `#/` landing (signed-out) or home (signed-in) · `#/signin` · `#/signup` · `#/welcome` onboarding · `#/home` projects · `#/p/<id>` ask · `#/p/<id>/overview` · `#/p/<id>/analyses` · `#/p/<id>/board` saved · `#/how` how Verity works · `#/trust` · `#/settings` · `#/ui`.

**App chrome = one sticky top bar, 64px, canvas, hairline-soft bottom border. No left rail, no permanent side panel.** Left: wordmark, then the project switcher (name + chevron menu: recent projects, all projects, new project). Centre: `PillTabs` Ask · Overview · Analyses · Saved. Right: a search pill "Search or ask…" with `⌘K` (opens the command palette: jump to a page or project, re-ask a recent question, start an analysis), a **Data** button with a count badge (opens the Data drawer), the avatar menu (Profile and usage, How Verity works, Trust report, Sign out / Create account for guests). Phones: wordmark + Data + avatar on top, a bottom tab bar for the four tabs.

**The Data drawer** holds what used to be the left panel: pill tabs Files · Links · Glossary; files as rows that open to the Data Health receipt (itemised lines, counts right-aligned), Preview rows, links as sentences with Keep / Remove, the glossary editor, Add files.

Session expiry is handled in ONE place (the app shell): any API call that reports the project's files are no longer loaded switches the whole project into the read-only / re-attach state with one banner; no page invents its own error for it.

## 7. The first five minutes

**Landing (`#/`, signed-out).** A marketing page in the owner's token language. Top: a dark promo strip ("Runs on open-weight models. Your rows never reach the AI."). Nav: wordmark, pill links (How it works, Trust, Sign in), black pill "Get started". Hero: `hero-display` headline "Ask your spreadsheets. Verify every answer.", a `subtitle-md` line, dual call to action, **"Try the live demo" (black pill, signs in as a guest and loads the sample company: zero friction, this is the evaluator's path)** and "Create an account" (outline), and beneath it the `AppPreview` inside a `xxxl` frame on the `AuroraBackdrop`. Then: a three-up of feature cards with glyph art (Messy files, read properly · Every number computed, not generated · Your rows never reach the AI); a dark `xxxl` showcase card "See the working" with the question → query → safety check → database → second model → answer flow animating; a row of proof numbers read from the eval report (accuracy, holdout, questions tested, rows sent to the AI: 0); "How it works" in three numbered steps; an FAQ accordion (privacy, which models, which files, limits, is it free); a footer.
**Auth (`#/signin`, `#/signup`).** Split layout: form left (name, work email, password with show/hide and a plain rule, role chips), `AuroraBackdrop` art with one rotating proof line right (stacked on phones). Inline errors in sentences. "Continue as guest" is always visible. A guest who signs up keeps their projects.
**Onboarding (`#/welcome`, once, skippable at every step, three steps with a progress ring):** 1) "What should we call you, and what do you do?" (name prefilled, role chips: HR analyst, HR business partner, Payroll, Finance, Founder, Other; the role tunes the suggested questions). 2) "Bring your data": the drop zone, "Use the sample company", "See what's inside" (file list with descriptions and downloads). 3) "Reading your files": the animated sequence that IS the education: Reading → Cleaning (title rows, totals, ₹ amounts, dates) → Finding links → Hiding personal data from the AI, each ticking with its real counts from the catalog, then "Your workspace is ready" with the three best first questions as cards and "See the overview".
There is no coach-mark tour. After onboarding, education is `Tip`s (once each: the Data button, the first answer's "How I got this", the Overview tab) and the `#/how` page.

## 8. The app

**Ask, empty.** Centred, generous: `display-lg` greeting ("What do you want to know, Sahil?"), then the **hero composer**: a `xxxl` rounded, level-2 elevated box, 3 lines tall, placeholder cycling real examples, a row inside it with a "Data: 7 files" chip (opens the drawer), a model status dot with tooltip, and the cobalt pill **Ask** (with `↵`). Under it, **four suggestion cards** (glyph, kind label, the question in `body-md`; role-aware; card press asks immediately) and a quiet "More ideas" link that opens a sheet of questions grouped by kind. Nothing else: no paragraph of tips (a small "?" in the composer opens a popover with the three writing tips).
**Ask, in conversation.** An 820px column. The analyst's question in a `primary-soft` bubble, right-aligned. The thinking card, then the answer card. The composer docks to the bottom as a floating `xxl` pill bar with a blurred translucent backdrop and level-2 elevation, clearly separated from the page, with one quiet hint ("Enter to ask") that disappears after the first question.
**Answer card** (`xxl`, hairline, 32px padding): confidence `Badge` and the headline (`heading-sm`); the hero figure (`heading-lg`, count-up) when the result is one value; `VerifiedList`; insight `Chip`s; the visual, large, with a `PillTabs` chart-type switcher and the table one tap away; "Keep in mind" as an `attention`-soft block; follow-ups as chips under an "Ask next" label; a compact icon toolbar with tooltips (Save, Copy, Download CSV, Expand, How I got this). Clarify = the question plus option pills. Refusal = what is missing and what would make it answerable. Error = the server's sentence, a countdown on Retry when `retry_after_s` is set.
**Overview.** `heading-lg` title with a `success` badge "No AI involved". Sticky pill tabs for the sections. A **bento grid**: KPI tiles (`heading-lg` numerals, a sparkline when the section has a trend) mixed with 2×1 and 2×2 chart tiles and full-width two-way tiles; tile actions appear on hover/focus as icon buttons (Ask about this, Save, Table and SQL, CSV); stagger reveal; skeleton bento while loading.
**Analyses.** A gallery of analysis kinds as glyph cards, then a **sentence builder**, not a form: "Show me the [average ▾] of [Annual CTC ▾] by [Department ▾]" with inline pill selects, options as pill tabs, a live title preview and the cobalt pill **Run**. The result renders as a tile card below with Save, CSV and "Continue in chat". Runs from this visit sit in a row of chips. A `success` badge "No AI needed".
**Home (`#/home`).** Greeting, a "New project" black pill, projects as `xxl` cards (name, file chips, counts, last opened, a tiny sparkline of activity), the sample company card with "See what's inside" and "Download all".
**Saved.** A printable report: title, date, saved answers and tiles as full-width cards, reorder, remove, "Print or save as PDF".
**Settings (`#/settings`).** Profile (name, role), usage (`UsageMeter`: questions left this hour and today, from `getMe()`), "Delete my data" (projects in this browser and the server session), Sign out; for guests, a card inviting them to create an account to keep their place.
**How Verity works (`#/how`)** and **Trust (`#/trust`)** are full pages in the marketing language, reachable signed-in or out.
**States.** Every empty state has a glyph, one sentence and one action. Every error says what happened, then what to do. A backend that does not know a route answers with a JSON 404 whose next step is "Restart the server, then reload the page": show that sentence, never "could not be computed".

## 9. Auth contract (backend `app/auth.py`; types in `types.ts`; calls in `api.ts`)

`User { id, kind: 'guest' | 'member', name, email | null, role | null, created_at, onboarded }` · `Usage { asks_this_hour, asks_per_hour, asks_today, asks_per_day }`.
`POST /api/auth/guest → { token, user }` · `POST /api/auth/signup { email, password, name, role? } → { token, user }` (sent with a guest token, it upgrades that guest and keeps their sessions; 409 with a sentence if the email exists) · `POST /api/auth/login { email, password } → { token, user }` (401 with one sentence for any failure) · `GET /api/auth/me → { user, usage }` · `PATCH /api/auth/me { name?, role?, onboarded? } → user` · `DELETE /api/auth/me → 204` · `POST /api/auth/logout → 204`.
Every `/api/sessions…` route needs `Authorization: Bearer <token>` and the session must belong to that user (401 / 403 in the human error shape). `/api/sample/*`, `/api/eval/report` and `/healthz` stay public. `api.ts` stores the token, attaches it everywhere, silently obtains a guest token when there is none, and keeps working (without a token) against a server that does not have the auth routes yet.
Honest limits, stated in the README: accounts live in a SQLite file that a free host wipes on redeploy; there is no email verification or password reset because there is no mail service; passwords are hashed with scrypt; tokens are HMAC-signed and expire in 7 days.

## 10. Storage contract (`frontend/src/lib/projects.ts`), unchanged except the key

Projects, history and saved items live in the browser, per user: key `verity.projects.v1.<userId>`; a guest who signs up keeps the same id, so nothing moves. Records, trimming and quota rules are as built (max 60 turns, stored answers trimmed to 200 table rows, saved tiles max 24). `tourDone` is dropped; `tipsSeen: string[]` is added.

## 11. Ownership for the v3 build

| Owner | Files |
|---|---|
| foundation (first, alone) | `src/index.css`, `index.html`, `public/fonts` wiring, `src/components/ui/**`, `src/components/graphics/**`, `src/lib/motion.ts`, and for this stage only `src/App.tsx` + `src/lib/route.ts` to add the v3 routes with placeholders |
| first-five-minutes | `src/components/marketing/**`, `src/components/auth/**`, `src/components/onboarding/**`, `src/components/education/**` (the tour is deleted; `Tip` content lives here), `src/pages/HowItWorks.tsx`, `src/pages/TrustReport.tsx` |
| ask | `src/components/thread/**`, `src/components/answer/**`, `src/components/charts/**`, `src/lib/format.ts`, `src/lib/csv.ts`, `src/lib/tables.ts` |
| insights | `src/components/overview/**`, `src/components/tiles/**`, `src/components/analyses/**` |
| journey | `src/App.tsx`, `src/lib/route.ts`, `src/lib/projects.ts`, `src/lib/session.ts` (auth state around `api.ts`), `src/components/shell/**` (TopBar, ProjectSwitcher, CommandPalette, AvatarMenu, MobileTabBar), `src/components/home/**`, `src/components/board/**`, `src/components/settings/**`, `src/components/upload/**` |
| data | `src/components/sidebar/**` (becomes the Data drawer), `src/components/workspace/**` |
`types.ts`, `api.ts` and `fixtures/` stay Lead-owned.

## 12. Words and the quality floor

Sentence case, plain verbs, the analyst's vocabulary: files, links between files, combined view, your agreed definition, the working. Never: schema, join, fan-out, guard, payload, pipeline, LLM, token, session. Buttons say what happens. Works at 390, 768 and 1280 wide; keyboard-complete; visible 2px `primary` focus ring with 2px offset; names on every control; 4.5:1 text contrast; charts have the table one tap away; no layout shift when an answer arrives; `pnpm typecheck`, `pnpm test`, `pnpm build` clean; no console errors, no CSP violations (strict CSP: everything self-hosted). The 30-second path must hold: land → "Try the live demo" → click a suggestion card → read the answer.
