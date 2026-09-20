// Run: cd frontend && node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { splitNumber, formatLike } from './countUp.ts'

const roundTrip = (display) => formatLike(splitNumber(display), splitNumber(display).value)

test('a formatted figure splits into prefix, number and suffix', () => {
  assert.deepEqual(
    { ...splitNumber('₹20.40 Cr'), groups: undefined },
    { prefix: '₹', digits: '20.40', suffix: ' Cr', value: 20.4, decimals: 2, groups: undefined },
  )
})

test('counting up never changes how a figure is written', () => {
  for (const display of ['₹20.40 Cr', '12.4%', '1,284', '1,28,400', '₹1,23,45,678.90', '-3.5 days', '0']) {
    assert.equal(roundTrip(display), display, display)
  }
})

test('Indian grouping is rebuilt at the same distances, not in thousands', () => {
  const spec = splitNumber('₹1,28,400')
  assert.equal(formatLike(spec, 128400), '₹1,28,400')
  // Part-way through the count-up the number is shorter; the groups it still has stay right.
  assert.equal(formatLike(spec, 64200), '₹64,200')
})

test('a decimal keeps its places while it counts', () => {
  const spec = splitNumber('₹20.40 Cr')
  assert.equal(formatLike(spec, 8.126), '₹8.13 Cr')
  assert.equal(formatLike(spec, 0), '₹0.00 Cr')
})

test('a figure with no number is left alone', () => {
  assert.equal(splitNumber('Not available'), null)
  assert.equal(splitNumber(''), null)
})

test('a negative figure keeps its sign in front of the separators', () => {
  const spec = splitNumber('-1,284')
  assert.equal(formatLike(spec, -1284), '-1,284')
})
