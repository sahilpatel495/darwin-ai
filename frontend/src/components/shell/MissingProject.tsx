// A project id in the address bar that this browser has never heard of: a link someone shared, or
// a project deleted in another tab. Say which of those it is, and offer the way on.

import { HOME } from '../../lib/route'
import Header from './Header'

export default function MissingProject() {
  return (
    <div className="flex h-full flex-col">
      <Header />
      <main className="mx-auto w-full max-w-3xl px-4 py-16 sm:px-6">
        <h1 className="type-headline text-ink">That project is not in this browser</h1>
        <p className="mt-3 measure type-body text-ink-soft">
          Projects are saved in the browser that made them, so a link to one does not travel. Open it where you made it, or start a new one.
        </p>
        <p className="mt-5">
          <a href={HOME}>Your projects</a>
        </p>
      </main>
    </div>
  )
}
