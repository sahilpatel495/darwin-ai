// Everything the four tabs of a project share (§6), in one component so none of them has to
// repeat it: the record, the files, the Data drawer, and the single answer to "the files are no
// longer loaded".
//
// The server holds the files in memory for two hours. The record — the glossary they edited, the
// links they removed, every turn — is the analyst's and lives in this browser. So an expired
// session costs them a re-attach and nothing else, and this component's real job is making that
// true for Ask, Overview, Analyses and Saved at once: one banner, one way back, whichever tab
// they happen to be standing on.

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, ensureSession, getCatalog, loadSample, resetSession, saveGlossary, setLinkStatus, uploadFiles } from '../../api'
import { fileNamesFrom, useProject, withTipSeen } from '../../lib/projects'
import type { ProjectRecord } from '../../lib/projects'
import type { Route } from '../../lib/route'
import { suggestionsFor } from '../../lib/suggestions'
import type { Catalog, User } from '../../types'
import AnalysesPage from '../analyses/AnalysesPage'
import Board from '../board/Board'
import { TIPS } from '../education/tips'
import type { TipId } from '../education/tips'
import OverviewPage from '../overview/OverviewPage'
import Sidebar from '../sidebar/Sidebar'
import { Banner, Dialog, Drawer, Tip } from '../ui'
import DropZone from '../upload/DropZone'
import UploadProgress from '../upload/UploadProgress'
import type { Busy } from '../upload/UploadProgress'
import { checkFiles, nothingAdded } from '../upload/files'
import MissingProject from './MissingProject'
import type { PageProps } from './page'
import { NOTHING_READ, problemFrom } from './problem'
import type { Problem } from './problem'
import Reattach from './Reattach'
import Workspace from './Workspace'

export interface ProjectShellProps {
  route: Route
  projectId: string
  user: User | null
  /** The record of a project created moments ago, for the browser that could not store it. */
  initialProject: ProjectRecord | null
  /** The catalog from the upload that just created this project, so it is not fetched twice. */
  initialCatalog: Catalog | null
  /** A question sent here from another tab, or from the command palette. Asked once. */
  pendingQuestion: string | null
  onQuestionTaken: () => void
  onAsk: (question: string) => void
  /** An answer arrived: the allowance has moved. */
  onAnswered: () => void
  dataOpen: boolean
  onDataOpenChange: (open: boolean) => void
}

/** One line about the files, for the drawer's header. The receipts are inside. */
function filesLine(project: ProjectRecord): string {
  const count = project.fileNames.length
  if (count === 0) return 'No files loaded'
  return count === 1 ? '1 file' : `${count} files`
}

export default function ProjectShell({
  route,
  projectId,
  user,
  initialProject,
  initialCatalog,
  pendingQuestion,
  onQuestionTaken,
  onAsk,
  onAnswered,
  dataOpen,
  onDataOpenChange,
}: ProjectShellProps) {
  const [project, update] = useProject(projectId, initialProject)
  const [catalog, setCatalog] = useState<Catalog | null>(initialCatalog)
  const [loading, setLoading] = useState(initialCatalog === null)
  const [busy, setBusy] = useState<Busy | null>(null)
  const [problem, setProblem] = useState<Problem | null>(null)
  const [adding, setAdding] = useState(false)

  // Opening a project is what "last opened" means, and the home list is ordered by it.
  useEffect(() => {
    update({ lastOpenedAt: new Date().toISOString() })
  }, [update])

  // One load per mount; App gives this component a key per project, so coming back re-runs it.
  //
  // The dependency is the session id and not the record: "last opened" above writes to the record
  // a tick after mount, and an effect that depended on the record would tear this one down
  // mid-flight — cancelling the very fetch it had just started, leaving the screen on "Loading".
  const loaded = useRef(initialCatalog !== null)
  const savedSessionId = project?.sessionId ?? null
  useEffect(() => {
    if (loaded.current) return
    loaded.current = true
    const sessionId = savedSessionId
    if (!sessionId) {
      setLoading(false) // nothing to ask the server: the re-attach flow takes it from here
      return
    }
    let live = true
    getCatalog(sessionId)
      .then((next) => {
        if (!live) return
        if (next?.tables?.length) setCatalog(next)
        else update({ sessionId: null }) // a session with nothing in it is the same as no session
        setLoading(false)
      })
      .catch((error: unknown) => {
        if (!live) return
        // Files live in server memory and are dropped after two hours or a restart (§6).
        if (error instanceof ApiError && error.status === 404) update({ sessionId: null })
        else setProblem(problemFrom(error))
        setLoading(false)
      })
    return () => {
      live = false
      // The guard has to be released with the fetch it was guarding. StrictMode runs this effect,
      // tears it down and runs it again: without this line the first fetch is abandoned, the
      // second never starts, and opening a saved project sits on "Loading your files…" for ever.
      loaded.current = false
    }
  }, [savedSessionId, update])

  const onSessionExpired = useCallback(() => {
    setCatalog(null)
    update({ sessionId: null })
  }, [update])

  if (!project) return <MissingProject />

  const sessionId = catalog ? project.sessionId : null
  const detached = !loading && !catalog

  /** The glossary the analyst edited and the links they removed are theirs, not the session's:
   *  the answers already in the thread were computed with them, so new answers must match.
   *  (A const rather than a declaration, so TypeScript keeps knowing `project` is not null here.) */
  const reapply = async (id: string, fresh: Catalog): Promise<Catalog> => {
    let next = fresh
    try {
      for (const linkId of project.removedLinkIds) {
        if (next.relationships.some((link) => link.id === linkId)) next = await setLinkStatus(id, linkId, 'rejected')
      }
      if (project.glossary) next = await saveGlossary(id, project.glossary)
    } catch {
      // A link or a metric that no longer exists must not cost the analyst their files.
    }
    return next
  }

  /** Files for a project that has none loaded: a new session, then everything they decided again. */
  async function attach(load: (sessionId: string) => Promise<Catalog>) {
    setProblem(null)
    try {
      // ponytail: this tab holds one live session at a time (api.ts keeps a single id), so
      // attaching files starts a fresh one. Another project's files would be dropped with it.
      resetSession()
      const id = await ensureSession()
      const fresh = await load(id)
      if (!fresh?.tables?.length) return setProblem(NOTHING_READ)
      const next = await reapply(id, fresh)
      setCatalog(next)
      update({ sessionId: id, fileNames: fileNamesFrom(next) })
      setAdding(false)
    } catch (error) {
      setProblem(problemFrom(error))
    } finally {
      setBusy(null)
    }
  }

  /** More files for a project that is already loaded. */
  async function addTo(id: string, upload: (sessionId: string) => Promise<Catalog>) {
    setProblem(null)
    try {
      const next = await upload(id)
      // The server skips a file it already holds and answers with the catalog unchanged; without
      // this, adding the same file twice ends in silence.
      if (nothingAdded(catalog, next)) {
        return setProblem({ message: 'Those files are already loaded, so nothing was added.', nextStep: '', tone: 'warn' })
      }
      setCatalog(next)
      update({ fileNames: fileNamesFrom(next) })
      setAdding(false)
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) onSessionExpired()
      else setProblem(problemFrom(error))
    } finally {
      setBusy(null)
    }
  }

  function onFiles(picked: File[]) {
    const { accepted, problems } = checkFiles(picked)
    if (problems.length) setProblem({ message: problems.join('\n'), nextStep: '', tone: 'warn' })
    if (!accepted.length) return
    setBusy({ kind: 'upload', files: accepted.length, fraction: 0 })
    const upload = (id: string) => uploadFiles(id, accepted, (fraction) => setBusy({ kind: 'upload', files: accepted.length, fraction }))
    void (sessionId ? addTo(sessionId, upload) : attach(upload))
  }

  function onSample() {
    setBusy({ kind: 'sample' })
    void attach(loadSample)
  }

  const banner = problem && (
    <Banner tone={problem.tone} nextStep={problem.nextStep} onDismiss={() => setProblem(null)}>
      {problem.message}
    </Banner>
  )

  const pageProps: PageProps = {
    sessionId,
    project,
    user,
    onAsk,
    onProjectChange: (next) => update(next),
    onOpenData: () => onDataOpenChange(true),
  }

  // The band above the tabs: at most a problem, the way back to having files, and one hint.
  const showBanner = problem !== null && !adding

  /**
   * Two of the three hints (§7) live in this band, under the top bar they point at: `data-button`
   * at the right-hand Data button, `overview-tab` at the Overview tab. The third is under the first
   * answer, which belongs to the thread.
   *
   * One at a time, in the order an analyst meets them: two hints stacked over the same screen is
   * the coach-mark tour again, wearing a different coat. `overview-tab` waits for the first answer,
   * because until then there is nothing for an overview to be an alternative to.
   */
  const unseen = (id: TipId) => !project.tipsSeen.includes(id)
  const bandTip: TipId | null =
    detached || loading ? null : unseen('data-button') ? 'data-button' : project.turns.length > 0 && unseen('overview-tab') ? 'overview-tab' : null
  const dismissTip = (id: string) => update(withTipSeen(project, id))

  let page: React.ReactNode
  if (route.name === 'overview') page = <OverviewPage {...pageProps} />
  else if (route.name === 'analyses') page = <AnalysesPage {...pageProps} />
  else if (route.name === 'board') page = <Board {...pageProps} />
  else
    page = (
      <Workspace
        {...pageProps}
        catalog={catalog}
        loading={loading}
        suggestions={suggestionsFor(catalog?.suggested_questions ?? [], user?.role ?? null)}
        pendingQuestion={pendingQuestion}
        onQuestionTaken={onQuestionTaken}
        onSessionExpired={onSessionExpired}
        onAnswered={onAnswered}
        firstAnswerTip={
          unseen('how-i-got-this') && (
            <Tip id="how-i-got-this" seen={project.tipsSeen} onDismiss={dismissTip}>
              {TIPS['how-i-got-this'].text}
            </Tip>
          )
        }
      />
    )

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* §6: one banner for the whole project. Whichever tab you are on, this is where the files
          being gone is said, and the only place it is said. */}
      {(showBanner || detached || bandTip) && (
        <div className="mx-auto w-full max-w-[1120px] shrink-0 space-y-3 px-4 pt-4 sm:px-6 print-hide">
          {showBanner && banner}
          {detached && <Reattach project={project} busy={busy} onFiles={onFiles} onSample={onSample} />}
          {bandTip && (
            <Tip id={bandTip} seen={project.tipsSeen} onDismiss={dismissTip}>
              {TIPS[bandTip].text}
            </Tip>
          )}
        </div>
      )}

      {page}

      {/* The Data drawer (§6): what used to be the permanent left panel, opened by the Data button
          in the top bar — from any of the four tabs, because it lives out here and not in one of
          them. */}
      <Drawer open={dataOpen} onClose={() => onDataOpenChange(false)} title="Your data" description={filesLine(project)}>
        <Sidebar
          sessionId={sessionId}
          catalog={catalog}
          readOnly={detached}
          fileNames={project.fileNames}
          onCatalogChange={setCatalog}
          onGlossaryEdited={(glossary) => update({ glossary })}
          onLinkStatusChanged={(linkId, status) =>
            update({
              removedLinkIds:
                status === 'rejected' ? [...new Set([...project.removedLinkIds, linkId])] : project.removedLinkIds.filter((id) => id !== linkId),
            })
          }
          onAddFiles={() => setAdding(true)}
        />
      </Drawer>

      {/* "Add more files" lives in the Files tab; the picker opens here, where it cannot be missed
          and where Esc puts the analyst back on the button they pressed. */}
      <Dialog open={adding && !detached} onClose={() => setAdding(false)} title="Add files to this project" size="sm">
        <p className="text-body-md text-slate">They join the files already loaded, and DarwinLens looks for links between them the same way.</p>
        <div className="mt-4">{busy ? <UploadProgress busy={busy} /> : <DropZone onFiles={onFiles} />}</div>
        {banner && <div className="mt-3">{banner}</div>}
      </Dialog>
    </div>
  )
}
