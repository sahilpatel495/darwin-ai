// Run from frontend/: node --test "src/**/*.test.mjs"
// Plain Node test runner (Node strips the TypeScript types itself), so no test dependency is needed.
import test from 'node:test'
import assert from 'node:assert/strict'
import { linkLine, metricProblem, needsALook, overviewLine, parseSynonyms, receiptLines, unionLine } from './wording.ts'

const cleanHealth = {
  rows: 24,
  columns: 4,
  skipped_title_rows: 0,
  dropped_total_rows: 0,
  duplicate_rows: 0,
  duplicates_removed: false,
  date_format: null,
  date_format_ambiguous: false,
  coercions: [],
  null_hotspots: {},
  pii_columns: [],
  preserved_id_columns: [],
  warnings: [],
}

// The salary register from src/fixtures/catalog.json, plus PII columns.
const messyHealth = {
  ...cleanHealth,
  skipped_title_rows: 3,
  dropped_total_rows: 1,
  duplicate_rows: 6,
  duplicates_removed: true,
  date_format: 'DD/MM/YYYY',
  coercions: [
    { column: 'gross', to_type: 'currency', detail: 'Parsed ₹ strings', unparseable: 3, examples: ['TBD', 'N/A'] },
    { column: 'pay_month', to_type: 'date', detail: 'Parsed day-first dates', unparseable: 0, examples: [] },
    { column: 'net', to_type: 'currency', detail: 'Parsed ₹ strings', unparseable: 0, examples: [] },
  ],
  null_hotspots: { net: 0.08 },
  pii_columns: ['name', 'email'],
  preserved_id_columns: ['emp_code'],
  warnings: ['Dropped 2 empty columns.'],
}

/** The receipt as the analyst reads it: "label  amount". */
const rendered = (health, label) => receiptLines(health, label).map((line) => (line.amount ? `${line.label}  ${line.amount}` : line.label))
const find = (health, start) => receiptLines(health).find((line) => line.label.startsWith(start))

test('receipt itemises every DataHealth field, with the count on the right', () => {
  const lines = rendered(messyHealth)
  for (const expected of [
    'Title rows skipped above the column names  3',
    'Total rows dropped, so sums are not counted twice  1',
    'Exact duplicate rows removed  6',
    'Unreadable ₹ amounts in gross left empty  3',
    'Read as dates  1',
    'Dates read as  DD/MM/YYYY',
    'Kept as text to preserve leading zeros  1',
    'Personal-data columns hidden from the AI  2',
  ]) {
    assert.ok(lines.includes(expected), `missing "${expected}" in:\n${lines.join('\n')}`)
  }
})

test('counts are the right column, and examples and column names are the note under the label', () => {
  assert.equal(find(messyHealth, 'Unreadable').note, 'For example TBD, N/A.')
  assert.equal(find(messyHealth, 'Personal-data').note, 'name, email')
  assert.equal(find(messyHealth, 'Kept as text').note, 'emp_code')
})

test('receipt names columns by the header in the file when it is told how', () => {
  const headers = { gross: 'Gross', pay_month: 'Pay Month', net: 'Net', emp_code: 'Emp Code' }
  const lines = rendered(messyHealth, (column) => headers[column] ?? column)
  for (const expected of ['Unreadable ₹ amounts in Gross left empty  3', 'Read as dates  1', 'Values left empty in Net  8%', 'Kept as text to preserve leading zeros  1']) {
    assert.ok(lines.includes(expected), `missing "${expected}" in:\n${lines.join('\n')}`)
  }
  assert.equal(receiptLines(messyHealth, (c) => headers[c] ?? c).find((l) => l.label === 'Read as dates').note, 'Pay Month')
})

test('duplicates that were kept are a warning with the reason, not a removal', () => {
  const line = find({ ...cleanHealth, duplicate_rows: 4 }, 'Exact duplicate')
  assert.equal(line.label, 'Exact duplicate rows kept')
  assert.equal(line.amount, '4')
  assert.equal(line.tone, 'warn')
  assert.match(line.note, /no ID column/)
})

test('unreadable values and ambiguous dates are warnings; clean conversions are grouped by type', () => {
  const lines = receiptLines({ ...messyHealth, date_format_ambiguous: true })
  assert.equal(lines.find((l) => l.label.startsWith('Unreadable')).tone, 'warn')
  assert.equal(lines.find((l) => l.label === 'Dates read as').tone, 'warn')
  assert.ok(lines.some((l) => l.label === 'Read as ₹ amounts' && l.note === 'net' && l.tone === 'ok'))
  // gross has its own warning line, so it is not repeated in the grouped line.
  assert.ok(!lines.some((l) => l.label === 'Read as ₹ amounts' && l.note.includes('gross')))
})

test('mostly-empty columns and backend warnings are passed on as warnings', () => {
  const lines = receiptLines(messyHealth)
  assert.ok(lines.some((l) => l.label === 'Values left empty in net' && l.amount === '8%' && l.tone === 'warn'))
  assert.ok(lines.some((l) => l.label === 'Dropped 2 empty columns.' && l.amount === undefined && l.tone === 'warn'))
})

test('a clean file still gets a receipt line, so silence never looks like a skipped check', () => {
  assert.deepEqual(receiptLines(cleanHealth), [{ tone: 'ok', label: 'No cleaning was needed', note: 'Every value was read as it appears in the file.' }])
})

test('long column lists are capped so a 300-column file stays readable', () => {
  const pii = Array.from({ length: 10 }, (_, i) => `col_${i + 1}`)
  const line = find({ ...cleanHealth, pii_columns: pii }, 'Personal-data')
  assert.equal(line.amount, '10')
  assert.equal(line.note, 'col_1, col_2, col_3, col_4, col_5, col_6 and 4 more')
})

test('the amber mark says the first thing to check and how many others there are', () => {
  assert.equal(needsALook(receiptLines(cleanHealth)), null)
  assert.equal(needsALook(receiptLines({ ...cleanHealth, duplicate_rows: 4 })), 'Exact duplicate rows kept: 4.')
  assert.equal(needsALook(receiptLines(messyHealth)), 'Unreadable ₹ amounts in gross left empty: 3, and 2 more to check.')
  // A backend warning is already a whole sentence; the joined sentence must not gain a second stop.
  assert.equal(needsALook(receiptLines({ ...cleanHealth, warnings: ['Dropped 2 empty columns.'] })), 'Dropped 2 empty columns.')
})

const catalog = {
  tables: [
    { name: 'employees', is_view: false, health: { ...cleanHealth, pii_columns: ['name', 'email'] } },
    { name: 'salary_register', is_view: false, health: cleanHealth },
    { name: 'attendance_all', is_view: true, health: cleanHealth },
  ],
  relationships: [{ id: 'a', status: 'active' }, { id: 'b', status: 'suggested' }],
  unions: [{ id: 'attendance_all', status: 'active' }],
}

test('the overview line counts what is loaded, and leaves out what is zero', () => {
  assert.equal(overviewLine(catalog), '2 tables, 2 links, 1 combined view, 2 personal-data columns hidden')
  // A removed link and a removed view drop straight out of the line.
  assert.equal(
    overviewLine({ ...catalog, relationships: [{ id: 'a', status: 'rejected' }], unions: [{ id: 'v', status: 'rejected' }] }),
    '2 tables, 2 personal-data columns hidden',
  )
  assert.equal(overviewLine({ tables: [{ name: 'one', is_view: false, health: cleanHealth }], relationships: [{ id: 'a', status: 'active' }], unions: [] }), '1 table, 1 link')
})

const link = {
  id: 'employees.emp_id->salary_register.emp_code',
  left_table: 'employees',
  left_column: 'emp_id',
  right_table: 'salary_register',
  right_column: 'emp_code',
  match_left: 1,
  match_right: 1,
  cardinality: '1:N',
  status: 'active',
}

// What Links.tsx passes in: SQL table name -> the file the analyst uploaded.
const files = { employees: 'employees.csv', salary_register: 'Salary_Register.xlsx', attendance_q1: 'attendance_q1.csv', attendance_q2: 'attendance_q2.csv' }
const name = (table) => files[table] ?? table

test('a link is one sentence, named by its files and never by SQL identifiers', () => {
  assert.equal(
    linkLine(link, name).sentence,
    'employees.csv and Salary_Register.xlsx are linked on emp_id and emp_code. 100% of rows in employees.csv have a match in Salary_Register.xlsx.',
  )
  assert.equal(linkLine(link, name).pair, 'employees.csv and Salary_Register.xlsx')
  assert.match(linkLine({ ...link, right_column: 'emp_id' }, name).sentence, /linked on emp_id\. /)
})

test('the match quoted is the better direction (the one that switches a link on), rounded down so 99.6% never shows as 100%', () => {
  assert.match(linkLine({ ...link, match_left: 0.996, match_right: 0.5 }, name).sentence, /99% of rows in employees\.csv have a match in Salary_Register\.xlsx\./)
  // A bonus sheet covering a quarter of the staff: every bonus row finds its employee.
  assert.match(linkLine({ ...link, match_left: 0.25, match_right: 1 }, name).sentence, /100% of rows in Salary_Register\.xlsx have a match in employees\.csv\./)
  // 0.29 * 100 is 28.999999999999996 in floating point; the analyst must still see 29%.
  assert.match(linkLine({ ...link, match_left: 0.29, match_right: 0.1 }, name).sentence, /29% of rows/)
})

test('a many-to-many link says out loud that it can double a total', () => {
  assert.match(linkLine({ ...link, cardinality: 'N:M' }, name).sentence, /counted more than once\.$/)
  assert.ok(!linkLine(link, name).sentence.includes('more than once'))
})

test('a combined view is named by the files it stacks', () => {
  const view = unionLine({ id: 'attendance_all', view_name: 'attendance_all', tables: ['attendance_q1', 'attendance_q2'], status: 'active' }, name)
  assert.equal(view.pair, 'attendance_q1.csv and attendance_q2.csv')
  assert.equal(view.sentence, 'attendance_q1.csv and attendance_q2.csv have the same columns, so a question that spans them reads one combined view.')
  assert.equal(unionLine({ tables: ['employees', 'attendance_q1', 'attendance_q2'] }, name).pair, 'employees.csv, attendance_q1.csv and attendance_q2.csv')
})

test('synonyms are trimmed, de-duplicated without regard to case, and empties dropped', () => {
  assert.deepEqual(parseSynonyms(' churn, Turnover ,, churn,  TURNOVER, exits '), ['churn', 'Turnover', 'exits'])
  assert.deepEqual(parseSynonyms(''), [])
})

test('a glossary edit the server would refuse is stopped with a sentence, not sent', () => {
  assert.equal(metricProblem('Leavers divided by average headcount.', ['churn', 'turnover']), null)
  assert.equal(metricProblem('Leavers divided by average headcount.', []), null)
  // Spaces only: the text box's own "required" check lets this through.
  assert.match(metricProblem('   \n ', []), /^Write a definition before saving/)
  const twentyOne = Array.from({ length: 21 }, (_, i) => `name ${i}`)
  assert.equal(metricProblem('ok', twentyOne.slice(0, 20)), null)
  assert.match(metricProblem('ok', twentyOne), /^Keep to 20 other names or fewer\. There are 21 now\./)
  // A pasted sentence with no commas becomes one very long "name".
  assert.equal(metricProblem('ok', ['s'.repeat(80)]), null)
  const tooLong = metricProblem('ok', ['churn', 's'.repeat(81)])
  assert.match(tooLong, /is longer than 80 characters/)
  assert.ok(tooLong.length < 160, 'the sentence quotes only the start of the long name')
})
