// Run: cd frontend && node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { STAGE_LABELS, foldStep, summarizeSteps, tidyDetail } from './steps.ts'
import fixtureSteps from '../../fixtures/steps.json' with { type: 'json' }

const step = (stage, status, detail = '') => ({ stage, status, detail })
const fold = (events) => events.reduce(foldStep, [])

test('every stage the brief names has a human label', () => {
  assert.deepEqual(STAGE_LABELS, {
    understand: 'Understanding the question',
    generate: 'Writing SQL',
    guard: 'Checking the SQL is safe',
    execute: 'Running the query',
    repair: 'Repairing',
    verify: 'Verifying the result',
    chart: 'Choosing a chart',
    narrate: 'Writing the answer',
  })
})

test('a started step is replaced by its own result, not listed twice', () => {
  const steps = fold([step('generate', 'started'), step('generate', 'ok', 'wrote a 3-step plan')])
  assert.deepEqual(steps, [step('generate', 'ok', 'wrote a 3-step plan')])
})

test('a stage that runs again after a repair is listed again', () => {
  const steps = fold([step('guard', 'warn', 'Rejected'), step('repair', 'ok'), step('guard', 'ok')])
  assert.deepEqual(steps.map((s) => `${s.stage}:${s.status}`), ['guard:warn', 'repair:ok', 'guard:ok'])
})

test('a step that finishes after later steps have run closes its own line, wherever that is', () => {
  // The real order: verification starts, the chart and the wording finish, then verification reports.
  const steps = fold([step('verify', 'started'), step('chart', 'ok', 'Bar'), step('narrate', 'started'), step('narrate', 'ok'), step('verify', 'ok', 'Agreed')])
  assert.deepEqual(steps.map((s) => `${s.stage}:${s.status}`), ['verify:ok', 'chart:ok', 'narrate:ok'])
})

test('counts the server left unpluralised read as plain English', () => {
  assert.equal(tidyDetail('Read-only, 1 table(s), 4 column(s)'), 'Read-only, 1 table, 4 columns')
  assert.equal(tidyDetail('5,088 row(s) in 12 ms'), '5,088 rows in 12 ms')
  assert.equal(tidyDetail('No ambiguous terms'), 'No ambiguous terms')
})

test('the closing "done" event is not a step the user needs to read', () => {
  assert.deepEqual(fold([step('narrate', 'ok'), step('done', 'ok')]), [step('narrate', 'ok')])
})

test('folding never mutates the previous list (React state)', () => {
  const before = [step('generate', 'started')]
  foldStep(before, step('generate', 'ok'))
  assert.deepEqual(before, [step('generate', 'started')])
})

test('summary counts steps and names problems in plain words', () => {
  assert.equal(summarizeSteps(fold(fixtureSteps)), '9 steps, 1 warning')
  assert.equal(summarizeSteps([step('guard', 'ok')]), '1 step')
  assert.equal(summarizeSteps([step('guard', 'warn'), step('execute', 'failed'), step('verify', 'warn')]), '3 steps, 2 warnings, 1 failed')
})
