// Run from frontend/: node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import catalog from '../../fixtures/catalog.json' with { type: 'json' }
import { classifyQuestion, groupQuestions, questionWords } from './questions.ts'

const words = questionWords(catalog)
const kind = (question) => classifyQuestion(question, words)

test('a question about a period is a trend, whatever else it names', () => {
  assert.equal(kind('How has headcount changed month by month?'), 'trends')
  assert.equal(kind('What is the gross pay trend over time?'), 'trends')
  assert.equal(kind('How many people joined each quarter?'), 'trends')
})

test('a question that names columns from two different files is across files', () => {
  // gross belongs only to the salary register, department only to employees.
  assert.equal(kind('What is the total gross pay by department?'), 'across')
  // Both in employees: one file, so it is not an across-files question.
  assert.notEqual(kind('How many people are in each department by location?'), 'across')
})

test('a word two files share proves nothing about spanning them', () => {
  // emp_id is in employees and in both attendance files, so it cannot make a question "across".
  assert.ok(!words.byFile.has('emp id'), 'emp id belongs to more than one file and must not be a signal')
  assert.equal(words.byFile.get('gross'), 'salary_register')
  assert.equal(words.byFile.get('department'), 'employees')
  // A bare year is not a file word.
  assert.ok(!words.byFile.has('2025'))
})

test('a question that names a measure from the glossary is an HR measure', () => {
  assert.equal(kind('What is the attrition rate for FY25?'), 'measures')
  assert.equal(kind('Which location has the highest average CTC?'), 'measures')
  // Matched on the other names too, not only the metric's own name.
  assert.equal(kind('What is our staff turnover?'), 'measures')
})

test('everything else is a total or a breakdown', () => {
  assert.equal(kind('How many people are in each location?'), 'totals')
  assert.equal(kind('What is the biggest team?'), 'totals')
})

test('groups come back in reading order, and an empty group is left out', () => {
  const groups = groupQuestions(catalog)
  assert.deepEqual(
    groups.map((group) => group.title),
    ['Trends', 'Across files', 'HR measures'],
  )
  assert.equal(groups.flatMap((group) => group.questions).length, catalog.suggested_questions.length)
  assert.deepEqual(groupQuestions({ ...catalog, suggested_questions: [] }), [])
})
