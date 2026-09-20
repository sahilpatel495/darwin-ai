// Run: cd frontend && node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { STAGE_LABELS, foldStep, modelName, summarizeRun, tidyDetail, toProgress, waitSeconds } from './steps.ts'
import fixtureSteps from '../../fixtures/steps.json' with { type: 'json' }

const step = (stage, status, detail = '') => ({ stage, status, detail })
const fold = (events) => events.reduce(foldStep, [])
const shown = (steps, running = false) => toProgress(steps, running).map((s) => `${s.id}:${s.state}`)

test('every stage the brief names has a human label', () => {
  assert.deepEqual(STAGE_LABELS, {
    understand: 'Understanding the question',
    generate: 'Writing the query',
    guard: 'Checking the query is safe',
    execute: 'Running it on your data',
    repair: 'Fixing the query',
    verify: 'Double-checking with a second AI model',
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

test('the timeline shows what is still to come, so the wait has a shape', () => {
  assert.deepEqual(shown([], true), [
    'understand:active', // something is always happening while the run is in flight
    'generate:pending',
    'guard:pending',
    'execute:pending',
    'verify:pending',
    'chart:pending',
    'narrate:pending',
  ])
  assert.deepEqual(shown([step('understand', 'ok'), step('generate', 'started')], true).slice(0, 3), ['understand:done', 'generate:active', 'guard:pending'])
  // Nothing is active once the run is over, however it ended.
  assert.deepEqual(shown([], false)[0], 'understand:pending')
})

test('the step after the last result is the one that is running, and only one is', () => {
  // The server announces some stages only when they finish, so a card with every row done or
  // pending would show a question that looks stuck (§11).
  const done = shown([step('understand', 'ok'), step('generate', 'ok')], true)
  assert.deepEqual(done.slice(0, 3), ['understand:done', 'generate:done', 'guard:active'])
  assert.equal(done.filter((row) => row.endsWith(':active')).length, 1)
  // A wait for a busy model is where the run actually is: nothing below it starts breathing.
  const busy = shown([step('generate', 'warn', 'All the free AI models are busy. Retrying in 12 seconds.')], true)
  assert.deepEqual(busy.slice(0, 3), ['understand:pending', 'generate:waiting', 'guard:pending'])
  const failed = shown([step('execute', 'failed', 'Column not found')], true)
  assert.ok(!failed.some((row) => row.endsWith(':active')))
})

test('a repaired run shows the fix between the safety check and the query running', () => {
  const steps = fold([step('guard', 'warn', 'Rejected: unknown column'), step('repair', 'ok', 'Rewrote the query'), step('guard', 'ok', 'Read-only')])
  assert.deepEqual(shown(steps, true), [
    'understand:active',
    'generate:pending',
    'guard:done', // the second run of the check is the one that stands
    'repair:done',
    'execute:pending',
    'verify:pending',
    'chart:pending',
    'narrate:pending',
  ])
})

test('the whole fixture run ends with every step done and the detail tidied', () => {
  const steps = toProgress(fold(fixtureSteps), false)
  assert.ok(steps.every((s) => s.state === 'done'))
  assert.equal(steps.find((s) => s.id === 'guard').detail, 'Read-only, 2 tables, 3 columns')
  assert.equal(steps.find((s) => s.id === 'repair').label, 'Fixing the query')
})

test('a step left open when the run was stopped is not shown as still running', () => {
  assert.deepEqual(shown([step('generate', 'started')], false).slice(0, 2), ['understand:pending', 'generate:pending'])
  // A status this build does not know does not crash the timeline, and a new stage is kept.
  const unknown = shown([step('rerank', 'skipped', 'new in a later server')], false)
  assert.ok(unknown.includes('rerank:pending'))
  assert.equal(toProgress([step('rerank', 'skipped', 'x')], false).at(-1).label, 'rerank')
})

test('the models being busy is a wait, not a failure: amber, with the seconds it asked for', () => {
  const busy = step('generate', 'warn', 'All the free AI models are busy. Retrying in 12 seconds.')
  assert.equal(waitSeconds(busy.detail), 12)
  assert.equal(waitSeconds('Rejected: unknown column department'), null)
  assert.equal(toProgress([busy], true).find((s) => s.id === 'generate').state, 'waiting')
  assert.equal(toProgress([step('guard', 'warn', 'Rejected')], true).find((s) => s.id === 'guard').state, 'warn')
})

test('the model doing the writing is named as soon as it has written', () => {
  assert.equal(modelName(fold(fixtureSteps)), 'openai/gpt-oss-120b')
  assert.equal(modelName([step('generate', 'started')]), null)
  assert.equal(modelName([]), null)
})

test('the collapsed line says how long it took and how much was checked', () => {
  assert.equal(summarizeRun(fold(fixtureSteps), 3247), 'Answered in 3.2 s, 9 checks, 1 warning')
  assert.equal(summarizeRun([step('guard', 'ok')], 1000), 'Answered in 1.0 s, 1 check')
  // A turn restored from a previous visit was timed in a session that is gone.
  assert.equal(summarizeRun([step('guard', 'ok')], null), 'Worked through 1 check')
  assert.equal(summarizeRun([step('guard', 'warn'), step('execute', 'failed'), step('verify', 'warn')], null), 'Worked through 3 checks, 2 warnings, 1 failed')
})
