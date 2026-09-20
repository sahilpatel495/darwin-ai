// Run from frontend/: node --test "src/components/**/*.test.mjs"
// Plain Node test runner (Node strips the TypeScript types itself), so no test dependency is needed.
import test from 'node:test'
import assert from 'node:assert/strict'
import { linkExplanation, linkLabel, matchPercent, metricProblem, parseSynonyms, receiptLines, unionLabel } from './wording.ts'

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

const texts = (health) => receiptLines(health).map((line) => line.text)

test('receipt turns every DataHealth field into the sentence from the brief', () => {
  const lines = texts(messyHealth)
  for (const expected of [
    'Skipped 3 title rows',
    'Dropped 1 total row',
    'Removed 6 exact duplicate rows',
    'gross: parsed ₹ amounts, 3 unreadable values left empty (TBD, N/A)',
    'Dates read as DD/MM/YYYY',
    'PII columns hidden from the model: name, email',
    'Kept as text to preserve leading zeros: emp_code',
  ]) {
    assert.ok(
      lines.some((text) => text.startsWith(expected)),
      `missing "${expected}" in:\n${lines.join('\n')}`,
    )
  }
})

test('receipt uses singular and plural correctly', () => {
  const lines = texts({ ...cleanHealth, skipped_title_rows: 1, dropped_total_rows: 2, duplicate_rows: 1, duplicates_removed: true })
  assert.ok(lines.some((t) => t.startsWith('Skipped 1 title row ')), lines.join('\n'))
  assert.ok(lines.some((t) => t.startsWith('Dropped 2 total rows ')), lines.join('\n'))
  assert.ok(lines.some((t) => t.startsWith('Removed 1 exact duplicate row.')), lines.join('\n'))
})

test('duplicates that were kept are reported as a warning, not as removed', () => {
  const line = receiptLines({ ...cleanHealth, duplicate_rows: 4 }).find((l) => l.text.includes('duplicate'))
  assert.ok(line.text.startsWith('Found 4 exact duplicate rows and kept them'), line.text)
  assert.equal(line.tone, 'warn')
})

test('unreadable values and ambiguous dates are warnings; clean conversions are grouped by type', () => {
  const lines = receiptLines({ ...messyHealth, date_format_ambiguous: true })
  assert.equal(lines.find((l) => l.text.startsWith('gross:')).tone, 'warn')
  assert.equal(lines.find((l) => l.text.startsWith('Dates read as')).tone, 'warn')
  assert.ok(lines.some((l) => l.text === 'Read as ₹ amounts: net.' && l.tone === 'ok'))
  assert.ok(lines.some((l) => l.text === 'Read as dates: pay_month.'))
  // gross has its own warning line, so it is not repeated in the grouped line.
  assert.ok(!lines.some((l) => l.text.startsWith('Read as ₹ amounts') && l.text.includes('gross')))
})

test('mostly-empty columns and backend warnings are passed on as warnings', () => {
  const lines = receiptLines(messyHealth)
  assert.ok(lines.some((l) => l.text === 'net: 8% of values are empty.' && l.tone === 'warn'))
  assert.ok(lines.some((l) => l.text === 'Dropped 2 empty columns.' && l.tone === 'warn'))
})

test('a clean file still gets a receipt line, so silence never looks like a skipped check', () => {
  assert.deepEqual(receiptLines(cleanHealth), [{ tone: 'ok', text: 'No cleaning was needed. Every value was read as it appears in the file.' }])
})

test('long column lists are capped so a 300-column file stays readable', () => {
  const pii = Array.from({ length: 10 }, (_, i) => `col_${i + 1}`)
  const line = texts({ ...cleanHealth, pii_columns: pii }).find((t) => t.startsWith('PII columns'))
  assert.equal(line, 'PII columns hidden from the model: col_1, col_2, col_3, col_4, col_5, col_6 and 4 more.')
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

test('link label matches the brief', () => {
  assert.equal(linkLabel(link), 'employees.emp_id ↔ salary_register.emp_code · 100% · 1:N')
})

test('match percent is the weaker direction, rounded down so 99.6% never shows as 100%', () => {
  assert.equal(matchPercent({ ...link, match_left: 0.996, match_right: 1 }), 99)
  assert.equal(matchPercent({ ...link, match_left: 1, match_right: 0.62 }), 62)
  // 0.29 * 100 is 28.999999999999996 in floating point; the analyst must still see 29%.
  assert.equal(matchPercent({ ...link, match_left: 0.29, match_right: 1 }), 29)
})

test('link explanation says the cardinality in words and warns on many-to-many', () => {
  assert.match(linkExplanation(link), /One employees row can match many salary_register rows/)
  assert.match(linkExplanation({ ...link, cardinality: 'N:M' }), /counted more than once/)
  assert.match(linkExplanation({ ...link, match_left: 0.9, match_right: 1 }), /90% of employees\.emp_id values appear in salary_register/)
})

test('union label names the combined table and its parts', () => {
  assert.equal(
    unionLabel({ id: 'attendance_all', view_name: 'attendance_all', tables: ['attendance_q1', 'attendance_q2'], status: 'active' }),
    'attendance_all = attendance_q1 + attendance_q2',
  )
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
