// Run: cd frontend && node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { proofLines } from './proof.ts'
import bar from '../../fixtures/answer_bar.json' with { type: 'json' }
import kpi from '../../fixtures/answer_kpi.json' with { type: 'json' }
import clarify from '../../fixtures/answer_clarify.json' with { type: 'json' }
import refusal from '../../fixtures/answer_refusal.json' with { type: 'json' }

const withWork = (over) => ({ ...bar, work: { ...bar.work, ...over } })
const asIs = (key) => key
const ids = (answer, name = asIs) => proofLines(answer, name).map((line) => line.id)
const texts = (answer, name = asIs) => proofLines(answer, name).map((line) => line.text)

test('every answer is computed by the database and sends no rows, in that order', () => {
  const lines = texts(withWork({ cross_check: { status: 'skipped', model: null, detail: '', sql: null }, metrics_used: [] }))
  assert.deepEqual(lines, ['Computed by a database from your files', 'No rows or personal data were sent to the AI'])
})

test('an agreed cross-check earns a line; unavailable and skipped earn none', () => {
  assert.deepEqual(ids(bar), ['computed', 'crosscheck', 'privacy'])
  for (const status of ['unavailable', 'skipped']) {
    assert.deepEqual(ids(withWork({ cross_check: { ...bar.work.cross_check, status } })), ['computed', 'privacy'])
  }
})

test('a disagreement is never a tick: it is a banner, so no line is generated', () => {
  assert.deepEqual(ids(kpi).includes('crosscheck'), false)
  assert.equal(kpi.work.cross_check.status, 'disagreed', 'the fixture this pins is still a disagreement')
})

test('an agreed definition is named, and several are joined as a sentence', () => {
  const name = (key) => ({ attrition_rate: 'attrition rate', headcount: 'headcount' })[key] ?? key
  assert.equal(texts(kpi, name)[1], 'Used your agreed definition of attrition rate')
  const two = withWork({ metrics_used: ['attrition_rate', 'headcount'] })
  assert.equal(texts(two, name)[2], 'Used your agreed definition of attrition rate and headcount')
})

test('the caller decides what a metric key is called', () => {
  assert.equal(texts(kpi)[1], 'Used your agreed definition of attrition_rate')
})

test('a clarifying question, a refusal and an error computed nothing, so they claim nothing', () => {
  assert.deepEqual(proofLines(clarify, asIs), [])
  assert.deepEqual(proofLines(refusal, asIs), [])
  assert.deepEqual(proofLines({ ...bar, kind: 'error' }, asIs), [])
})
