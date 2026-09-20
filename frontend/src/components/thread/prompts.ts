// Two small things the composer needs and nothing else in the product does: which glyph a
// suggestion card may draw, and what the placeholder is halfway through typing itself out (§8).
//
// The questions themselves come from lib/suggestions, which knows the analyst's role. There is
// one classifier in this product and it is not here.
//
// No runtime imports on purpose: the tests load this file directly with `node --test`.

import type { GlyphName } from '../graphics/Glyph'

const GLYPHS: GlyphName[] = ['bars', 'trend', 'donut', 'table', 'shield', 'link', 'sparkles', 'upload', 'lock', 'receipt', 'people', 'rupee', 'calendar', 'compare']

/** The glyph a card should draw. A suggestion carries its glyph as a plain string, so a name the
 *  set cannot draw has to fall back to something rather than to an empty box. */
export const glyphName = (name: string): GlyphName => (GLYPHS.includes(name as GlyphName) ? (name as GlyphName) : 'sparkles')

const CHAR_MS = 55 // a fast, confident typist
const HOLD_MS = 2400 // long enough to read the whole question before the next one starts

/**
 * The placeholder mid-typewriter: each example types itself out, holds, then the next one starts
 * from nothing. `elapsed` is milliseconds since the cycle began and everything is derived from it
 * — one clock, so nothing drifts out of step and stopping is simply not asking again.
 */
export function typedPlaceholder(examples: string[], elapsed: number): string {
  if (examples.length === 0) return ''
  const span = (question: string) => question.length * CHAR_MS + HOLD_MS
  const total = examples.reduce((sum, question) => sum + span(question), 0)
  // Modulo twice: a clock that has been running since before this component mounted can hand us a
  // negative number, and a negative index would start the cycle in the middle of nothing.
  let left = ((elapsed % total) + total) % total
  for (const question of examples) {
    if (left < span(question)) return question.slice(0, Math.min(question.length, Math.floor(left / CHAR_MS) + 1))
    left -= span(question)
  }
  return examples[examples.length - 1] ?? ''
}
