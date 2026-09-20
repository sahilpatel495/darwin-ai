// A project id in the address bar that this browser has never heard of: a link someone shared, or
// a project deleted in another tab. Say which of those it is, and offer the way on.

import { HOME } from '../../lib/route'
import { EmptyState } from '../ui'
import Header from './Header'

export default function MissingProject() {
  return (
    <div className="flex h-full flex-col">
      <Header />
      <main className="mx-auto w-full max-w-2xl px-4 py-12 sm:px-6">
        <EmptyState
          title="That project is not in this browser"
          action={
            <a href={HOME} className="type-body">
              Your projects
            </a>
          }
        >
          Projects are saved in the browser that made them, so a link to one does not travel. Open it where you made it, or start a new one.
        </EmptyState>
      </main>
    </div>
  )
}
