// A project id in the address bar that this browser has never heard of: a link somebody shared, a
// project deleted in another tab, or somebody else's work under a different sign-in. Say which of
// those it is, and offer the way on.

import { go, PROJECTS } from '../../lib/route'
import { Button, EmptyState } from '../ui'

export default function MissingProject() {
  return (
    <main className="mx-auto w-full max-w-[820px] px-4 py-12 sm:px-6 sm:py-16">
      <EmptyState
        glyph="table"
        title="That project is not in this browser"
        action={
          <Button variant="primary" onClick={() => go(PROJECTS)}>
            Go to your projects
          </Button>
        }
      >
        Projects are saved in the browser that made them, under the account that made them, so a link to one does not travel. Open it where you made it,
        or start a new one.
      </EmptyState>
    </main>
  )
}
