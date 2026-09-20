// Run from frontend/: node --test "src/**/*.test.mjs"
// Plain Node test runner (Node strips the TypeScript types itself), so no test dependency is
// needed. Both files under test are import-free on purpose, which is what lets this work.
import test from 'node:test'
import assert from 'node:assert/strict'
import { EXPLAIN } from './explain.ts'
import { anchorSelectors, placePanel, TOUR_STEPS } from './tourSteps.ts'

// §8: the analyst never reads these words, so they must never appear in copy shown to them.
const JARGON = /\b(schema|join|joins|joined|fan-?out|guard|payload|pipeline|llm|token|tokens|session|sessions)\b/i

const sentences = (body) => body.split(/(?<=[.?])\s+/).filter(Boolean)

test('every explanation has a title and a body written for an analyst', () => {
  const keys = ['confidence', 'crossCheck', 'definition', 'dataHealth', 'links', 'combined', 'clarify']
  assert.deepEqual(Object.keys(EXPLAIN).sort(), [...keys].sort())
  for (const [key, { title, body }] of Object.entries(EXPLAIN)) {
    assert.ok(title.length > 0 && title.length < 40, `${key}: the title is one short phrase`)
    assert.doesNotMatch(title, JARGON, `${key}: the title uses the analyst's words`)
    assert.doesNotMatch(body, JARGON, `${key}: the body uses the analyst's words`)
    // Two sentences (§10). One is too thin to say what it means and why it matters; three is an essay.
    assert.equal(sentences(body).length, 2, `${key}: two sentences`)
    assert.match(title[0], /[A-Z]/, `${key}: sentence case, so only the first letter is capital`)
    assert.doesNotMatch(title, /[A-Z]{2,}/, `${key}: no all-caps labels`)
  }
})

test('the tour names the six anchors once each and stays in the analyst’s words', () => {
  assert.deepEqual(
    TOUR_STEPS.map((step) => step.anchor),
    ['files', 'composer', 'working', 'overview', 'analyses', 'trust'],
  )
  for (const { anchor, title, body } of TOUR_STEPS) {
    assert.doesNotMatch(title, JARGON, `${anchor}: the title uses the analyst's words`)
    assert.doesNotMatch(body, JARGON, `${anchor}: the body uses the analyst's words`)
    assert.doesNotMatch(title, /[A-Z]{2,}/, `${anchor}: no all-caps labels`)
  }
})

test('a step looks for its placed anchor first, then for the nav rail link', () => {
  // Order matters: querySelector with a comma-joined list would return whichever comes first in
  // the document, which is the rail — so the selectors are tried one at a time, best first.
  for (const step of TOUR_STEPS) {
    const selectors = anchorSelectors(step)
    assert.equal(selectors[0], `[data-tour="${step.anchor}"]`, `${step.anchor}: the placed anchor is tried first`)
    assert.equal(selectors.length, step.fallback ? 2 : 1)
  }
  // The three rail steps are the ones nobody places an anchor for.
  assert.deepEqual(
    TOUR_STEPS.filter((step) => step.fallback).map((step) => step.anchor),
    ['overview', 'analyses', 'trust'],
  )
})

test('the tour panel sits below its anchor, above it when there is no room, and never off screen', () => {
  const panel = { width: 320, height: 200 }
  const viewport = { width: 1280, height: 800 }

  const below = placePanel({ top: 100, left: 40, width: 200, height: 30 }, panel, viewport)
  assert.deepEqual(below, { top: 142, left: 40 }, 'below the anchor, one gap down')

  // An anchor near the bottom: 700 + 30 + 12 + 200 is past 800, so the panel flips above it.
  const above = placePanel({ top: 700, left: 40, width: 200, height: 30 }, panel, viewport)
  assert.deepEqual(above, { top: 488, left: 40 })

  // A composer anchored at the right edge of a phone must not put its Next button off screen.
  const phone = placePanel({ top: 100, left: 300, width: 80, height: 30 }, panel, { width: 390, height: 844 })
  assert.equal(phone.left, 390 - 320 - 8)

  // A panel taller than the screen is clamped to the top margin rather than scrolled off it.
  const tiny = placePanel({ top: 10, left: 0, width: 40, height: 20 }, { width: 320, height: 700 }, { width: 390, height: 500 })
  assert.deepEqual(tiny, { top: 8, left: 8 })
})
