// Checks for src/lib/format.ts. Lives here because the thread agent owns this directory.
// Run: cd frontend && node --test "src/**/*.test.mjs"   (Node 24 strips the TypeScript types itself)
import test from 'node:test'
import assert from 'node:assert/strict'
import { axisTicks, formatDuration, formatShare, formatTick, formatValue, humanize } from '../../lib/format.ts'

test('plain numbers use Indian digit grouping', () => {
  assert.equal(formatValue(1234567, 'number'), '12,34,567')
  assert.equal(formatValue(12.345, 'number'), '12.35')
  assert.equal(formatValue(168, 'number'), '168')
})

test('currency is compact lakh and crore from one lakh up, matching the backend display strings', () => {
  assert.equal(formatValue(1200000, 'currency_inr'), '₹12.00 L')
  assert.equal(formatValue(633334, 'currency_inr'), '₹6.33 L')
  assert.equal(formatValue(12000000, 'currency_inr'), '₹1.20 Cr')
  assert.equal(formatValue(45000, 'currency_inr'), '₹45,000')
  assert.equal(formatValue(-250000, 'currency_inr'), '-₹2.50 L')
})

test('a value that rounds up to 100 lakh is shown as one crore', () => {
  assert.equal(formatValue(9999999, 'currency_inr'), '₹1.00 Cr')
  assert.equal(formatValue(-250000000, 'currency_inr'), '-₹25.00 Cr')
  assert.equal(formatValue(123456789012.4, 'currency_inr'), '₹12,345.68 Cr')
})

// The same cases docs/PLAN.md pins for the backend's to_display: a tooltip must match the table.
test('below one lakh the exact amount is shown, with paise only when there are any', () => {
  assert.equal(formatValue(99999.5, 'currency_inr'), '₹99,999.50')
  assert.equal(formatValue(45000.75, 'currency_inr'), '₹45,000.75')
  assert.equal(formatValue(99999.996, 'currency_inr'), '₹1.00 L', 'rounds to 1,00,000.00 paise-wise, so it is a lakh')
  assert.equal(formatValue(-1234567.5, 'currency_inr'), '-₹12.35 L')
})

test('a negative that rounds to zero carries no minus sign', () => {
  assert.equal(formatValue(-0.001, 'currency_inr'), '₹0')
  assert.equal(formatValue(-0.04, 'percent'), '0.0%')
  assert.equal(formatValue(-3.25, 'percent'), '-3.3%')
  assert.equal(formatTick(-0.2, 'number'), '-0.2')
})

test('a small rate is not flattened to zero', () => {
  assert.equal(formatValue(0.0045, 'number'), '0.0045')
  assert.equal(formatValue(-0.0001, 'number'), '-0.0001')
  assert.equal(formatValue(0.5, 'number'), '0.5')
})

test('percent values are already percent points and keep one decimal', () => {
  assert.equal(formatValue(28.6, 'percent'), '28.6%')
  assert.equal(formatValue(28, 'percent'), '28.0%')
})

test('missing and non-numeric cells never become NaN', () => {
  assert.equal(formatValue(null, 'number'), '—')
  assert.equal(formatValue(Number.NaN, 'currency_inr'), '—')
  assert.equal(formatValue('Engineering', 'currency_inr'), 'Engineering')
  assert.equal(formatValue(true, 'number'), 'Yes')
})

test('axis ticks are short', () => {
  assert.equal(formatTick(1250000, 'currency_inr'), '₹12.5 L')
  assert.equal(formatTick(300000, 'currency_inr'), '₹3 L')
  assert.equal(formatTick(20000000, 'currency_inr'), '₹2 Cr')
  assert.equal(formatTick(45000, 'currency_inr'), '₹45,000')
  assert.equal(formatTick(2500000, 'number'), '25 L')
  assert.equal(formatTick(170, 'number'), '170')
  assert.equal(formatTick(25, 'percent'), '25%')
})

test('report helpers', () => {
  assert.equal(formatShare(0.925), '92.5%')
  assert.equal(formatShare(1), '100%')
  assert.equal(formatDuration(840), '840 ms')
  assert.equal(formatDuration(2400), '2.4 s')
  assert.equal(formatDuration(undefined), '—', 'a report row with no timing must not read "NaN s"')
  assert.equal(humanize('avg_headcount'), 'Avg headcount')
  assert.equal(humanize('attrition_pct'), 'Attrition %')
  assert.equal(humanize('avg_ctc'), 'Avg CTC')
  assert.equal(humanize('hr_metrics'), 'HR metrics')
  assert.equal(humanize('paid_leave'), 'Paid leave', 'abbreviations only match whole words')
})

test('one axis, one unit: the ruler does not change halfway up', () => {
  // Average salary by department: the largest bar is 1.34 L, so the whole axis stays in rupees
  // rather than reading "₹70,000, ₹1.1 L".
  const salary = axisTicks('currency_inr', 134000)
  assert.equal(salary(0), '₹0')
  assert.equal(salary(70000), '₹70,000')
  assert.equal(salary(140000), '₹1,40,000')
  // Gross pay by month: crore all the way down, including the ticks that are not whole crore.
  const pay = axisTicks('currency_inr', 47300000)
  assert.equal(pay(44000000), '₹4.4 Cr')
  assert.equal(pay(0), '₹0 Cr')
  // Ten lakh and up without reaching a crore: lakh for every tick.
  const mid = axisTicks('currency_inr', 2500000)
  assert.equal(mid(500000), '₹5 L')
  assert.equal(mid(2500000), '₹25 L')
  // Plain numbers and percentages are untouched by the unit rule.
  assert.equal(axisTicks('number', 430)(170), '170')
  assert.equal(axisTicks('percent', 25)(25), '25%')
  assert.equal(axisTicks('currency_inr', 134000)(Number.NaN), '')
})
