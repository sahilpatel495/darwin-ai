// Run from frontend/: node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { glyphName, typedPlaceholder } from './prompts.ts'

test('a glyph name from a newer server falls back rather than drawing nothing', () => {
  assert.equal(glyphName('rupee'), 'rupee')
  assert.equal(glyphName('hologram'), 'sparkles')
  assert.equal(glyphName(''), 'sparkles')
})

test('the placeholder types one example out, holds it, then starts the next from nothing', () => {
  const examples = ['abc', 'de']
  assert.equal(typedPlaceholder(examples, 0), 'a')
  assert.equal(typedPlaceholder(examples, 120), 'abc')
  assert.equal(typedPlaceholder(examples, 2000), 'abc', 'it holds the whole question long enough to read')
  assert.equal(typedPlaceholder(examples, 3 * 55 + 2400), 'd', 'then the next one starts')
  // The cycle repeats, and a clock that started before this composer did cannot break it.
  assert.equal(typedPlaceholder(examples, 5 * 55 + 2 * 2400), 'a')
  assert.equal(typedPlaceholder(examples, -10), typedPlaceholder(examples, 5 * 55 + 2 * 2400 - 10))
  assert.equal(typedPlaceholder([], 500), '')
})
