// Everything Verity found in the uploaded files: the files with their receipts, how the files
// connect, and the metric definitions. A white card in a column from 768px up; below that the same
// card collapses behind its own header, because on a phone the briefing and the question box come
// first.
//
// The sidebar owns its two writes (keep/remove a link, save a definition). It reports the new
// catalog upwards so the workspace can store it, and reports the edit itself so the project record
// can replay it after the files are re-attached (§6.6).

import { useId, useState } from 'react'
import { ApiError, saveGlossary, setLinkStatus } from '../../api'
import type { Catalog, Metric } from '../../types'
import { Banner, Button, Card, ListRow, Tabs, cx } from '../ui'
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

const TITLE = 'Your data'

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
      className="relative w-full shrink-0 bg-wash px-3 pt-3 pb-1 print-hide md:w-[23rem] md:overflow-y-auto md:px-4 md:py-5"
    >
      <Card flush>
        <div className="flex items-start gap-3 px-4 pt-4 pb-3">
          <div className="min-w-0 flex-1">
            <h2 className="type-section text-ink">{TITLE}</h2>
            <p className="mt-0.5 type-small text-ink-2">
              {catalog ? overviewLine(catalog) : 'These are the files this project was built from.'}
            </p>
          </div>
          {/* One tap on a phone, always open on a wide screen: the same words either way. */}
          <Button
            variant="ghost"
            size="sm"
            aria-expanded={open}
            aria-controls={panelId}
            aria-label={open ? `Hide ${TITLE}` : `Show ${TITLE}`}
            onClick={() => setOpen((was) => !was)}
            className="-mt-0.5 md:hidden"
          >
            {open ? 'Hide' : 'Show'}
          </Button>
        </div>

        <div id={panelId} className={cx('pb-1', !open && 'max-md:hidden')}>
          {problem && (
            <Banner tone="error" nextStep={problem.nextStep} onDismiss={() => setProblem(null)} className="mx-4 mb-3">
              {problem.message}
            </Banner>
          )}
          {catalog ? (
            <Tabs label="Files, links and definitions" tabs={tabs} active={tab} onChange={setTab}>
              <div className="px-4 pt-3 pb-4">
                {tab === 'files' && <Files sessionId={sessionId} catalog={catalog} readOnly={readOnly} onAddFiles={onAddFiles} />}
                {tab === 'links' && <Links catalog={catalog} readOnly={readOnly} onSetLink={setLink} />}
                {tab === 'glossary' && <Glossary glossary={catalog.glossary} readOnly={readOnly} onSave={saveMetrics} />}
              </div>
            </Tabs>
          ) : (
            <ul className="px-2 pb-3">
              {fileNames.map((fileName) => (
                <ListRow as="li" key={fileName} className="items-baseline justify-between">
                  <span className="min-w-0 truncate type-body text-ink" title={fileName}>
                    {fileName}
                  </span>
                  <span className="shrink-0 type-small text-ink-2">Not loaded</span>
                </ListRow>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </aside>
  )
}
