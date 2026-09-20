// The first-run tour's words and its one piece of arithmetic, kept out of the component so both
// can be read and tested without a browser (education.test.mjs). No runtime imports.

/** The anchors other owners place: `data-tour="files"` and so on (§10). */
export type TourAnchor = 'files' | 'composer' | 'working' | 'trust'

export interface TourStep {
  anchor: TourAnchor
  title: string
  body: string
}

/** Four steps, in the order the analyst meets them (§6.7). A missing anchor is skipped. */
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
    anchor: 'trust',
    title: 'How often it is right, measured',
    body: 'The Trust Report scores Verity on a fixed set of questions whose correct answers were worked out separately from the app. Failures are listed, not hidden.',
  },
]

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
