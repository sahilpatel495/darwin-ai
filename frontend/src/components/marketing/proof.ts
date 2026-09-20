// The landing page's row of proof numbers (§7), read from the accuracy report.
//
// Nothing here is a claim the product makes about itself: three of the four figures come from
// eval/report.json, and the fourth is zero because it is structurally zero. When the report is
// missing or unreadable — a fresh checkout, a server that has never run the test — the row falls
// back to the facts that are true without a measurement rather than printing "0%", which reads as
// a failing grade instead of as "not measured".
//
// No runtime imports: proof.test.mjs loads this file directly with `node --test`.

import type { EvalReport } from '../../types'

export interface ProofNumber {
  /** The figure, already formatted. */
  value: string
  /** What it counts. One short phrase, sentence case. */
  label: string
  /** The caveat that keeps the figure honest. One sentence. */
  note: string
}

/** Whole percents: a landing page has no room for the decimal, and the Trust page has both. */
const percent = (share: number): string => `${Math.round(share * 100)}%`

/** True without any test having been run, so it survives the fallback. */
const ZERO_ROWS: ProofNumber = {
  value: '0',
  label: 'Rows of your data sent to the AI',
  note: 'The AI is told what your columns hold, never what is in them.',
}

const TWO_MODELS: ProofNumber = {
  value: 'Two',
  label: 'Models that have to agree',
  note: 'A second model writes its own query for the same question.',
}

/** A half-written or older report file must not put "NaN%" on the landing page. */
const share = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1 ? value : null

const count = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) && value > 0 ? Math.round(value) : null

/**
 * Up to four figures for the landing page. Pass `null` when the report could not be read: the
 * row still stands, one figure shorter, and says nothing that has not been measured.
 */
export function proofNumbers(report: EvalReport | null | undefined): ProofNumber[] {
  if (!report) return [ZERO_ROWS, TWO_MODELS]

  const accuracy = share(report.accuracy)
  const holdout = share(report.accuracy_holdout)
  const total = count(report.total)
  // A run over the tuning questions only still writes 0 for the holdout figure. That is "not
  // measured", not "nothing was right", so it is left out rather than shown as 0%.
  const measuredHoldout = holdout !== null && report.cases?.some((c) => c.split === 'holdout') === true

  const numbers: ProofNumber[] = []
  if (accuracy !== null) {
    numbers.push({
      value: percent(accuracy),
      label: 'Test questions answered correctly',
      note: 'Correct answers worked out separately, from the clean source data.',
    })
  }
  if (measuredHoldout && holdout !== null) {
    numbers.push({
      value: percent(holdout),
      label: 'Correct on questions held back',
      note: 'Set aside at the start and never looked at while the product was tuned.',
    })
  }
  if (total !== null) {
    numbers.push({
      value: String(total),
      label: 'Questions in the test set',
      note: `Run ${report.runs > 1 ? `${report.runs} times ` : ''}on one made-up company, with every failure listed.`,
    })
  }
  numbers.push(ZERO_ROWS)
  return numbers.length > 1 ? numbers : [ZERO_ROWS, TWO_MODELS]
}
