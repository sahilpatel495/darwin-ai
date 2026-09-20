// Run from frontend/: node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { csvFileName, toCsv } from './csv.ts'

test('columns are the header, rows follow, line ends are CRLF', () => {
  assert.equal(toCsv(['department', 'total_gross'], [['Sales', 225000.5], ['HR', null]]), 'department,total_gross\r\nSales,225000.5\r\nHR,\r\n')
})

test('commas, quotes and line breaks are quoted the RFC 4180 way', () => {
  assert.equal(toCsv(['note'], [['a, b'], ['say "hi"'], ['two\nlines']]), 'note\r\n"a, b"\r\n"say ""hi"""\r\n"two\nlines"\r\n')
})

test('text that a spreadsheet would run as a formula is neutralised with a single quote', () => {
  const csv = toCsv(['=cmd'], [['=HYPERLINK("http://evil","x")'], ['+1+1'], ['-2+3'], ['@SUM(A1)'], ['\tTab'], ['safe = text']])
  assert.deepEqual(csv.trimEnd().split('\r\n'), ["'=cmd", `"'=HYPERLINK(""http://evil"",""x"")"`, "'+1+1", "'-2+3", "'@SUM(A1)", "'\tTab", 'safe = text'])
})

test('a negative number stays a number, so the column still sums in Excel', () => {
  assert.equal(toCsv(['change'], [[-1200.5], [true]]), 'change\r\n-1200.5\r\ntrue\r\n')
})

test('the file name is the question, slugified, with a fallback when nothing survives', () => {
  assert.equal(csvFileName('What was total gross pay, by dept?'), 'what-was-total-gross-pay-by-dept.csv')
  assert.equal(csvFileName('../../etc/passwd'), 'etc-passwd.csv')
  assert.equal(csvFileName('वेतन?'), 'verity-result.csv')
  assert.ok(csvFileName('a'.repeat(59) + ' b '.repeat(50)).length <= 64)
  assert.ok(!csvFileName('x'.repeat(59) + ' y').includes('-.csv'), 'no dash left dangling where the name was cut')
})
