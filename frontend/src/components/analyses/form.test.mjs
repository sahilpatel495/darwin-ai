// Run from frontend/: node --test "src/**/*.test.mjs"
// The sentence under the pickers is what the analyst trusts before they run anything, so every
// kind in the fixture catalogue is checked here.
import test from 'node:test'
import assert from 'node:assert/strict'
import { defaultOptions, groupedColumns, isComplete, MISSING, noColumnsLine, previewSentence } from './form.ts'

const COLUMNS = [
  { ref: 'employees.department', label: 'department', table_label: 'employees.csv', kind: 'category' },
  { ref: 'employees.location', label: 'location', table_label: 'employees.csv', kind: 'category' },
  { ref: 'employees.date_of_joining', label: 'date_of_joining', table_label: 'employees.csv', kind: 'date' },
  { ref: 'employees.annual_ctc', label: 'annual_ctc', table_label: 'employees.csv', kind: 'measure' },
  { ref: 'salary_register.pay_month', label: 'pay_month', table_label: 'Salary_Register_2025.xlsx', kind: 'date' },
  { ref: 'salary_register.gross', label: 'gross', table_label: 'Salary_Register_2025.xlsx', kind: 'measure' },
]

// What the page passes in: the column labels, humanised (lib/format humanize).
const LABELS = {
  'employees.department': 'Department',
  'employees.location': 'Location',
  'employees.annual_ctc': 'Annual CTC',
  'salary_register.gross': 'Gross',
  'salary_register.pay_month': 'Pay month',
}

const measureIn = { key: 'measure', label: 'What to measure', accepts: ['measure'], optional: false }
const byIn = { key: 'by', label: 'Split by', accepts: ['category'], optional: false }
const dateIn = { key: 'date', label: 'Over which date', accepts: ['date'], optional: false }
const optionalBy = { ...byIn, optional: true }
const aggregate = { key: 'aggregate', label: 'How to combine', choices: ['sum', 'average', 'count', 'median', 'min', 'max'] }
const grain = { key: 'grain', label: 'Every', choices: ['month', 'quarter', 'year', 'week'] }

const kind = (key, inputs, options = []) => ({ key, name: key, description: '', example: '', inputs, options })

test('a column picker offers only the kinds its input accepts, grouped by file', () => {
  const groups = groupedColumns(measureIn, COLUMNS)
  assert.deepEqual(
    groups.map((g) => [g.table, g.columns.map((c) => c.ref)]),
    [
      ['employees.csv', ['employees.annual_ctc']],
      ['Salary_Register_2025.xlsx', ['salary_register.gross']],
    ],
  )
  assert.deepEqual(groupedColumns(byIn, COLUMNS).flatMap((g) => g.columns.map((c) => c.ref)), [
    'employees.department',
    'employees.location',
  ])
  // Two files both hold a date: each keeps its own group, in catalog order.
  assert.deepEqual(groupedColumns(dateIn, COLUMNS).map((g) => g.table), ['employees.csv', 'Salary_Register_2025.xlsx'])
})

test('a picker with nothing to offer says so in the analyst\'s words', () => {
  assert.equal(noColumnsLine(dateIn), 'No date columns in your files')
  assert.equal(noColumnsLine(measureIn), 'No number columns in your files')
  assert.equal(noColumnsLine({ ...byIn, accepts: ['category', 'text'] }), 'No text columns in your files')
})

test('the first choice of every option is preselected', () => {
  assert.deepEqual(defaultOptions(kind('trend', [], [aggregate, grain])), { aggregate: 'sum', grain: 'month' })
  assert.deepEqual(defaultOptions(kind('distribution', [], [])), {})
})

test('an analysis is ready when every required input has a column', () => {
  const trend = kind('trend', [measureIn, dateIn, optionalBy])
  assert.equal(isComplete(trend, {}), false)
  assert.equal(isComplete(trend, { measure: 'salary_register.gross' }), false)
  assert.equal(isComplete(trend, { measure: 'salary_register.gross', date: 'salary_register.pay_month' }), true)
})

test('the preview reads like the question the analyst would ask', () => {
  const breakdown = kind('breakdown', [measureIn, byIn], [aggregate])
  assert.equal(
    previewSentence(breakdown, { measure: 'employees.annual_ctc', by: 'employees.department' }, { aggregate: 'average' }, LABELS),
    'Average Annual CTC by Department',
  )
  // A sum is silent: the column added up is the column.
  assert.equal(
    previewSentence(breakdown, { measure: 'salary_register.gross', by: 'employees.department' }, { aggregate: 'sum' }, LABELS),
    'Gross by Department',
  )

  const trend = kind('trend', [measureIn, dateIn, optionalBy], [aggregate, grain])
  const trendInputs = { measure: 'salary_register.gross', date: 'salary_register.pay_month' }
  assert.equal(previewSentence(trend, trendInputs, { aggregate: 'sum', grain: 'month' }, LABELS), 'Gross by month')
  assert.equal(
    previewSentence(trend, { ...trendInputs, by: 'employees.location' }, { aggregate: 'sum', grain: 'quarter' }, LABELS),
    'Gross by quarter, with a line for each Location',
  )

  assert.equal(
    previewSentence(kind('top_n', [measureIn, byIn], [aggregate]), { measure: 'salary_register.gross', by: 'employees.location' }, { aggregate: 'sum', top_n: '10' }, LABELS),
    'Top 10 Locations by Gross',
  )
  assert.equal(
    previewSentence(kind('share', [measureIn, byIn], [aggregate]), { measure: 'salary_register.gross', by: 'employees.department' }, { aggregate: 'average' }, LABELS),
    'Share of average Gross by Department',
  )
  assert.equal(
    previewSentence(kind('pivot', [measureIn, byIn], [aggregate]), { measure: 'employees.annual_ctc', by: 'employees.department', across: 'employees.location' }, { aggregate: 'average' }, LABELS),
    'Average Annual CTC by Department and Location',
  )
  assert.equal(
    previewSentence(kind('correlation', [measureIn]), { measure: 'employees.annual_ctc', measure_b: 'salary_register.gross' }, {}, LABELS),
    'Annual CTC against Gross',
  )
  assert.equal(
    previewSentence(kind('change', [measureIn, dateIn, optionalBy], [aggregate, grain]), { measure: 'salary_register.gross', date: 'salary_register.pay_month', by: 'employees.department' }, { aggregate: 'sum', grain: 'month' }, LABELS),
    'Gross, this month against the one before, split by Department',
  )
  assert.equal(previewSentence(kind('distribution', [measureIn]), { measure: 'employees.annual_ctc' }, {}, LABELS), 'How Annual CTC is spread')
  assert.equal(previewSentence(kind('outliers', [measureIn]), { measure: 'salary_register.gross' }, {}, LABELS), 'Unusual Gross values')
})

test('what is not chosen yet reads as a gap, never as a wrong promise', () => {
  const breakdown = kind('breakdown', [measureIn, byIn], [aggregate])
  assert.equal(previewSentence(breakdown, {}, { aggregate: 'average' }, LABELS), `Average ${MISSING} by ${MISSING}`)
  // No stray "…s" when the group to rank has not been chosen.
  assert.equal(
    previewSentence(kind('top_n', [measureIn, byIn], [aggregate]), { measure: 'salary_register.gross' }, { aggregate: 'sum', top_n: '5' }, LABELS),
    `Top 5 ${MISSING} by Gross`,
  )
})

test('a kind this screen has never seen still describes itself truthfully', () => {
  const unknown = { key: 'cohort', name: 'Cohort retention', description: '', example: '', inputs: [measureIn, byIn], options: [] }
  assert.equal(previewSentence(unknown, {}, {}, LABELS), 'Cohort retention')
  assert.equal(
    previewSentence(unknown, { measure: 'employees.annual_ctc', by: 'employees.department' }, {}, LABELS),
    'Cohort retention: Annual CTC, Department',
  )
})

test('a column with no label still appears, by its reference', () => {
  const breakdown = kind('breakdown', [measureIn, byIn], [aggregate])
  assert.equal(
    previewSentence(breakdown, { measure: 'attendance.days_present', by: 'employees.department' }, { aggregate: 'sum' }, LABELS),
    'Attendance.days_present by Department',
  )
})
