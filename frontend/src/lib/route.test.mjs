// Run from frontend/: node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { boardPath, parseRoute, projectPath } from './route.ts'

test('the four routes and the gallery', () => {
  assert.deepEqual(parseRoute('#/'), { name: 'home' })
  assert.deepEqual(parseRoute('#/trust'), { name: 'trust' })
  assert.deepEqual(parseRoute('#/ui'), { name: 'gallery' })
  assert.deepEqual(parseRoute('#/p/abc'), { name: 'project', id: 'abc' })
  assert.deepEqual(parseRoute('#/p/abc/board'), { name: 'board', id: 'abc' })
})

test('a first visit has no hash at all, and anything unrecognised lands home', () => {
  assert.deepEqual(parseRoute(''), { name: 'home' })
  assert.deepEqual(parseRoute('#'), { name: 'home' })
  assert.deepEqual(parseRoute('#/p'), { name: 'home' }, 'a project route without an id')
  assert.deepEqual(parseRoute('#/p/'), { name: 'home' })
  assert.deepEqual(parseRoute('#/nowhere'), { name: 'home' })
})

test('ids survive the round trip, including the ones a hash would otherwise split', () => {
  for (const id of ['9f1c-4', 'a/b', 'a b', 'वेतन']) {
    assert.deepEqual(parseRoute(projectPath(id)), { name: 'project', id })
    assert.deepEqual(parseRoute(boardPath(id)), { name: 'board', id })
  }
})

test('a broken percent escape is read literally rather than thrown', () => {
  assert.deepEqual(parseRoute('#/p/%'), { name: 'project', id: '%' })
})
