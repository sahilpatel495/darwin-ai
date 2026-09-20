// Run from frontend/: node --test "src/**/*.test.mjs"
// Plain Node test runner (Node strips the TypeScript types itself), so no test dependency is
// needed. Both files under test are import-free on purpose, which is what lets this work.
//
// The tour that used to be tested here is gone (§7): there is no coach-mark walkthrough any more,
// so its steps, its anchors and its panel arithmetic went with it. What replaced it is three
// one-line hints, and the only thing worth pinning about them is the copy.
import test from 'node:test'
import assert from 'node:assert/strict'
import { EXPLAIN } from './explain.ts'
import { TIPS, TIP_ORDER } from './tips.ts'

// §12: the analyst never reads these words, so they must never appear in copy shown to them.
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

test('the product is called DarwinLens everywhere the analyst can read it', () => {
  const copy = [...Object.values(EXPLAIN).flatMap(({ title, body }) => [title, body]), ...TIP_ORDER.map((id) => TIPS[id].text)]
  for (const line of copy) assert.doesNotMatch(line, /Verity/, 'the product was renamed on 2026-09-21')
})

test('there are exactly three tips, each one line in the analyst’s words', () => {
  // Three is the whole budget (§7). A fourth is a sign a screen is not explaining itself.
  assert.equal(TIP_ORDER.length, 3)
  assert.deepEqual([...TIP_ORDER].sort(), Object.keys(TIPS).sort())

  for (const id of TIP_ORDER) {
    const tip = TIPS[id]
    assert.equal(tip.id, id, `${id}: the record knows its own id`)
    assert.doesNotMatch(tip.text, JARGON, `${id}: uses the analyst's words`)
    // Sentence case (§3). "AI" is a word, not an eyebrow label; anything else in capitals is one.
    assert.equal(tip.text.replace(/\bAI\b/g, '').match(/[A-Z]{2,}/), null, `${id}: no all-caps labels`)
    // One line beside the thing it explains, not a paragraph: that is what `#/how` is for.
    assert.equal(sentences(tip.text).length, 1, `${id}: one sentence`)
    assert.ok(tip.text.length < 140, `${id}: short enough to sit on one line beside a control`)
    assert.ok(tip.where.length > 0, `${id}: says who renders it`)
  }
})
