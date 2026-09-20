// Run from frontend/: node --test "src/**/*.test.mjs"
// Onboarding's third step reports what happened to the analyst's own files, so the arithmetic
// behind those lines is the one thing on that screen that can lie.
import test from 'node:test'
import assert from 'node:assert/strict'
import { firstQuestions, readingStages } from './reading.ts'

const health = (over = {}) => ({
  rows: 0,
  columns: 0,
  skipped_title_rows: 0,
  dropped_total_rows: 0,
  duplicate_rows: 0,
  duplicates_removed: false,
  date_format: null,
  date_format_ambiguous: false,
  coercions: [],
  null_hotspots: {},
  pii_columns: [],
  preserved_id_columns: [],
  warnings: [],
  ...over,
})

const table = (name, over = {}) => ({
  name,
  source_file: `${name}.csv`,
  sheet: null,
  row_count: 10,
  columns: [],
  health: health(),
  is_view: false,
  ...over,
})

const CATALOG = {
  session_id: 's',
  version: 1,
  fingerprint: 'f',
  tables: [
    table('employees', {
      row_count: 500,
      columns: [
        { name: 'full_name', label: 'Full name' },
        { name: 'work_email', label: 'Work email' },
      ],
      health: health({ pii_columns: ['full_name', 'work_email'] }),
    }),
    table('salary_register', {
      row_count: 500,
      health: health({ skipped_title_rows: 3, dropped_total_rows: 1, duplicate_rows: 6, duplicates_removed: true, coercions: [{}, {}] }),
    }),
    table('attendance_q1', { row_count: 1200 }),
    table('attendance_q2', { row_count: 1200 }),
    // A combined view is not a file anyone dropped in, so it must not be counted as one.
    table('attendance_all', { row_count: 2400, is_view: true }),
  ],
  relationships: [
    { status: 'active' },
    { status: 'active' },
    { status: 'rejected' },
  ],
  unions: [{ view_name: 'attendance_all', tables: ['attendance_q1', 'attendance_q2'], status: 'active' }],
  glossary: [],
  suggested_questions: ['One?', 'Two?', 'Three?', 'Four?'],
}

const byId = (catalog) => Object.fromEntries(readingStages(catalog).map((stage) => [stage.id, stage]))

test('the five stages are always all there, in order', () => {
  // A sequence that changes length with every upload makes the progress ring look broken.
  assert.deepEqual(
    readingStages(CATALOG).map((s) => s.id),
    ['read', 'clean', 'links', 'combined', 'hidden'],
  )
  for (const stage of readingStages(CATALOG)) {
    assert.ok(stage.label.length > 0 && stage.detail.length > 0, `${stage.id}: never an empty line`)
  }
})

test('the counts are the catalog’s own, and a combined view is not counted as a file', () => {
  const stages = byId(CATALOG)
  // Four files, not five: attendance_all is a view built from two of them.
  assert.match(stages.read.detail, /^4 files, 3,400 rows$/)
  assert.equal(stages.clean.detail, '3 title rows skipped, 1 total row dropped, 6 repeated rows removed and 2 columns of ₹ amounts and dates read properly')
  assert.match(stages.links.detail, /^2 links/)
  assert.match(stages.combined.detail, /^2 files stacked into 1 view/)
  assert.equal(stages.hidden.detail, '2 columns kept back: Full name and Work email')
})

test('nothing to report is said, not skipped', () => {
  const plain = { ...CATALOG, tables: [table('one')], relationships: [], unions: [] }
  const stages = byId(plain)
  assert.equal(stages.read.detail, '1 file, 10 rows')
  assert.equal(stages.clean.detail, 'Nothing needed fixing')
  assert.match(stages.links.detail, /each file answers on its own/)
  assert.match(stages.combined.detail, /None of your files/)
  assert.match(stages.hidden.detail, /No personal-data columns/)
})

test('duplicates that were found but not removed are not claimed as removed', () => {
  const found = {
    ...CATALOG,
    tables: [table('one', { health: health({ duplicate_rows: 9, duplicates_removed: false }) })],
  }
  assert.equal(byId(found).clean.detail, 'Nothing needed fixing')
})

test('a column hidden in two files is one hidden column, not two', () => {
  const twice = {
    ...CATALOG,
    tables: ['a', 'b'].map((name) =>
      table(name, { columns: [{ name: 'email', label: 'Work email' }], health: health({ pii_columns: ['email'] }) }),
    ),
    relationships: [],
    unions: [],
  }
  assert.equal(byId(twice).hidden.detail, '1 column kept back: Work email')
})

test('the ready card offers three questions at most', () => {
  assert.deepEqual(firstQuestions(CATALOG), ['One?', 'Two?', 'Three?'])
  assert.deepEqual(firstQuestions({ ...CATALOG, suggested_questions: ['Only?'] }), ['Only?'])
})
