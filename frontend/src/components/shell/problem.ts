// One shape for everything that goes wrong on a screen, and the one place an API failure becomes
// two plain sentences: what happened, then what to do (§8). Nothing technical ever reaches the
// analyst — a status code tells them nothing they can act on.

import { ApiError } from '../../api'

export interface Problem {
  /** What happened. Line breaks are kept, so several skipped files read as one line each. */
  message: string
  /** What to do next. Empty when the message already says. */
  nextStep: string
  /** `warn`: the app carried on. `error`: the action failed. */
  tone: 'warn' | 'error'
}

export function problemFrom(error: unknown): Problem {
  if (error instanceof ApiError) return { message: error.message, nextStep: error.nextStep, tone: 'error' }
  console.error(error) // a bug in this app, not a reply from the server: keep the detail for the engineer
  return { message: 'Something went wrong in the app.', nextStep: 'Reload the page and try again.', tone: 'error' }
}

/** A reply that is not a catalog, or a catalog with nothing readable in it. */
export const NOTHING_READ: Problem = {
  message: 'No table could be read from those files.',
  nextStep: 'Check that they have rows under a header row, then add them again.',
  tone: 'error',
}
