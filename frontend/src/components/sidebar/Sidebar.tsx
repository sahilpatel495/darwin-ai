// The body of the Data drawer (§6): everything DarwinLens found in the uploaded files — the files
// with their receipts, how the files connect, and the metric definitions. The drawer around it
// carries the heading and the close button, so this starts straight in on what is loaded.
//
// It owns its two writes (keep/remove a link, save a definition). It reports the new catalog
// upwards so the workspace can store it, and reports the edit itself so the project record can
// replay it after the files are re-attached (§6.6).

import { useState } from 'react'
import { ApiError, saveGlossary, setLinkStatus } from '../../api'
import type { Catalog, Metric } from '../../types'
import { Banner, ListRow, PillTabs } from '../ui'
import ReadyState from '../workspace/ReadyState'
import Expander from './Expander'
import Files from './Files'
import Glossary from './Glossary'
import Links from './Links'
import { overviewLine } from './wording'

export interface SidebarProps {
  sessionId: string | null
  catalog: Catalog | null
  /** Files are not loaded: everything reads, nothing can be changed. */
  readOnly: boolean
  /** From the project record. Shown as "Not loaded" rows when there is no catalog. */
  fileNames: string[]
  onCatalogChange: (catalog: Catalog) => void
  onGlossaryEdited: (glossary: Metric[]) => void
  onLinkStatusChanged: (linkId: string, status: 'active' | 'rejected') => void
  onAddFiles: () => void
  /** Hints this reader has already dismissed, from the project record's `tipsSeen` (§10). */
  tipsSeen?: readonly string[]
  /** Called with the hint's id when it is dismissed, so the record can remember it for good. */
  onTipSeen?: (id: string) => void
}

interface Problem {
  message: string
  nextStep: string
}

export default function Sidebar({
  sessionId,
  catalog,
  readOnly,
  fileNames,
  onCatalogChange,
  onGlossaryEdited,
  onLinkStatusChanged,
  onAddFiles,
  tipsSeen = [],
  onTipSeen,
}: SidebarProps) {
  const [tab, setTab] = useState('files')
  const [problem, setProblem] = useState<Problem | null>(null)
  // Until the shell hands down the project record's list, a dismissal lasts as long as the drawer
  // is mounted — which is the whole visit to the project, so the hint never nags mid-session.
  const [dismissed, setDismissed] = useState<string[]>([])
  const dismissTip = (id: string) => {
    setDismissed((all) => [...all, id])
    onTipSeen?.(id)
  }

  /** Both writes go through here, so a failure is always reported the same way, in one place. */
  async function call<T>(action: (sessionId: string) => Promise<T>): Promise<T | undefined> {
    if (!sessionId) return undefined
    setProblem(null)
    try {
      return await action(sessionId)
    } catch (error) {
      if (error instanceof ApiError) setProblem({ message: error.message, nextStep: error.nextStep })
      else setProblem({ message: 'Something went wrong in the app.', nextStep: 'Reload the page and try again.' })
      return undefined
    }
  }

  const setLink = async (linkId: string, status: 'active' | 'rejected') => {
    const next = await call((id) => setLinkStatus(id, linkId, status))
    if (!next) return
    onCatalogChange(next)
    onLinkStatusChanged(linkId, status)
  }

  const saveMetrics = async (glossary: Metric[]): Promise<boolean> => {
    const next = await call((id) => saveGlossary(id, glossary))
    if (!next) return false
    onCatalogChange(next)
    onGlossaryEdited(next.glossary)
    return true
  }

  return (
    <div className="print-hide">
      <p className="text-body-md text-ink">{catalog ? overviewLine(catalog) : 'These are the files this project was built from.'}</p>

      {/* The summary onboarding ends on, kept one tap away: what was done to the files, and what
          was never shown to the AI. Folded, because by now the analyst is here to look something
          up rather than to be told the story again. */}
      {catalog && (
        <Expander
          chevronAtEnd
          className="mt-4 rounded-xl border border-hairline-soft"
          summaryClassName="px-4 py-3"
          label={<span className="text-body-sm font-bold text-ink-deep">What I found in your files</span>}
        >
          <div className="px-4 pb-4">
            <ReadyState catalog={catalog} heading={null} />
          </div>
        </Expander>
      )}

      {problem && (
        <Banner tone="error" nextStep={problem.nextStep} onDismiss={() => setProblem(null)} className="mt-4">
          {problem.message}
        </Banner>
      )}

      {catalog ? (
        <PillTabs
          label="Files, links and definitions"
          size="sm"
          className="mt-5"
          active={tab}
          onChange={setTab}
          tabs={[
            { id: 'files', label: `Files (${catalog.tables.filter((table) => !table.is_view).length})` },
            { id: 'links', label: `Links (${catalog.relationships.length + catalog.unions.length})` },
            { id: 'glossary', label: `Glossary (${catalog.glossary.length})` },
          ]}
        >
          <div className="pt-6">
            {tab === 'files' && <Files sessionId={sessionId} catalog={catalog} readOnly={readOnly} onAddFiles={onAddFiles} />}
            {tab === 'links' && (
              <Links catalog={catalog} readOnly={readOnly} onSetLink={setLink} tipsSeen={[...tipsSeen, ...dismissed]} onTipSeen={dismissTip} />
            )}
            {tab === 'glossary' && <Glossary glossary={catalog.glossary} readOnly={readOnly} onSave={saveMetrics} />}
          </div>
        </PillTabs>
      ) : (
        // Nothing is loaded on the server: the names are all the project record kept, and the way
        // back is the re-attach card on the Ask page, not a second one in here.
        <div className="mt-5">
          <ul className="-mx-3">
            {fileNames.map((fileName) => (
              <ListRow as="li" key={fileName} className="items-baseline justify-between px-3 py-3">
                <span className="min-w-0 truncate text-body-md text-ink" title={fileName}>
                  {fileName}
                </span>
                <span className="shrink-0 text-body-sm text-steel">Not loaded</span>
              </ListRow>
            ))}
          </ul>
          <p className="measure mt-4 text-body-sm text-slate">
            {fileNames.length
              ? 'Your answers so far still read. Put the files back on the Ask page to ask new questions.'
              : 'No files have been added to this project yet.'}
          </p>
        </div>
      )}
    </div>
  )
}
