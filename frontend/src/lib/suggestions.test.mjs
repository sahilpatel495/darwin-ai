// Run from frontend/: node --test "src/**/*.test.mjs"
// The suggestion list is the first thing an analyst clicks, so what it must never do is offer a
// question the files cannot answer — hence: catalog questions first, templates only to fill a gap.
import test from 'node:test'
import assert from 'node:assert/strict'
import { groupSuggestions, kindOf, ROLES, suggestionsFor } from './suggestions.ts'

const CATALOG = [
  'What is the total gross pay by department?',
  'How has headcount changed month by month?',
  'What is the attrition rate for FY25?',
  'Which location has the highest average CTC?',
]

test('a question is filed under what it is about, not under the first word that matched', () => {
  assert.equal(kindOf('How has headcount changed month by month?').kind, 'People')
  assert.equal(kindOf('What is the attrition rate for FY25?').kind, 'Attrition')
  assert.equal(kindOf('What is the total gross pay by department?').kind, 'Pay')
  assert.equal(kindOf('How many days were people absent in Q1?').kind, 'Attendance')
  assert.equal(kindOf('Show me something else entirely').kind, 'Breakdown')
})

test('every suggestion carries a glyph and a kind', () => {
  for (const item of suggestionsFor(CATALOG, 'HR analyst')) {
    assert.ok(item.glyph.length > 0, item.question)
    assert.ok(item.kind.length > 0, item.question)
    assert.equal(item.question.trim(), item.question)
  }
})

test('the role decides the order, not the catalog', () => {
  const analyst = suggestionsFor(CATALOG, 'HR analyst').map((s) => s.kind)
  assert.equal(analyst[0], 'Attrition', 'an analyst is asked about attrition first')

  const payroll = suggestionsFor(CATALOG, 'Payroll').map((s) => s.kind)
  assert.equal(payroll[0], 'Pay')

  const founder = suggestionsFor(CATALOG, 'Founder').map((s) => s.kind)
  assert.equal(founder[0], 'People')
})

test('every question the files can answer is kept, whatever the role', () => {
  for (const role of [...ROLES, null, 'Something we never shipped']) {
    const questions = suggestionsFor(CATALOG, role).map((s) => s.question)
    assert.equal(questions.length, 4, `${role}`)
    assert.deepEqual([...questions].sort(), [...CATALOG].sort(), `${role}`)
  }
})

test('templates only fill a gap, and never repeat what the catalog already said', () => {
  const none = suggestionsFor([], 'Payroll')
  assert.equal(none.length, 2, 'a server with no suggestions still offers the role its own')
  assert.ok(none.every((s) => s.question.length > 0))

  const one = suggestionsFor(['What is the total gross pay this year?'], 'Payroll')
  assert.equal(one[0].question, 'What is the total gross pay this year?')
  assert.equal(new Set(one.map((s) => s.question.toLowerCase())).size, one.length, 'no duplicates')
})

test('a scruffy list from the server does not produce a scruffy card', () => {
  const messy = ['  What is the total gross pay by department?  ', 'What is the total gross pay by department?', '', '   ']
  const picked = suggestionsFor(messy, null)
  assert.deepEqual(picked.map((s) => s.question).slice(0, 1), ['What is the total gross pay by department?'])
  assert.equal(picked.filter((s) => s.kind === 'Pay').length, 1, 'the same question twice is one card')
})

test('more ideas are grouped by subject, each subject once', () => {
  const groups = groupSuggestions([...CATALOG, 'How many people were absent in March?'], 'HR analyst')
  const kinds = groups.map((group) => group.kind)
  assert.deepEqual(kinds, [...new Set(kinds)], 'a subject has one heading')
  assert.equal(
    groups.reduce((total, group) => total + group.items.length, 0),
    5,
  )
})
