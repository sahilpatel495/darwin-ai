// The three hints that replaced the tour (§7).
//
// There was a six-step coach-mark tour here. It held the page hostage before anyone had a reason
// to care about the answer, so people dismissed it without reading and learned nothing. These
// three lines appear once each, beside the thing they explain, at the moment it first matters,
// and then never again. Three is the whole budget; a fourth is a sign something on the screen is
// not explaining itself.
//
// The copy rule is §12's: one sentence, the analyst's words, and it says what the thing is for —
// not where to click. No runtime imports: education.test.mjs loads this file directly.

export type TipId = 'data-button' | 'how-i-got-this' | 'overview-tab'

export interface TipCopy {
  id: TipId
  /** Who renders it, so the three owners can find their own without reading this file. */
  where: string
  /** One line. The `Tip` primitive puts "Got it" beside it. */
  text: string
}

export const TIPS: Record<TipId, TipCopy> = {
  'data-button': {
    id: 'data-button',
    where: 'ProjectShell, under the top bar, the first time a project has files.',
    text: 'Data holds your files: what was cleaned while they were read, and which columns are kept away from the AI.',
  },
  'how-i-got-this': {
    id: 'how-i-got-this',
    where: 'Thread, under the first real answer in a project.',
    text: 'Open “How I got this” to see the question as it was read and the query that produced this number.',
  },
  'overview-tab': {
    id: 'overview-tab',
    where: 'ProjectShell, under the Overview tab, once the first answer has arrived.',
    text: 'Overview fills itself in from your files, with no question to write and no AI involved.',
  },
}

/** The three in the order an analyst meets them. */
export const TIP_ORDER: TipId[] = ['data-button', 'how-i-got-this', 'overview-tab']
