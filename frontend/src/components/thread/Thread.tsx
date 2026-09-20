// Seam between the app shell (frontend-shell agent) and the conversation (frontend-thread agent).
// The shell renders <Thread> once the catalog has tables. Thread owns its own message state.
import type { Catalog } from '../../types'

export interface ThreadProps {
  sessionId: string
  catalog: Catalog
  /** Called when the API reports the session expired (ApiError 404) so the shell can reset. */
  onSessionExpired: () => void
}

export default function Thread({ catalog }: ThreadProps) {
  return <div className="p-6 text-ink-soft">Thread placeholder: {catalog.tables.length} tables loaded.</div>
}
