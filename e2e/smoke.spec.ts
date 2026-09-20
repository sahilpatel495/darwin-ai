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
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

/** The first-run tour opens over a fresh workspace. A person would read it or skip it; skip it. */
async function skipTour(page: Page) {
  const skip = page.getByRole('button', { name: 'Skip' })
  if (await skip.isVisible({ timeout: 15_000 }).catch(() => false)) await skip.click()
}

/** Land, load the sample data, arrive at the briefing. */
async function openSample(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Try with sample HR data' }).click()
  await expect(page.getByRole('heading', { name: /what I found in your files/ })).toBeVisible({ timeout: 60_000 })
  await skipTour(page)
}

test('sample data, a suggested question, the chart, then the query behind it', async ({ page }) => {
  await openSample(page)

  // The briefing's own "Questions to start with": the first one, as a first-time user would.
  const briefing = page.getByRole('region', { name: /what I found in your files/ })
  await briefing.getByRole('button', { name: /\?$/ }).first().click()

  // "Salary" matches three columns in the sample, so the first question may come back as a
  // question of its own. Answer it the way a person would, then wait for the answer itself.
  const chartSwitch = page.getByRole('radiogroup', { name: 'Show the result as' })
  const clarify = page.getByText(/could mean more than one column/)
  await expect(chartSwitch.or(clarify).first()).toBeVisible({ timeout: 150_000 })
  if (await clarify.isVisible()) {
    // Every option reads "<meaning> — <column> in <file>"; the "?" beside the question does not.
    await page.getByRole('button', { name: / in / }).first().click()
    await expect(chartSwitch).toBeVisible({ timeout: 150_000 })
  }

  // The working: every answer opens to the query that produced it.
  await page.getByRole('button', { name: 'How I got this' }).first().click()
  await page.getByText('Show the query that produced this answer').click()
  await expect(page.locator('pre').filter({ hasText: /select/i }).first()).toBeVisible()
})

test('the half with no AI: the overview computes itself, and an analysis runs on demand', async ({ page }) => {
  await openSample(page)

  await page.getByRole('link', { name: 'Overview' }).click()
  await expect(page.getByText('Computed from your files. No AI involved.')).toBeVisible()
  const tiles = page.getByRole('article')
  await expect(tiles.first()).toBeVisible({ timeout: 60_000 })

  // Every tile shows its own working: the rows, and the query that produced them.
  await page.getByRole('button', { name: /^Actions for / }).first().click()
  await page.getByRole('menuitem', { name: 'View table and SQL' }).click()
  await expect(page.getByRole('dialog').locator('pre').filter({ hasText: /select/i })).toBeVisible()
  await page.keyboard.press('Escape')

  // Analyses: the analyst picks the columns, the database does the rest.
  await page.getByRole('link', { name: 'Analyses' }).click()
  await page.getByRole('button', { name: /^Break down/ }).click()
  await page.getByLabel('What to measure').selectOption({ label: 'Gross' })
  await page.getByLabel('Split by').selectOption({ label: 'Department' })
  await page.getByRole('button', { name: 'Run this analysis' }).click()
  await expect(page.getByText(/Gross by department/i).first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('button', { name: 'Save to board' })).toBeVisible()
})
