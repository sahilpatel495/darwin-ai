// The first-run tour's words, its anchors and its one piece of arithmetic, kept out of the
// component so all three can be read and tested without a browser (education.test.mjs).
// No runtime imports.

/** What each step points at. Other owners place `data-tour="files"` and so on (§10). */
export type TourAnchor = 'files' | 'composer' | 'working' | 'overview' | 'analyses' | 'trust'

export interface TourStep {
  anchor: TourAnchor
  /**
   * Where else to look, when nothing carries `data-tour="<anchor>"`. The nav rail is built from a
   * plain list of links in App.tsx, so the tour finds its rail items by where they go rather than
   * asking another owner to mark six anchors it can work out for itself.
   */
  fallback?: string
  title: string
  body: string
}

/** Six steps, in the order the analyst meets them (§6.7). A step with no anchor on screen is skipped. */
export const TOUR_STEPS: TourStep[] = [
  {
    anchor: 'files',
    title: 'What we cleaned and what we hid',
    body: 'Open a file here to read every change made while it was loaded, counted line by line, and the personal-data columns that are kept away from the AI.',
  },
  {
    anchor: 'composer',
    title: 'Ask the way you would ask a colleague',
    body: 'Plain English is enough: "gross pay by department in 2025". Name the period and the measure and you will need fewer follow-ups.',
  },
  {
    anchor: 'working',
    title: 'Every answer shows its working',
    body: 'This opens the question as Verity read it, the query that ran, and exactly what was sent to the AI. Use it before you put a number in front of anyone.',
  },
  {
    anchor: 'overview',
    fallback: 'nav a[href$="/overview"]',
    title: 'The numbers you did not have to ask for',
    body: 'Overview is a dashboard your files fill in by themselves: headline figures, breakdowns, trends and data quality. Nothing on it is written by an AI.',
  },
  {
    anchor: 'analyses',
    fallback: 'nav a[href$="/analyses"]',
    title: 'Run an analysis by picking columns',
    body: 'Analyses lets you choose the measure and the grouping yourself, so there is no wording to get right. The database does the work, the same way every time.',
  },
  {
    anchor: 'trust',
    fallback: 'nav a[href="#/trust"]',
    title: 'How often it is right, measured',
    body: 'The Trust Report scores Verity on a fixed set of questions whose correct answers were worked out separately from the app. Failures are listed, not hidden.',
  },
]

/** The selectors for one step, best first: the placed anchor, then wherever else it may live. */
export function anchorSelectors(step: TourStep): string[] {
  return step.fallback ? [`[data-tour="${step.anchor}"]`, step.fallback] : [`[data-tour="${step.anchor}"]`]
}

/** The bits of a DOMRect the placement needs. Spelled out so the test needs no DOM. */
export interface Box {
  top: number
  left: number
  width: number
  height: number
}

/**
 * Where to put the tour panel for an anchor: below it when there is room, above it when there is
 * not, and always fully on screen. A panel half off the right edge of a phone is a tour that
 * cannot be finished, so the clamp matters more than the preference.
 */
export function placePanel(anchor: Box, panel: { width: number; height: number }, viewport: { width: number; height: number }, gap = 12, margin = 8): { top: number; left: number } {
  const left = Math.max(margin, Math.min(anchor.left, viewport.width - panel.width - margin))
  const below = anchor.top + anchor.height + gap
  const fitsBelow = below + panel.height + margin <= viewport.height
  const top = fitsBelow ? below : Math.max(margin, anchor.top - gap - panel.height)
  return { top, left }
}
