// Run from frontend/: node --test "src/**/*.test.mjs"
// The sample listing comes from a server that may not have the endpoint at all, so the parsing
// is the interesting part: anything unexpected has to end as an empty list, never as a crash.
import test from 'node:test'
import assert from 'node:assert/strict'
import { fileSize, parseSampleFiles, sampleFileUrl } from './sample.ts'

test('a listing is read whether it is wrapped or bare', () => {
  const bare = parseSampleFiles([{ name: 'employees.csv', size: 66038, description: 'One row per employee.' }])
  assert.deepEqual(bare, [{ name: 'employees.csv', size: 66038, description: 'One row per employee.' }])

  const wrapped = parseSampleFiles({ files: [{ name: 'sales.csv', bytes: 100, about: 'Orders.' }] })
  assert.deepEqual(wrapped, [{ name: 'sales.csv', size: 100, description: 'Orders.' }])
})

test('a file the server described badly still lists, one it did not name does not', () => {
  const files = parseSampleFiles([{ name: 'a.csv' }, { size: 10 }, { name: '' }, null, 'a.csv'])
  assert.deepEqual(files, [{ name: 'a.csv', size: null, description: '' }])
})

test('anything that is not a listing is no listing at all', () => {
  for (const body of [null, undefined, 42, '<!doctype html>', { detail: 'Not Found' }, { files: 'none' }]) {
    assert.deepEqual(parseSampleFiles(body), [], `${JSON.stringify(body)}`)
  }
})

test('sizes read the way a file browser writes them', () => {
  assert.equal(fileSize(null), '')
  assert.equal(fileSize(0), '0 bytes')
  assert.equal(fileSize(900), '900 bytes')
  assert.equal(fileSize(36340), '35 KB')
  assert.equal(fileSize(1024 * 1000), '1.0 MB')
  assert.equal(fileSize(157386), '154 KB')
})

test('a file name with a space survives the download link', () => {
  assert.equal(sampleFileUrl('Salary Register 2025.xlsx'), '/api/sample/files/Salary%20Register%202025.xlsx')
})
