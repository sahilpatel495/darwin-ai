// Run from frontend/: node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { reorder } from './order.ts'

test('an item swaps with its neighbour', () => {
  assert.deepEqual(reorder(['a', 'b', 'c'], 1, -1), ['b', 'a', 'c'])
  assert.deepEqual(reorder(['a', 'b', 'c'], 1, 1), ['a', 'c', 'b'])
})

test('a move off either end changes nothing, and neither does an item that is not there', () => {
  const list = ['a', 'b', 'c']
  assert.deepEqual(reorder(list, 0, -1), list)
  assert.deepEqual(reorder(list, 2, 1), list)
  assert.deepEqual(reorder(list, -1, 1), list, 'the id was not found in the list')
  assert.deepEqual(reorder([], 0, 1), [])
})

test('the list handed in is left alone', () => {
  const list = ['a', 'b']
  reorder(list, 0, 1)
  assert.deepEqual(list, ['a', 'b'])
})
