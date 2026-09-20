// Everything Verity found in the uploaded files: the files with their receipts, how the files
// connect, and the metric definitions. A column from 768px up; below that the same panel collapses
// behind one line, because on a phone the briefing and the question box come first.
//
// The sidebar owns its two writes (keep/remove a link, save a definition). It reports the new
// catalog upwards so the workspace can store it, and reports the edit itself so the project record
// can replay it after the files are re-attached (§6.6).

import { useId, useState } from 'react'
import { ApiError, saveGlossary, setLinkStatus } from '../../api'
import type { Catalog, Metric } from '../../types'
import { Banner, RuledRow, Tabs, cx } from '../ui'
import type { TabItem } from '../ui'
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
}

const TITLE = "What we found in your files"

interface Problem {
  message: string
  nextStep: string
}

export default function Sidebar({ sessionId, catalog, readOnly, fileNames, onCatalogChange, onGlossaryEdited, onLinkStatusChanged, onAddFiles }: SidebarProps) {
  const [tab, setTab] = useState('files')
  const [open, setOpen] = useState(false) // below 768px only; from 768px up the panel is always shown
  const [problem, setProblem] = useState<Problem | null>(null)
  const panelId = useId()

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

  const tabs: TabItem[] = catalog
    ? [
        // The first-run tour points at this tab (§10).
        { id: 'files', label: `Files (${catalog.tables.filter((table) => !table.is_view).length})`, buttonProps: { 'data-tour': 'files' } },
        { id: 'links', label: `Links (${catalog.relationships.length + catalog.unions.length})` },
        { id: 'glossary', label: `Glossary (${catalog.glossary.length})` },
      ]
    : []

  return (
    <aside
      aria-label={TITLE}
      // `relative` matters: screen-reader-only text is absolutely positioned, and against an
      // unpositioned scroller it is laid out on the page instead, which then scrolls as a whole.
      className="relative w-full shrink-0 border-rule bg-paper print-hide max-md:border-b md:w-80 md:overflow-y-auto md:border-r"
    >
      {/* One line on a phone, a heading on a wide screen: the same words either way. */}
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((was) => !was)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left md:hidden"
      >
        <span className="type-title text-ink">{TITLE}</span>
        <span className="type-small text-ink-soft">{open ? 'Hide' : 'Show'}</span>
      </button>
      <h2 className="px-4 pt-4 type-title text-ink max-md:hidden">{TITLE}</h2>

      <div id={panelId} className={cx('px-4 pb-8', !open && 'max-md:hidden')}>
        {catalog ? (
          <>
            <p className="pb-3 type-small text-ink-soft">{overviewLine(catalog)}</p>
            {problem && (
              <Banner tone="error" nextStep={problem.nextStep} onDismiss={() => setProblem(null)} className="mb-3">
                {problem.message}
              </Banner>
            )}
            <Tabs label="Files, links and definitions" tabs={tabs} active={tab} onChange={setTab}>
              {tab === 'files' && <Files sessionId={sessionId} catalog={catalog} readOnly={readOnly} onAddFiles={onAddFiles} />}
              {tab === 'links' && <Links catalog={catalog} readOnly={readOnly} onSetLink={setLink} />}
              {tab === 'glossary' && <Glossary glossary={catalog.glossary} readOnly={readOnly} onSave={saveMetrics} />}
            </Tabs>
          </>
        ) : (
          <>
            <p className="measure pb-3 type-small text-ink-soft">These are the files this project was built from.</p>
            <ul>
              {fileNames.map((fileName) => (
                <RuledRow as="li" key={fileName}>
                  {/* One child, so nothing here has to fight RuledRow's own alignment or gap. */}
                  <span className="flex w-full items-baseline justify-between gap-3">
                    <span className="min-w-0 truncate type-body text-ink" title={fileName}>
                      {fileName}
                    </span>
                    <span className="shrink-0 type-small text-ink-soft">Not loaded</span>
                  </span>
                </RuledRow>
              ))}
            </ul>
          </>
        )}
      </div>
    </aside>
  )
}
