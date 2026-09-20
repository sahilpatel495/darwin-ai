// App shell: owns the session, the catalog and the one place problems are reported.
// Landing until the session has tables, then sidebar + Thread. No router and no state library:
// the only route is the hash `#/trust`, and the only shared state lives in this component.

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, ensureSession, getCatalog, loadSample, resetSession, saveGlossary, setLinkStatus, uploadFiles } from './api'
import Header from './components/shell/Header'
import Notice from './components/shell/Notice'
import type { Problem } from './components/shell/Notice'
import Sidebar from './components/sidebar/Sidebar'
import Thread from './components/thread/Thread'
import Landing from './components/upload/Landing'
import type { Busy } from './components/upload/UploadProgress'
import { checkFiles, nothingAdded } from './components/upload/files'
import TrustReport from './pages/TrustReport'
import type { Catalog, Metric } from './types'

// In mock mode getCatalog always returns the full fixture, which would skip the landing page.
// Starting empty lets a developer walk the real first-run flow: landing, sample data, workspace.
const MOCK = import.meta.env.VITE_MOCK === '1'

function LoadingScreen() {
  // The hosted demo sleeps when idle and takes about a minute to wake. A silent skeleton looks
  // broken long before that, so after a few seconds the wait is explained in words.
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 4000)
    return () => clearTimeout(timer)
  }, [])
  return (
    <div role="status" className="mx-auto w-full max-w-5xl space-y-4 px-4 py-16 sm:px-6">
      <div aria-hidden className="animate-pulse space-y-4">
        <div className="h-10 w-2/3 rounded bg-sunken" />
        <div className="h-10 w-1/2 rounded bg-sunken" />
      </div>
      <p className="text-sm text-ink-soft">
        {slow ? 'Still starting. The server sleeps when nobody is using it and can take about a minute to wake up.' : 'Loading…'}
      </p>
    </div>
  )
}

export default function App() {
  // The ref is the truth for API calls (a state value would be stale inside an async handler
  // right after "New session"); the state copy exists only so <Thread> re-renders with the id.
  const sessionRef = useRef<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<Busy | null>(null)
  const [problem, setProblem] = useState<Problem | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [hash, setHash] = useState(location.hash)
  const onTrustPage = hash === '#/trust'

  const forgetSession = () => {
    resetSession()
    sessionRef.current = null
    setSessionId(null)
    setCatalog(null)
    setDrawerOpen(false)
  }

  /**
   * Every problem is shown through here. It also closes the phone drawer: the banner lives in the
   * page behind the drawer, where it would be neither seen nor read out by a screen reader.
   */
  const showProblem = (next: Problem) => {
    setDrawerOpen(false)
    setProblem(next)
  }

  // Sessions live in server memory, so a redeploy or two idle hours ends them. Any 404 means
  // that: drop the dead id and say so plainly. The next action creates a fresh session.
  // (forgetSession and showProblem only touch refs and state setters, so the copies captured here never go stale.)
  const expireSession = useCallback(() => {
    forgetSession()
    showProblem({ message: 'Your session expired.', nextStep: 'Please upload your files again.', tone: 'warn' })
  }, [])

  const report = (error: unknown) => {
    if (error instanceof ApiError && error.status === 404) return expireSession()
    if (error instanceof ApiError) return showProblem({ message: error.message, nextStep: error.nextStep, tone: 'bad' })
    console.error(error) // a bug in this app, not a server reply: keep the detail for the engineer, not the analyst
    showProblem({ message: 'Something went wrong in the app.', nextStep: 'Reload the page and try again.', tone: 'bad' })
  }

  /**
   * Every API call goes through here, so a failure is always reported the same way. Resolves
   * undefined on failure, and also when the session was cleared or expired while the server was
   * working: that reply is about files the analyst no longer has, and showing it would attach the
   * old files to the new session.
   */
  async function call<T>(action: (sessionId: string) => Promise<T>): Promise<T | undefined> {
    setProblem(null)
    let id = sessionRef.current
    try {
      if (!id) {
        id = await ensureSession()
        sessionRef.current = id
        setSessionId(id)
      }
      const result = await action(id)
      return sessionRef.current === id ? result : undefined
    } catch (error) {
      if (sessionRef.current === id) report(error)
      return undefined
    }
  }

  /** Restores the workspace after a page reload; a brand-new session simply has no tables yet. */
  async function loadState() {
    setLoading(true)
    const restored = await call((id) => (MOCK ? Promise.resolve(null) : getCatalog(id)))
    setCatalog(restored?.tables?.length ? restored : null)
    setLoading(false)
  }

  // The ref guard stops React StrictMode's double-run in development from creating two sessions.
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    void loadState()
  }, [])

  useEffect(() => {
    const onHashChange = () => {
      setHash(location.hash)
      setDrawerOpen(false) // Back/Forward can leave the workspace with the drawer open, and an open drawer makes the header inert
    }
    // A file dropped beside the drop zone would otherwise make the browser open it and leave the app.
    const keepPage = (e: DragEvent) => e.preventDefault()
    // The drawer only exists below 768px. Closing it when the window grows past that keeps the
    // conversation from staying `inert` behind a drawer that is no longer drawn as one.
    const wide = matchMedia('(min-width: 768px)')
    const closeDrawerWhenWide = () => setDrawerOpen(false)
    window.addEventListener('hashchange', onHashChange)
    window.addEventListener('dragover', keepPage)
    window.addEventListener('drop', keepPage)
    wide.addEventListener('change', closeDrawerWhenWide)
    return () => {
      window.removeEventListener('hashchange', onHashChange)
      window.removeEventListener('dragover', keepPage)
      window.removeEventListener('drop', keepPage)
      wide.removeEventListener('change', closeDrawerWhenWide)
    }
  }, [])

  /** One line per file that was not added. Each sentence already says what to do, so there is no separate next step. */
  const showSkipped = (sentences: string[]) => {
    if (sentences.length) showProblem({ message: sentences.join('\n'), nextStep: '', tone: 'warn' })
  }

  const showCatalog = (next: Catalog | undefined, skipped: string[] = []) => {
    if (next === undefined) return // call() already reported why
    // Also true for a reply that is not a catalog at all: say something rather than show nothing.
    if (!next?.tables?.length) {
      return showProblem({ message: 'No table could be read from those files.', nextStep: 'Check that they contain rows under a header row, then add them again.', tone: 'bad' })
    }
    setCatalog(next)
    showSkipped(skipped)
  }

  async function addFiles(picked: File[]) {
    const { accepted, problems } = checkFiles(picked)
    if (accepted.length === 0) return showSkipped(problems)
    setBusy({ kind: 'upload', files: accepted.length, fraction: 0 })
    const next = await call((id) => uploadFiles(id, accepted, (fraction) => setBusy({ kind: 'upload', files: accepted.length, fraction })))
    setBusy(null)
    if (next && nothingAdded(catalog, next)) {
      problems.push(`${accepted.length === 1 ? `${accepted[0].name} is` : 'Those files are'} already loaded, so nothing was added.`)
    }
    showCatalog(next, problems)
  }

  async function addSample() {
    setBusy({ kind: 'sample' })
    const next = await call(loadSample)
    setBusy(null)
    showCatalog(next)
  }

  async function setLink(linkId: string, status: 'active' | 'rejected') {
    showCatalog(await call((id) => setLinkStatus(id, linkId, status)))
  }

  async function saveMetrics(glossary: Metric[]): Promise<boolean> {
    const next = await call((id) => saveGlossary(id, glossary))
    showCatalog(next)
    return next !== undefined
  }

  function newSession() {
    const warning = 'Start a new session? Your uploaded files and answers will be cleared.'
    if (catalog && !window.confirm(warning)) return
    forgetSession()
    location.hash = '#/'
    void loadState()
  }

  const closeDrawer = useCallback(() => setDrawerOpen(false), [])
  // Hand focus back to the button that opened the drawer. Done in an effect because the button
  // sits inside <main inert> until the closed state has rendered, and inert elements refuse focus.
  const drawerOpener = useRef<HTMLButtonElement>(null)
  const drawerWasOpen = useRef(false)
  useEffect(() => {
    if (drawerWasOpen.current && !drawerOpen) drawerOpener.current?.focus()
    drawerWasOpen.current = drawerOpen
  }, [drawerOpen])
  const notice = problem && <Notice problem={problem} onDismiss={() => setProblem(null)} />
  const fileCount = catalog ? catalog.tables.filter((table) => !table.is_view).length : 0

  return (
    <div className="flex h-full flex-col">
      <Header onTrustPage={onTrustPage} onNewSession={newSession} working={busy !== null} behindDrawer={drawerOpen} />

      {onTrustPage && (
        <main className="min-h-0 flex-1 overflow-y-auto">
          <TrustReport />
        </main>
      )}

      {/* Hidden rather than unmounted on the Trust Report page: Thread owns the conversation, and
          unmounting it would throw the analyst's answers away for the sake of reading a report. */}
      <div className={onTrustPage ? 'hidden' : 'flex min-h-0 flex-1'}>
        {catalog && sessionId ? (
          <>
            <Sidebar
              catalog={catalog}
              busy={busy}
              open={drawerOpen}
              onClose={closeDrawer}
              onFiles={addFiles}
              onSetLink={setLink}
              onSaveGlossary={saveMetrics}
            />
            <main inert={drawerOpen} className="flex min-h-0 min-w-0 flex-1 flex-col">
              <button
                ref={drawerOpener}
                type="button"
                onClick={() => setDrawerOpen(true)}
                className="shrink-0 border-b border-line bg-surface px-4 py-2 text-left text-sm font-medium text-accent md:hidden"
              >
                Your files and Data Health receipts ({fileCount})
              </button>
              {notice && <div className="shrink-0 px-4 pt-3">{notice}</div>}
              <div className="min-h-0 flex-1 overflow-y-auto">
                <Thread key={sessionId} sessionId={sessionId} catalog={catalog} onSessionExpired={expireSession} />
              </div>
            </main>
          </>
        ) : (
          <main className="min-h-0 flex-1 overflow-y-auto">
            {notice && <div className="mx-auto w-full max-w-5xl px-4 pt-4 sm:px-6">{notice}</div>}
            {loading ? <LoadingScreen /> : <Landing busy={busy} onFiles={addFiles} onSample={addSample} />}
          </main>
        )}
      </div>
    </div>
  )
}
