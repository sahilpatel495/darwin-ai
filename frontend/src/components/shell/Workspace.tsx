// The workspace (§6.3): one project, its files, and the conversation about them.
//
// The project record is the truth about everything the analyst decided — the glossary they edited,
// the links they removed, every turn. The server only holds the files, for two hours. So a session
// that expires costs them nothing but a re-upload, and this component's other job is making that
// true: loading the catalog, noticing when it is gone, and putting it back (§6.6).

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, ensureSession, getCatalog, loadSample, resetSession, setLinkStatus, saveGlossary, uploadFiles } from '../../api'
import { fileNamesFrom, useProject } from '../../lib/projects'
import type { ProjectRecord, Turn } from '../../lib/projects'
import type { Catalog } from '../../types'
import Tour from '../education/Tour'
import Sidebar from '../sidebar/Sidebar'
import Thread from '../thread/Thread'
import { Banner, Dialog, Skeleton } from '../ui'
import { checkFiles, nothingAdded } from '../upload/files'
import type { Busy } from '../upload/UploadProgress'
import DropZone from '../upload/DropZone'
import UploadProgress from '../upload/UploadProgress'
import Briefing from '../workspace/Briefing'
import Header from './Header'
import MissingProject from './MissingProject'
import { NOTHING_READ, problemFrom } from './problem'
import type { Problem } from './problem'
import Reattach from './Reattach'

interface WorkspaceProps {
  projectId: string
  /** The record of a project created moments ago, for the browser that could not store it. */
  initialProject?: ProjectRecord | null
  /** The catalog from the upload that just created this project, so it is not fetched twice. */
  initialCatalog: Catalog | null
}

/**
 * The briefing's "Questions to start with" ask a question, but §10 hands the thread only a node,
 * with no callback to call. The composer is the one control both sides already share, so the
 * question goes in the way a person would type it and the form submits itself.
 * ponytail: a DOM handshake. Replace it the day Thread exposes an ask callback of its own.
 */
function askInComposer(question: string) {
  const box = document.querySelector<HTMLTextAreaElement>('#verity-question, [data-tour="composer"] textarea')
  if (!box) return
  const setValue = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set
  setValue?.call(box, question) // React listens for the input event, not for an assignment to .value
  box.dispatchEvent(new Event('input', { bubbles: true }))
  // A tick for React to have taken the value before the form reads it back.
  setTimeout(() => {
    if (box.form) box.form.requestSubmit()
    else box.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
  }, 0)
}

function Loading() {
  return (
    <div role="status" className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6">
      <p className="type-body text-ink-soft">Loading your files…</p>
      <div aria-hidden className="mt-4 space-y-3">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-6 w-1/2" />
      </div>
    </div>
  )
}

export default function Workspace({ projectId, initialProject, initialCatalog }: WorkspaceProps) {
  const [project, update] = useProject(projectId, initialProject)
  const [catalog, setCatalog] = useState<Catalog | null>(initialCatalog)
  const [loading, setLoading] = useState(initialCatalog === null)
  const [busy, setBusy] = useState<Busy | null>(null)
  const [problem, setProblem] = useState<Problem | null>(null)
  const [adding, setAdding] = useState(false)
  /** "Show me around again" in How Verity works (§6.7) — the record has already been marked done. */
  const [replaying, setReplaying] = useState(false)

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
        // Files live in server memory and are dropped after two hours or a restart (§6.6).
        if (error instanceof ApiError && error.status === 404) update({ sessionId: null })
        else setProblem(problemFrom(error))
        setLoading(false)
      })
    return () => {
      live = false
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

  // Above the composer: what is true about the files right now. The dialog below is a deliberate
  // exception — it belongs to a button in the sidebar, so it opens where the eye already is.
  const notice = ((problem && !adding) || detached) && (
    <div className="space-y-3 pb-1">
      {!adding && banner}
      {detached && <Reattach project={project} busy={busy} onFiles={onFiles} onSample={onSample} />}
    </div>
  )

  return (
    <div className="flex h-full flex-col">
      <Header
        project={{ id: project.id, name: project.name, savedCount: project.savedAnswerIds.length }}
        onRename={(name) => update({ name })}
        onReplayTour={catalog ? () => setReplaying(true) : undefined}
      />

      {/* `relative` matters: screen-reader-only text is absolutely positioned, and against an
          unpositioned scroller it is laid out on the page instead, which then scrolls as a whole. */}
      <div className="relative flex min-h-0 flex-1 flex-col md:flex-row">
        {/* The sidebar holds dozens of controls. A keyboard user can step over them; the link is
            invisible until it has focus, and absent on a phone, where the panel starts collapsed. */}
        <button
          type="button"
          onClick={() => document.getElementById('verity-question')?.focus()}
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-control focus:bg-sheet focus:px-3 focus:py-2 focus:type-small focus:font-medium focus:text-indigo max-md:hidden"
        >
          Skip to your question
        </button>

        {/* On a phone the sidebar is a panel above the conversation, so it is capped and scrolls:
            an expanded file list must not push the question box off the screen. `md:contents`
            takes this wrapper out of the layout again on a wide screen, where the sidebar is a
            column that sizes itself. */}
        <div className="shrink-0 overflow-y-auto max-md:max-h-[60dvh] md:contents">
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
                  status === 'rejected'
                    ? [...new Set([...project.removedLinkIds, linkId])]
                    : project.removedLinkIds.filter((id) => id !== linkId),
              })
            }
            onAddFiles={() => setAdding(true)}
          />
        </div>

        <main className="flex min-h-0 min-w-0 flex-1 flex-col">
          {loading ? (
            <Loading />
          ) : (
            <Thread
              sessionId={sessionId}
              catalog={catalog}
              turns={project.turns}
              onTurnsChange={(turns: Turn[]) => update({ turns })}
              savedAnswerIds={project.savedAnswerIds}
              onToggleSaved={(answerId: string) =>
                update({
                  savedAnswerIds: project.savedAnswerIds.includes(answerId)
                    ? project.savedAnswerIds.filter((id) => id !== answerId)
                    : [...project.savedAnswerIds, answerId],
                })
              }
              onSessionExpired={onSessionExpired}
              emptyState={catalog && <Briefing catalog={catalog} onAsk={askInComposer} />}
              notice={notice || undefined}
            />
          )}
        </main>
      </div>

      {/* "Add more files" lives in the Files tab; the picker opens here, where it cannot be missed
          and where Esc puts the analyst back on the button they pressed. */}
      <Dialog open={adding && !detached} onClose={() => setAdding(false)} title="Add files to this project" size="sm">
        <p className="type-body text-ink-soft">
          They join the files already loaded, and Verity looks for links between them the same way.
        </p>
        <div className="mt-4">{busy ? <UploadProgress busy={busy} /> : <DropZone onFiles={onFiles} />}</div>
        {banner && <div className="mt-3">{banner}</div>}
      </Dialog>

      {/* The first-run tour (§6.7). It waits for the files, so every step points at something that
          is already on the screen, and `tourDone` on the record is what remembers it. */}
      <Tour
        run={catalog !== null && (!project.tourDone || replaying)}
        onDone={() => {
          setReplaying(false)
          if (!project.tourDone) update({ tourDone: true })
        }}
      />
    </div>
  )
}
