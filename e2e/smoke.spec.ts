// The two journeys that must never break: the 30-second path to a checkable answer, and the
// half of the product that answers without a model at all.
//
//   cd e2e && pnpm install && pnpm exec playwright install chromium
//   BASE_URL=http://localhost:8031 pnpm test     # a backend of your own
//   BASE_URL=https://<deployed-host> pnpm test   # a deployment
//
// The first test needs a model configured, so neither is part of `pytest` or CI. The second one
// costs no tokens: Overview and Analyses are computed by the database from templates.
// Selectors are the words and roles a person (or a screen reader) meets, never CSS classes.
//
// Written against the v3 interface. What changed from v2, and why the old selectors are gone:
// there is no first-run tour to skip (three one-line hints replaced it), no briefing screen
// between the sample and the workspace ("Try the live demo" lands straight in it), and the tile
// menu became a row of icon buttons. Everything below is what a person actually reads on screen.
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

/**
 * The evaluator's path: land, press one button, be in a workspace with the sample company loaded.
 * A guest account is made on the way, so there is nothing to sign up for.
 *
 * The composer is the proof we arrived: it is the one control that only exists inside a project.
 */
async function openSample(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Try the live demo' }).first().click()
  await expect(page.getByLabel('Your question')).toBeVisible({ timeout: 60_000 })
}

test('sample data, a suggested question, the chart, then the query behind it', async ({ page }) => {
  await openSample(page)

  // The four suggestion cards under the composer. Pressing one asks it there and then.
  await page.getByRole('button', { name: /\?$/ }).first().click()

  // "Salary" matches three columns in the sample, so the first question may come back as a
  // question of its own. Answer it the way a person would, then wait for the answer itself.
  const chartSwitch = page.getByRole('tablist', { name: 'Show the result as' })
  const clarify = page.getByText(/could mean more than one column/)
  await expect(chartSwitch.or(clarify).first()).toBeVisible({ timeout: 150_000 })
  if (await clarify.isVisible()) {
    // Every option reads "<meaning> — <column> in <file>"; the "?" beside the question does not.
    await page.getByRole('button', { name: / in / }).first().click()
    await expect(chartSwitch.first()).toBeVisible({ timeout: 150_000 })
  }

  // The working: every answer opens to the query that produced it.
  await page.getByRole('button', { name: 'How I got this' }).first().click()
  await page.getByText('Show the query that produced this answer').first().click()
  await expect(page.locator('pre').filter({ hasText: /select/i }).first()).toBeVisible()
})

test('the half with no AI: the overview computes itself, and an analysis runs on demand', async ({ page }) => {
  await openSample(page)

  await page.getByRole('banner').getByRole('link', { name: 'Overview' }).click()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await expect(page.getByText('No AI involved')).toBeVisible()

  // Every tile shows its own working: the rows, and the query that produced them. The actions are
  // icon buttons on the tile now, named for what they do rather than hidden behind a menu.
  await page.getByRole('button', { name: 'Table and SQL' }).first().click({ timeout: 60_000 })
  await expect(page.getByRole('dialog').locator('pre').filter({ hasText: /select/i }).first()).toBeVisible()
  await page.keyboard.press('Escape')

  // Analyses: the analyst fills in a sentence, and the database does the rest.
  await page.getByRole('banner').getByRole('link', { name: 'Analyses' }).click()
  await page.getByRole('button', { name: /^Break down/ }).click()
  await page.getByLabel('What to measure').selectOption({ label: 'Gross' })
  await page.getByLabel('Split by').selectOption({ label: 'Department' })
  await page.getByRole('button', { name: 'Run', exact: true }).click()
  // The server title-cases the analysis from the file's own headers: "Total Gross by Department".
  await expect(page.getByText(/gross by department/i).first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('button', { name: 'Save to the board' }).first()).toBeVisible()
})
