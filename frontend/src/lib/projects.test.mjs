// Run from frontend/: node --test "src/**/*.test.mjs"
// Node has no localStorage, so the tests bring their own — which also lets a quota error and a
// browser with storage switched off be tested, the two cases that decide whether the app survives.
import test from 'node:test'
import assert from 'node:assert/strict'

function fakeStorage({ failTimes = 0 } = {}) {
  const store = new Map()
  let fails = failTimes
  return {
    store,
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => {
      if (fails > 0) {
        fails--
        const error = new Error('exceeded the quota')
        error.name = 'QuotaExceededError'
        throw error
      }
      store.set(key, value)
    },
    removeItem: (key) => store.delete(key),
  }
}

globalThis.localStorage = fakeStorage()

const {
  createProject,
  deleteProject,
  fileNamesFrom,
  getProject,
  lastOpened,
  listProjects,
  projectName,
  projectSummary,
  shrink,
  trimAnswer,
  trimTurns,
  updateProject,
} = await import('./projects.ts')

const KEY = 'verity.projects.v1'
const stored = () => JSON.parse(globalThis.localStorage.getItem(KEY) ?? '[]')

const answer = (rows = 0, payloads = 1) => ({
  id: 'a1',
  kind: 'answer',
  question: 'q',
  text: 't',
  table: { columns: ['x'], rows: Array.from({ length: rows }, (_, i) => [i]), display: Array.from({ length: rows }, (_, i) => [`${i}`]), row_count: rows, truncated: false },
  work: { payloads: Array.from({ length: payloads }, (_, i) => ({ purpose: 'generate', messages: [{ role: 'user', content: `m${i}` }] })) },
})

const turn = (n) => ({ id: `t${n}`, question: `q${n}`, answer: answer(0, 1), askedAt: `2026-09-0${1}T00:0${0}:00Z` })

test('a stored answer keeps 200 table rows and says it was cut', () => {
  const kept = trimAnswer(answer(250))
  assert.equal(kept.table.rows.length, 200)
  assert.equal(kept.table.display.length, 200)
  assert.equal(kept.table.truncated, true)
  assert.equal(kept.table.row_count, 250, 'the real count is still the truth about the result')
  assert.equal(trimAnswer(answer(7)).table.truncated, false, 'a small table is left alone')
  assert.equal(trimAnswer({ ...answer(0), table: null }).table, null)
})

test('only the first model payload keeps its messages', () => {
  const kept = trimAnswer(answer(0, 3))
  assert.equal(kept.work.payloads.length, 3)
  assert.equal(kept.work.payloads[0].messages.length, 1)
  assert.deepEqual(kept.work.payloads[1].messages, [])
  assert.deepEqual(kept.work.payloads[2].messages, [])
})

test('a project keeps its newest 60 turns', () => {
  const turns = trimTurns(Array.from({ length: 70 }, (_, i) => turn(i)))
  assert.equal(turns.length, 60)
  assert.equal(turns[0].id, 't10')
  assert.equal(turns.at(-1).id, 't69')
})

test('shrink drops the oldest half of the biggest project and stops when nothing is left', () => {
  const big = { id: 'b', turns: Array.from({ length: 10 }, (_, i) => turn(i)) }
  const small = { id: 's', turns: [turn(0)] }
  const after = shrink([small, big])
  assert.equal(after[1].turns.length, 5)
  assert.equal(after[1].turns[0].id, 't5', 'the newest half survives')
  assert.equal(after[0].turns.length, 1, 'the smaller project is untouched')
  assert.equal(shrink([{ id: 'a', turns: [] }]), null)
  assert.equal(shrink([]), null)
})

test('a project is named after its first file', () => {
  assert.equal(projectName(['Salary_Register_2025.xlsx', 'a.csv', 'b.csv', 'c.csv', 'd.csv', 'e.csv']), 'Salary Register 2025 and 5 more')
  assert.equal(projectName(['employees.csv']), 'employees')
  assert.equal(projectName([], true), 'Sample HR company')
  assert.equal(projectName([]), 'Untitled project')
})

test('the row says how much work is in a project', () => {
  assert.equal(projectSummary({ turns: [], savedAnswerIds: [] }), 'No questions yet')
  assert.equal(projectSummary({ turns: [turn(1)], savedAnswerIds: [] }), '1 question')
  assert.equal(projectSummary({ turns: [turn(1), turn(2)], savedAnswerIds: ['a'] }), '2 questions, 1 saved')
})

test('last opened reads as a person would say it', () => {
  const now = new Date(2026, 8, 20, 10, 0)
  assert.equal(lastOpened(new Date(2026, 8, 20, 9, 0).toISOString(), now), 'Opened today')
  assert.equal(lastOpened(new Date(2026, 8, 19, 23, 0).toISOString(), now), 'Opened yesterday')
  assert.equal(lastOpened(new Date(2026, 8, 12).toISOString(), now), 'Opened on 12 September')
  assert.match(lastOpened(new Date(2025, 8, 12).toISOString(), now), /2025/)
  assert.equal(lastOpened('not a date', now), 'Opened earlier')
})

test('combined views are not files the analyst has to re-attach', () => {
  const catalog = {
    tables: [
      { source_file: 'employees.csv', is_view: false },
      { source_file: 'Salary_Register_2025.xlsx', is_view: false },
      { source_file: 'Salary_Register_2025.xlsx', is_view: false },
      { source_file: 'a.csv + b.csv', is_view: true },
    ],
  }
  assert.deepEqual(fileNamesFrom(catalog), ['employees.csv', 'Salary_Register_2025.xlsx'])
})

test('projects round-trip through storage, newest first', () => {
  const first = createProject({ name: 'One', isSample: false, fileNames: ['a.csv'], sessionId: 's1' })
  const second = createProject({ name: 'Two', isSample: true, fileNames: [], sessionId: 's2' })
  assert.deepEqual(
    listProjects().map((project) => project.name),
    ['Two', 'One'],
  )
  updateProject(first.id, { name: 'Renamed', lastOpenedAt: new Date(Date.now() + 1000).toISOString() })
  assert.equal(getProject(first.id).name, 'Renamed')
  assert.equal(listProjects()[0].name, 'Renamed', 'opening a project moves it to the top')
  deleteProject(second.id)
  assert.equal(getProject(second.id), null)
  assert.equal(stored().length, 1)
})

test('turns are trimmed on the way into storage, not on the way out', () => {
  const project = createProject({ name: 'Trim', isSample: false, fileNames: [], sessionId: 's' })
  updateProject(project.id, { turns: Array.from({ length: 64 }, (_, i) => turn(i)) })
  assert.equal(getProject(project.id).turns.length, 60)
  deleteProject(project.id)
})

test('a quota error drops the oldest turns of the biggest project and saves anyway', () => {
  globalThis.localStorage = fakeStorage()
  const project = createProject({ name: 'Full', isSample: false, fileNames: [], sessionId: 's' })
  updateProject(project.id, { turns: Array.from({ length: 10 }, (_, i) => turn(i)) })

  const before = globalThis.localStorage.getItem(KEY)
  globalThis.localStorage = fakeStorage({ failTimes: 1 })
  globalThis.localStorage.store.set(KEY, before)
  updateProject(project.id, { name: 'Still saved' })

  const saved = getProject(project.id)
  assert.equal(saved.name, 'Still saved')
  assert.equal(saved.turns.length, 5, 'the oldest half went, the project stayed')
})

test('a browser with storage switched off loses the history, not the app', () => {
  globalThis.localStorage = fakeStorage({ failTimes: Infinity })
  assert.deepEqual(listProjects(), [])
  const project = createProject({ name: 'Nowhere', isSample: false, fileNames: [], sessionId: 's' })
  assert.equal(project.name, 'Nowhere', 'creating a project still returns one to work with')
  assert.equal(getProject(project.id), null)
  assert.equal(updateProject(project.id, { name: 'x' }), null)
  assert.doesNotThrow(() => deleteProject(project.id))
})
