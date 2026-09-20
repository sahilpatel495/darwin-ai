// The four lines onboarding ends on and the Data drawer keeps: they are the product's claim about
// the analyst's files, so they are counted from the catalog and checked here rather than read off
// a screenshot. Same machinery as components/answer/render.test.mjs: Vite's SSR loader reads the
// .tsx and react-dom/server draws it. Run: cd frontend && node --test "src/**/*.test.mjs"
import test, { after, before } from 'node:test'
import assert from 'node:assert/strict'
import { tmpdir } from 'node:os'
import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import catalog from '../../fixtures/catalog.json' with { type: 'json' }

let vite
let ReadyState

before(async () => {
  vite = await createServer({
    root: new URL('../../..', import.meta.url).pathname,
    configFile: false, // no Tailwind or proxy needed to draw markup
    cacheDir: `${tmpdir()}/darwinlens-ready-test`, // never touch the dev server's cache
    appType: 'custom',
    logLevel: 'error',
    server: { middlewareMode: true, ws: false, hmr: false, watch: null },
    optimizeDeps: { noDiscovery: true },
  })
  ReadyState = (await vite.ssrLoadModule('/src/components/workspace/ReadyState.tsx')).default
})
after(() => vite.close())

const words = (props = {}) =>
  renderToStaticMarkup(h(ReadyState, { catalog, ...props }))
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;|&quot;/g, "'")
    .replace(/\s+/g, ' ')
    .trim()

test('every line carries its real count, and the combined view is not counted as an uploaded file', () => {
  const text = words()
  // Four uploaded files: attendance_all is a combined view, which the next line is about.
  assert.match(text, /Read and cleaned 4 files/)
  assert.match(text, /Found 2 links between your files/)
  assert.match(text, /Combined 2 files that have the same columns/)
  assert.match(text, /Hid 2 personal-data columns from the AI/)
  assert.match(text, /No AI was involved in any of it/)
})

test('an opened line names the files, by the header the analyst wrote', () => {
  const text = words()
  assert.match(text, /employees\.csv 8 rows/, 'each file with its row count')
  assert.match(text, /employees\.csv and Salary_Register_2025\.xlsx are linked on/, 'the link as a sentence')
  assert.match(text, /employees\.csv name, email/, 'the hidden columns, under the file they are in')
})

test('a removed link and a rejected view are not claimed as found', () => {
  const text = words({
    catalog: {
      ...catalog,
      relationships: catalog.relationships.map((link) => ({ ...link, status: 'rejected' })),
      unions: catalog.unions.map((union) => ({ ...union, status: 'rejected' })),
    },
  })
  assert.match(text, /Found no links between your files/)
  assert.match(text, /No files needed combining/)
})

test('nothing found is still said out loud, so a blank line never reads as a check that was skipped', () => {
  const clean = {
    ...catalog,
    relationships: [],
    unions: [],
    tables: catalog.tables.map((table) => ({ ...table, health: { ...table.health, pii_columns: [] } })),
  }
  assert.match(words({ catalog: clean }), /Found no personal data to hide/)
})

test('the caller can write its own title, and the default is the one onboarding ends on', () => {
  assert.match(words(), /Here’s what I found in your files/)
  assert.doesNotMatch(words({ heading: null }), /Here’s what I found/)
})
