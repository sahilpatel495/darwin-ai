// Run: cd frontend && node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { flowNodes } from './flow.ts'
import bar from '../../fixtures/answer_bar.json' with { type: 'json' }
import kpi from '../../fixtures/answer_kpi.json' with { type: 'json' }
import line from '../../fixtures/answer_line.json' with { type: 'json' }

const work = (over) => ({ ...bar.work, ...over })
const node = (answerWork, id) => flowNodes(answerWork).find((n) => n.id === id)
const tones = (answerWork) => flowNodes(answerWork).map((n) => `${n.id}:${n.tone}`)

test('the route is always the same six nodes, in the order the work happened', () => {
  assert.deepEqual(flowNodes(bar.work).map((n) => n.id), ['question', 'query', 'safety', 'data', 'crosscheck', 'answer'])
})

test('a repaired query loops, and the safety check says it rejected one', () => {
  // The fixture's second attempt is a retry after the guard rejected the first.
  assert.equal(node(bar.work, 'query').loops, 1)
  assert.equal(node(bar.work, 'safety').tone, 'warn')
  assert.match(node(bar.work, 'safety').note, /Rejected once/)
  const clean = work({ attempts: [] })
  assert.equal(node(clean, 'query').loops, 0)
  assert.equal(node(clean, 'safety').tone, 'done')
  assert.equal(node(clean, 'safety').note, 'Read-only')
})

test('the query node names the model that wrote it, from the payload or the attempt', () => {
  assert.equal(node(bar.work, 'query').note, 'openai/gpt-oss-120b')
  assert.equal(node(work({ payloads: [] }), 'query').note, 'openai/gpt-oss-120b', 'the attempt still knows')
  assert.equal(node(work({ payloads: [], attempts: [] }), 'query').note, null)
})

test('the second model is green only when it agreed', () => {
  assert.ok(tones(bar.work).includes('crosscheck:done'))
  assert.ok(tones(kpi.work).includes('crosscheck:failed'), 'the fixture this pins is a disagreement')
  assert.equal(node(kpi.work, 'crosscheck').note, 'Disagreed')
  assert.equal(node(line.work, 'crosscheck').tone, 'idle', 'unavailable is not a pass')
  assert.equal(node(work({ cross_check: { ...bar.work.cross_check, status: 'skipped' } }), 'crosscheck').note, 'Not run')
})

test('the data node says how much the database read, in Indian digits', () => {
  assert.equal(node(work({ rows_scanned: 128400 }), 'data').note, '1,28,400 rows read')
  assert.equal(node(work({ rows_scanned: 1 }), 'data').note, '1 row read')
  assert.equal(node(work({ rows_scanned: 0 }), 'data').note, 'Computed by the database')
})

test('an answer that came from memory says so on the last node', () => {
  assert.equal(node(work({ cached: true }), 'answer').note, 'From memory')
  assert.equal(node(bar.work, 'answer').note, null)
})
