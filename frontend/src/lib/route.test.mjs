// Run from frontend/: node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { analysesPath, boardPath, guard, overviewPath, parseRoute, projectPath, routeProjectId } from './route.ts'

test('every screen has a route, and the gallery', () => {
  assert.deepEqual(parseRoute('#/'), { name: 'home' })
  assert.deepEqual(parseRoute('#/trust'), { name: 'trust' })
  assert.deepEqual(parseRoute('#/ui'), { name: 'gallery' })
  assert.deepEqual(parseRoute('#/p/abc'), { name: 'project', id: 'abc' })
  assert.deepEqual(parseRoute('#/p/abc/overview'), { name: 'overview', id: 'abc' })
  assert.deepEqual(parseRoute('#/p/abc/analyses'), { name: 'analyses', id: 'abc' })
  assert.deepEqual(parseRoute('#/p/abc/board'), { name: 'board', id: 'abc' })
})

test('a page nobody has heard of is that project, not a dead end', () => {
  assert.deepEqual(parseRoute('#/p/abc/typo'), { name: 'project', id: 'abc' })
  assert.deepEqual(parseRoute('#/p/abc/board/extra'), { name: 'board', id: 'abc' })
})

test('the nav rail knows which project a route is about', () => {
  assert.equal(routeProjectId(parseRoute(overviewPath('abc'))), 'abc')
  assert.equal(routeProjectId(parseRoute(analysesPath('abc'))), 'abc')
  assert.equal(routeProjectId(parseRoute('#/')), null)
  assert.equal(routeProjectId(parseRoute('#/trust')), null)
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
    assert.deepEqual(parseRoute(overviewPath(id)), { name: 'overview', id })
    assert.deepEqual(parseRoute(analysesPath(id)), { name: 'analyses', id })
  }
})

test('a broken percent escape is read literally rather than thrown', () => {
  assert.deepEqual(parseRoute('#/p/%'), { name: 'project', id: '%' })
})

test('a visitor can read about the product but cannot open anybody’s work', () => {
  for (const hash of ['#/', '#/signin', '#/signup', '#/how', '#/trust', '#/ui']) {
    assert.equal(guard(parseRoute(hash), false), null, hash)
  }
  for (const hash of ['#/p/abc', '#/p/abc/overview', '#/p/abc/board', '#/settings', '#/welcome']) {
    assert.equal(guard(parseRoute(hash), false), '#/', hash)
  }
})

test('signing in takes you off the sign-in page and leaves you everywhere else', () => {
  assert.equal(guard(parseRoute('#/signin'), true), '#/home')
  assert.equal(guard(parseRoute('#/signup'), true), '#/home')
  for (const hash of ['#/', '#/home', '#/welcome', '#/settings', '#/p/abc', '#/trust']) {
    assert.equal(guard(parseRoute(hash), true), null, hash)
  }
})
