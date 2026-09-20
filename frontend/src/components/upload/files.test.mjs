// Run from frontend/: node --test "src/components/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { ACCEPT_ATTRIBUTE, MAX_FILES_PER_UPLOAD, MAX_FILE_BYTES, checkFiles, nothingAdded } from './files.ts'

const file = (name, size = 1024) => ({ name, size })

test('accepts exactly the types from the brief, whatever the letter case', () => {
  const picked = [file('employees.csv'), file('export.TSV'), file('Salary_Register_2025.xlsx'), file('macro.xlsm')]
  const { accepted, problems } = checkFiles(picked)
  assert.deepEqual(accepted, picked)
  assert.deepEqual(problems, [])
  assert.equal(ACCEPT_ATTRIBUTE, '.csv,.tsv,.xlsx,.xlsm')
})

test('an unsupported type is skipped with a sentence naming the file and what is supported', () => {
  const { accepted, problems } = checkFiles([file('employees.csv'), file('notes.pdf')])
  assert.deepEqual(accepted.map((f) => f.name), ['employees.csv'])
  assert.deepEqual(problems, ['notes.pdf was skipped. Verity reads .csv, .tsv, .xlsx and .xlsm files.'])
})

test('a double extension cannot sneak past the check', () => {
  assert.equal(checkFiles([file('payroll.csv.exe')]).accepted.length, 0)
  assert.equal(checkFiles([file('csv')]).accepted.length, 0)
})

test('old .xls gets its own next step, because HR systems still export it', () => {
  const { accepted, problems } = checkFiles([file('old.xls')])
  assert.equal(accepted.length, 0)
  assert.deepEqual(problems, ['old.xls is in the old Excel format. Open it in Excel, save it as .xlsx, and add it again.'])
})

test('empty and oversized files are stopped before any upload starts', () => {
  const { accepted, problems } = checkFiles([file('blank.csv', 0), file('huge.csv', MAX_FILE_BYTES + 1), file('edge.csv', MAX_FILE_BYTES)])
  assert.deepEqual(accepted.map((f) => f.name), ['edge.csv'])
  assert.deepEqual(problems, [
    'blank.csv is empty. Export it again and check it has rows.',
    'huge.csv is larger than 25 MB. Remove the sheets or columns you do not need and add it again.',
  ])
})

test('more files than the server takes at once: the first ten go, the rest get a sentence, nothing is uploaded in vain', () => {
  const picked = Array.from({ length: 12 }, (_, i) => file(`month_${i + 1}.csv`))
  const { accepted, problems } = checkFiles([file('notes.pdf'), ...picked])
  assert.equal(MAX_FILES_PER_UPLOAD, 10)
  assert.deepEqual(accepted.map((f) => f.name), picked.slice(0, 10).map((f) => f.name))
  assert.deepEqual(problems, [
    'notes.pdf was skipped. Verity reads .csv, .tsv, .xlsx and .xlsm files.',
    'Only 10 files can be added at a time, so the last 2 were left out. Add them once these have loaded.',
  ])
  assert.deepEqual(checkFiles(picked.slice(0, 10)).problems, [])
  assert.match(checkFiles(picked.slice(0, 11)).problems[0], /the last 1 was left out\. Add it once/)
})

test('a very long file name is kept whole in its sentence, so the analyst can still tell which file it was', () => {
  const name = `${'x'.repeat(200)}.docx`
  assert.deepEqual(checkFiles([file(name)]).problems, [`${name} was skipped. Verity reads .csv, .tsv, .xlsx and .xlsm files.`])
})

test('the same file added twice is noticed: the server skips it and returns the catalog unchanged', () => {
  assert.equal(nothingAdded({ version: 3 }, { version: 3 }), true)
  assert.equal(nothingAdded({ version: 3 }, { version: 4 }), false)
  // First upload of a session: there is nothing to have been "already loaded".
  assert.equal(nothingAdded(null, { version: 1 }), false)
})

test('a folder of scans gives a short message, not thirty identical lines', () => {
  const { accepted, problems } = checkFiles([file('employees.csv'), ...Array.from({ length: 30 }, (_, i) => file(`scan_${i}.pdf`))])
  assert.equal(accepted.length, 1)
  assert.equal(problems.length, 6)
  assert.equal(problems[0], 'scan_0.pdf was skipped. Verity reads .csv, .tsv, .xlsx and .xlsm files.')
  assert.equal(problems[5], '25 more files were skipped too. Verity reads .csv, .tsv, .xlsx and .xlsm files of up to 25 MB.')
  // Six skipped files: five sentences and "1 more file", never a count of zero.
  assert.equal(checkFiles(Array.from({ length: 6 }, (_, i) => file(`scan_${i}.pdf`))).problems[5], '1 more file was skipped too. Verity reads .csv, .tsv, .xlsx and .xlsm files of up to 25 MB.')
  assert.equal(checkFiles(Array.from({ length: 5 }, (_, i) => file(`scan_${i}.pdf`))).problems.length, 5)
})
