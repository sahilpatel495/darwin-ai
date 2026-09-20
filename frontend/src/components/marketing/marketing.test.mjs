// Run from frontend/: node --test "src/**/*.test.mjs"
// The landing page's two pieces of logic: the proof row's reading of the accuracy report, and the
// copy itself, which is checked the same way every other analyst-facing string in this product is.
import test from 'node:test'
import assert from 'node:assert/strict'
import { proofNumbers } from './proof.ts'
import { DISCLAIMER, FAQ, FEATURES, FLOW, HOW_IT_WORKS, TAGLINE } from './copy.ts'

const JARGON = /\b(schema|join|joins|joined|fan-?out|guard|payload|pipeline|llm|token|tokens|session|sessions)\b/i

const REPORT = {
  generated_at: '2026-09-20T21:00:00+05:30',
  model: 'openai/gpt-oss-120b',
  runs: 3,
  total: 40,
  accuracy: 0.925,
  accuracy_holdout: 0.9,
  trust_score: 0.88,
  by_category: {},
  p50_ms: 2400,
  p95_ms: 6100,
  repair_rate: 0.1,
  crosscheck_agreement: 0.92,
  calibration: {},
  models: [],
  cases: [{ split: 'holdout' }, { split: 'dev' }],
}

test('a full report gives four figures, the last of which is the zero', () => {
  const numbers = proofNumbers(REPORT)
  assert.equal(numbers.length, 4)
  assert.deepEqual(
    numbers.map((n) => n.value),
    ['93%', '90%', '40', '0'],
  )
  assert.match(numbers[3].label, /never|AI/i)
})

test('a report with no unseen questions leaves the holdout figure out rather than printing 0%', () => {
  // The file still writes accuracy_holdout: 0 for a dev-only run. "0%" would read as a failing
  // grade instead of as "not measured", which is the whole reason this branch exists.
  const devOnly = { ...REPORT, accuracy_holdout: 0, cases: [{ split: 'dev' }] }
  const values = proofNumbers(devOnly).map((n) => n.value)
  assert.deepEqual(values, ['93%', '40', '0'])
})

test('no report at all still leaves a row standing, saying nothing unmeasured', () => {
  for (const missing of [null, undefined]) {
    const numbers = proofNumbers(missing)
    assert.equal(numbers.length, 2)
    assert.equal(numbers[0].value, '0')
    for (const n of numbers) assert.doesNotMatch(n.value, /%/, 'an accuracy claim needs a measurement behind it')
  }
})

test('a half-written report never puts NaN or a nonsense percentage on the landing page', () => {
  const broken = { ...REPORT, accuracy: Number.NaN, accuracy_holdout: 4, total: -1, cases: [] }
  for (const n of proofNumbers(broken)) {
    assert.doesNotMatch(n.value, /NaN|Infinity|-/, `"${n.value}" is not a figure to show a visitor`)
  }
})

test('the landing copy uses the analyst’s words and never shouts', () => {
  const lines = [
    TAGLINE,
    DISCLAIMER,
    ...FEATURES.flatMap((f) => [f.title, f.body]),
    ...FLOW.flatMap((s) => [s.label, s.detail]),
    ...HOW_IT_WORKS.flat(),
    ...FAQ.flatMap((f) => [f.question, ...f.answer]),
  ]
  for (const line of lines) {
    assert.doesNotMatch(line, JARGON, `not the analyst's words: "${line}"`)
    assert.doesNotMatch(line, /Verity/, `the product was renamed: "${line}"`)
    // Sentence case (§3). Initialisms are words, not labels, so the ones this product uses by
    // name are allowed through; anything else in capitals is an eyebrow label in disguise.
    const shouted = line.replace(/\b(AI|HR|PAN|CSV|TSV|MB|DarwinLens|Darwinbox|FDE)\b/g, '').match(/[A-Z]{2,}/)
    assert.equal(shouted, null, `all-caps in "${line}"`)
  }
})

test('the footer carries the line the assignment requires, unedited', () => {
  assert.match(DISCLAIMER, /Not affiliated with or endorsed by Darwinbox\.$/)
})

test('two of the six flow steps involve a model, and neither of them is the one that computes', () => {
  // The argument of the showcase card: the AI writes and words, the database computes.
  assert.equal(FLOW.filter((step) => step.ai).length, 2)
  const computes = FLOW.find((step) => /database computes/i.test(step.label))
  assert.ok(computes && computes.ai === false)
})

test('every FAQ answer is one or two paragraphs, and the five topics §7 asks for are there', () => {
  assert.deepEqual(
    FAQ.map((f) => f.id),
    ['privacy', 'models', 'files', 'limits', 'cost'],
  )
  for (const item of FAQ) {
    assert.ok(item.answer.length >= 1 && item.answer.length <= 2, `${item.id}: a third paragraph belongs on the How page`)
    assert.match(item.question, /\?$/, `${item.id}: the summary is a question`)
  }
})
