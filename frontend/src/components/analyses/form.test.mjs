// Run from frontend/: node --test "src/**/*.test.mjs"
// The sentence under the pickers is what the analyst trusts before they run anything, so every
// kind in the fixture catalogue is checked here.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  defaultOptions,
  groupedColumns,
  groupValues,
  isComplete,
  MISSING,
  noColumnsLine,
  previewSentence,
  sentenceParts,
  shortLabel,
  slotForMessage,
  unmentionedInputs,
} from './form.ts'
import catalog from '../../fixtures/analyses.json' with { type: 'json' }

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

// --- The sentence builder ------------------------------------------------------------------------

/** Every gap the builder will draw a picker in. */
const slots = (parts) => parts.filter((part) => typeof part !== 'string')

test('every analysis the server offers can be filled in entirely, with nothing out of reach', () => {
  for (const item of catalog.kinds) {
    const options = defaultOptions(item)
    const keys = slots(sentenceParts(item, options)).map((slot) => slot.key)
    const reachable = [...keys, ...unmentionedInputs(item, options).map((input) => input.key)]
    for (const input of item.inputs) {
      assert.ok(reachable.includes(input.key), `${item.key} has no picker for ${input.key}`)
    }
    // An option with no fixed choices is a value, and values live in the sentence itself.
    for (const option of item.options.filter((o) => o.choices.length === 0)) {
      assert.ok(keys.includes(option.key), `${item.key} has no gap for ${option.key}`)
    }
    assert.equal(new Set(reachable).size, reachable.length, `${item.key} asks for the same thing twice`)
  }
})

test('a date the sentence names only by its grain still gets a picker of its own', () => {
  const trend = catalog.kinds.find((k) => k.key === 'trend')
  assert.deepEqual(unmentionedInputs(trend, defaultOptions(trend)).map((input) => input.key), ['date'])
  const breakdown = catalog.kinds.find((k) => k.key === 'breakdown')
  assert.deepEqual(unmentionedInputs(breakdown, defaultOptions(breakdown)), [])
})

test('an unknown analysis still offers a gap for every column it needs', () => {
  const unknown = { key: 'cohort', name: 'Cohort retention', description: '', example: '', inputs: [measureIn, byIn], options: [] }
  assert.deepEqual(slots(sentenceParts(unknown, {})).map((s) => s.key), ['measure', 'by'])
})

test('comparing two groups reads as a sentence and offers both groups', () => {
  const compare = {
    key: 'compare', name: 'Compare two groups', description: '', example: '',
    inputs: [measureIn, { key: 'by', label: 'Which column', accepts: ['category'], optional: false }],
    options: [aggregate, { key: 'group_a', label: "First group (one of the chosen column's values)", choices: [] },
              { key: 'group_b', label: "Second group (one of the chosen column's values)", choices: [] }],
  }
  const inputs = { measure: 'employees.annual_ctc', by: 'employees.department' }
  assert.equal(
    previewSentence(compare, inputs, { aggregate: 'average', group_a: 'Engineering', group_b: 'Sales' }, LABELS),
    'Average Annual CTC: Engineering against Sales in Department',
  )
  // Nothing chosen yet reads as gaps, never as a wrong promise.
  assert.equal(previewSentence(compare, {}, { aggregate: 'average' }, LABELS), `Average ${MISSING}: ${MISSING} against ${MISSING} in ${MISSING}`)
  assert.equal(shortLabel("First group (one of the chosen column's values)"), 'First group')
})

test('the two group pickers offer the chosen column\'s own values', () => {
  const columns = [
    { ref: 'employees.department', label: 'department', table_label: 'employees.csv', kind: 'category', values: ['Engineering', 'Sales'] },
    { ref: 'employees.annual_ctc', label: 'annual_ctc', table_label: 'employees.csv', kind: 'measure', values: [] },
  ]
  const compare = { key: 'compare', name: 'Compare', description: '', example: '', inputs: [measureIn, byIn], options: [] }
  assert.deepEqual(groupValues(compare, { measure: 'employees.annual_ctc', by: 'employees.department' }, columns), ['Engineering', 'Sales'])
  // No group column chosen yet: nothing to offer, rather than the wrong column's values.
  assert.deepEqual(groupValues(compare, { measure: 'employees.annual_ctc' }, columns), [])
})

test('an analysis whose groups are not chosen cannot be run', () => {
  const compare = {
    key: 'compare', name: 'Compare', description: '', example: '', inputs: [measureIn, byIn],
    options: [aggregate, { key: 'group_a', label: 'First group', choices: [] }, { key: 'group_b', label: 'Second group', choices: [] }],
  }
  const chosen = { measure: 'employees.annual_ctc', by: 'employees.department' }
  assert.equal(isComplete(compare, chosen, { aggregate: 'sum' }), false)
  assert.equal(isComplete(compare, chosen, { aggregate: 'sum', group_a: 'Engineering' }), false)
  assert.equal(isComplete(compare, chosen, { aggregate: 'sum', group_a: 'Engineering', group_b: 'Sales' }), true)
  // An option with fixed choices is preselected, so it never blocks Run.
  assert.equal(isComplete(kind('breakdown', [measureIn, byIn], [aggregate]), { measure: 'a', by: 'b' }), true)
})

test('a refusal from the server lands beside the picker it names', () => {
  const pivot = kind('pivot', [measureIn, { key: 'by', label: 'Rows', accepts: ['category'], optional: false },
                               { key: 'across', label: 'Columns', accepts: ['category'], optional: false }], [aggregate])
  assert.deepEqual(slotForMessage('Break down needs a column for “Split by”. Pick one from the list.', kind('breakdown', [measureIn, byIn])), {
    of: 'input',
    key: 'by',
  })
  assert.deepEqual(slotForMessage('Rows and Columns have to be two different columns.', pivot), { of: 'input', key: 'by' })
  const compare = kind('compare', [measureIn, byIn], [{ key: 'group_a', label: "First group (one of the chosen column's values)", choices: [] }])
  // The label is matched up to its parenthesis, so the server's own punctuation — a curly
  // apostrophe where the label has a straight one — still lands on the right picker.
  assert.deepEqual(slotForMessage('Choose a value for “First group (one of the chosen column’s values)”.', compare), {
    of: 'option',
    key: 'group_a',
  })
  // Nothing it names: the message belongs beside Run, not beside a guess.
  assert.equal(slotForMessage('Pick two different numbers. A column always moves with itself.', pivot), null)
})
