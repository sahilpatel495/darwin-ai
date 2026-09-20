import { defineConfig } from '@playwright/test'

// One browser, one flow. The timeout is generous on purpose: the first question on a cold
// free-tier host pays for a container wake-up and a rate-limited model call.
export default defineConfig({
  testDir: '.',
  timeout: 180_000,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:8000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
})
