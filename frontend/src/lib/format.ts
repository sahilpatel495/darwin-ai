// Number formatting for chart axes, tooltips and the Trust Report.
//
// Why this exists: the backend already sends a display string for every table cell, but a chart
// axis needs labels for values that are not in the table (150000, 200000 ...). These functions
// follow the same rules as the backend's to_display (Indian digit grouping, ₹ lakh/crore from
// one lakh up, one-decimal percent) so a tooltip never disagrees with the table beside it.
//
// No runtime imports on purpose: the tests load this file directly with `node --test`.

import type { Cell, ChartSpec } from '../types'

type ValueFormat = ChartSpec['value_format']

const LAKH = 100_000
const CRORE = 10_000_000
const EMPTY = '—'

const grouped = (value: number, minDecimals: number, maxDecimals: number): string =>
  new Intl.NumberFormat('en-IN', { minimumFractionDigits: minDecimals, maximumFractionDigits: maxDecimals }).format(value)

/** "12.00 L" / "1.20 Cr", or null below one lakh. Same boundaries as the backend's _rupees:
 *  one lakh is judged on the amount rounded to paise (99,999.50 stays in rupees), and the unit
 *  on the amount rounded to a thousand (two decimals of a lakh), so 99,99,999 reads "1.00 Cr",
 *  not "100.00 L". */
function lakhCrore(abs: number, minDecimals: number, maxDecimals: number): string | null {
  if (Math.round(abs * 100) / 100 < LAKH) return null
  const unit = Math.round(abs / 1000) * 1000 >= CRORE ? CRORE : LAKH
  return `${grouped(abs / unit, minDecimals, maxDecimals)} ${unit === CRORE ? 'Cr' : 'L'}`
}

/** Digits for a tooltip or tile, without sign or symbol. Mirrors the backend's to_display so a
 *  tooltip reads exactly like the table cell beside it. */
function fullDigits(abs: number, format: ValueFormat): string {
  if (format === 'percent') return grouped(abs, 1, 1) // already percent points, e.g. 28.6
  if (format === 'currency_inr') {
    // Below one lakh the backend shows the exact amount: paise only when there are any.
    const wholeRupees = Number.isInteger(Math.round(abs * 100) / 100)
    return lakhCrore(abs, 2, 2) ?? grouped(abs, wholeRupees ? 0 : 2, 2)
  }
  // A small rate such as 0.0045 must not be shown as 0: keep two significant digits.
  if (abs > 0 && abs < 0.01) return new Intl.NumberFormat('en-IN', { maximumSignificantDigits: 2 }).format(abs)
  return grouped(abs, 0, 2)
}

/** Digits for an axis tick: whole rupees below a lakh, and lakh/crore for plain numbers too. */
function shortDigits(abs: number, format: ValueFormat): string {
  if (format === 'percent') return grouped(abs, 0, 1)
  return lakhCrore(abs, 0, 1) ?? grouped(abs, 0, format === 'currency_inr' ? 0 : 2)
}

function formatNumeric(value: number, format: ValueFormat, short: boolean): string {
  const digits = short ? shortDigits(Math.abs(value), format) : fullDigits(Math.abs(value), format)
  const sign = value < 0 && /[1-9]/.test(digits) ? '-' : '' // a tiny negative that rounds to zero is "0", not "-0"
  return `${sign}${format === 'currency_inr' ? '₹' : ''}${digits}${format === 'percent' ? '%' : ''}`
}

/** Full-precision label for a tooltip or tile. Never returns "NaN": a hostile or odd cell is
 *  shown as text, a missing one as a dash. */
export function formatValue(value: Cell, format: ValueFormat): string {
  if (value === null || value === '') return EMPTY
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'string') return value
  return Number.isFinite(value) ? formatNumeric(value, format, false) : EMPTY
}

/** Short label for an axis tick: "₹12.5 L", "25 L", "25%". */
export const formatTick = (value: number, format: ValueFormat): string =>
  Number.isFinite(value) ? formatNumeric(value, format, true) : ''

/**
 * A tick formatter with one unit for the whole axis. `formatTick` decides per value, which on a
 * salary axis reads "₹0, ₹35,000, ₹70,000, ₹1.1 L" — three rulers in one. Given the largest
 * value the axis has to show, this picks the unit once: rupees up to ten lakh, then lakh, then
 * crore from one crore, so every tick is a number worth reading.
 */
export function axisTicks(format: ValueFormat, max: number): (value: number) => string {
  const abs = Math.abs(max)
  const unit = format === 'percent' ? 1 : abs >= CRORE ? CRORE : abs >= 10 * LAKH ? LAKH : 1
  const suffix = unit === CRORE ? ' Cr' : unit === LAKH ? ' L' : ''
  return (value) => {
    if (!Number.isFinite(value)) return ''
    const digits = `${grouped(Math.abs(value) / unit, 0, format === 'percent' ? 1 : 2)}${suffix}`
    const sign = value < 0 && /[1-9]/.test(digits) ? '-' : ''
    return `${sign}${format === 'currency_inr' ? '₹' : ''}${digits}${format === 'percent' ? '%' : ''}`
  }
}

/** A 0..1 share as a percentage: 0.925 -> "92.5%". The eval report stores fractions, while
 *  query results store percent points, hence two functions. */
export const formatShare = (fraction: number): string => (Number.isFinite(fraction) ? `${grouped(fraction * 100, 0, 1)}%` : EMPTY)

export const formatDuration = (ms: number): string => (!Number.isFinite(ms) ? EMPTY : ms < 1000 ? `${Math.round(ms)} ms` : `${grouped(ms / 1000, 1, 1)} s`)

/** SQL aliases and category keys are snake_case ("avg_ctc", "hr_metrics"); people read
 *  "Avg CTC" and "HR metrics". The short list covers the HR abbreviations Verity's own glossary
 *  and eval categories use; anything else is simply sentence-cased. */
export function humanize(columnName: string): string {
  const words = columnName
    .replace(/_pct$/, ' %')
    .replace(/_/g, ' ')
    .trim()
    .replace(/\b(hr|ctc|id|lop|pf|fy|kpi)\b/gi, (word) => word.toUpperCase())
  return words.charAt(0).toUpperCase() + words.slice(1)
}
