// The one journey that must never break: a first-time user gets a charted, checkable answer
// from the sample data without typing anything.
//
//   cd e2e && pnpm install && pnpm exec playwright install chromium
//   pnpm test                                   # against http://localhost:8000
//   BASE_URL=https://<deployed-host> pnpm test  # against a deployment
//
// It needs a running app with a model configured, so it is not part of `pytest` or CI.
// Selectors are the words and roles a person (or a screen reader) sees, not CSS classes.
import { expect, test } from '@playwright/test'

test('sample data, first suggested question, chart, then the SQL behind it', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Try with sample HR data' }).click()

  // The empty thread offers the suggested questions right under this heading.
  const intro = page.getByRole('heading', { name: 'Ask a question about your data' }).locator('..')
  await intro.getByRole('button').first().click()

  // An answer with a chart always carries the Chart / Table switch.
  await expect(page.getByRole('group', { name: 'Show the result as' })).toBeVisible({ timeout: 150_000 })

  await page.getByText('How I got this', { exact: true }).click()
  await page.getByText('Show the query that produced this answer').click()
  await expect(page.locator('pre').filter({ hasText: /select/i }).first()).toBeVisible()
})
