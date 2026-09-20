// What every screen inside a project is handed by the shell. One shape, so Ask, Overview,
// Analyses and Saved are interchangeable to the router and none of them has to fetch the catalog,
// notice an expired session or draw its own error for it (§6).

import type { ProjectRecord } from '../../lib/projects'
import type { User } from '../../types'

export interface PageProps {
  /** null = the files are no longer loaded. The shell is already saying so; the page just stops. */
  sessionId: string | null
  project: ProjectRecord
  /** Who is reading, for a greeting or an allowance. Null on a server without accounts. */
  user: User | null
  /** Sends a question to the Ask page and goes there. */
  onAsk: (question: string) => void
  /** The page changed the record: the shell stores it and hands it back as `project`. */
  onProjectChange: (next: ProjectRecord) => void
  /** Opens the Data drawer — the same drawer the Data button in the top bar opens. */
  onOpenData: () => void
}
