// Run from frontend/: node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { columnLabel, labelOf, optionLabel, plainTables } from './tables.ts'

const column = (name, label) => ({ name, label })
const tables = [
  { name: 'salary_register_2025_register', source_file: 'Salary_Register_2025.xlsx', sheet: 'Register', columns: [column('gross', 'Gross')] },
  { name: 'salary_register_2025_bonuses', source_file: 'Salary_Register_2025.xlsx', sheet: 'Bonuses', columns: [] },
  { name: 'performance_reviews', source_file: 'performance_reviews.xlsx', sheet: 'Reviews', columns: [] },
  { name: 'employees', source_file: 'employees.csv', sheet: null, columns: [column('ctc', 'ctc')] },
  { name: 'sales', source_file: 'sales.csv', sheet: null, columns: [] },
]

test('a table is called by its file; the sheet is named only when the workbook gave several tables', () => {
  assert.equal(labelOf('salary_register_2025_register', tables), 'Salary_Register_2025.xlsx (sheet Register)')
  assert.equal(labelOf('performance_reviews', tables), 'performance_reviews.xlsx')
  assert.equal(labelOf('employees', tables), 'employees.csv')
  assert.equal(labelOf('dropped_since', tables), 'dropped_since')
})

test('table names in a server sentence become file names', () => {
  assert.equal(
    plainTables('6 exact duplicate rows were removed from salary_register_2025_register before answering.', tables),
    '6 exact duplicate rows were removed from Salary_Register_2025.xlsx (sheet Register) before answering.',
  )
  assert.equal(plainTables('Nothing matched in performance_reviews.', tables), 'Nothing matched in performance_reviews.xlsx.')
})

test('ordinary words and table.column references are left alone', () => {
  assert.equal(plainTables('Total sales for employees in 2025.', tables), 'Total sales for employees in 2025.')
  const link = 'The link employees.emp_id = salary_register_2025_register.emp_code is a suggestion.'
  assert.equal(plainTables(link, tables), link)
  assert.equal(plainTables('See my_salary_register_2025_register_old.', tables), 'See my_salary_register_2025_register_old.')
})

test('a column reference reads as "header in file"; an unknown one is shown as it came', () => {
  assert.equal(columnLabel('salary_register_2025_register.gross', tables), 'Gross in Salary_Register_2025.xlsx (sheet Register)')
  assert.equal(columnLabel('employees.nope', tables), 'employees.nope')
})

test('a clarify chip drops the SQL reference and does not say the column name twice', () => {
  const gross = { label: 'Gross pay (salary_register_2025_register.gross)', value: 'salary_register_2025_register.gross' }
  assert.equal(optionLabel(gross, tables), 'Gross pay · Gross in Salary_Register_2025.xlsx (sheet Register)')
  assert.equal(optionLabel({ label: 'ctc (employees.ctc)', value: 'employees.ctc' }, tables), 'ctc in employees.csv')
  assert.equal(optionLabel({ label: 'Something else', value: 'not a column' }, tables), 'Something else')
})
