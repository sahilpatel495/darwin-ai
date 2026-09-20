// Home (§6.1, §15). With no projects it is the landing — the product's promise, shown. With
// projects it is the shelf of them: interactive cards, the sample always first so the way in is
// never below the fold, and the two ways to start something new above.

import { useState } from 'react'
import { ensureSession, loadSample, resetSession, uploadFiles } from '../../api'
import { createProject, fileNamesFrom, listProjects, projectName } from '../../lib/projects'
import type { ProjectRecord } from '../../lib/projects'
import type { Catalog } from '../../types'
import { Banner, Button, Card } from '../ui'
import DropZone from '../upload/DropZone'
import Landing from '../upload/Landing'
import UploadProgress from '../upload/UploadProgress'
import type { Busy } from '../upload/UploadProgress'
import { checkFiles } from '../upload/files'
import Header from '../shell/Header'
import { NOTHING_READ, problemFrom } from '../shell/problem'
import type { Problem } from '../shell/problem'
import ProjectCard from './ProjectCard'
import SampleCard from './SampleCard'
import SampleFilesDialog from './SampleFilesDialog'

interface HomeProps {
  /** The workspace opens on the catalog that has just been read, without fetching it again. */
  onCreated: (project: ProjectRecord, catalog: Catalog) => void
}

export default function Home({ onCreated }: HomeProps) {
  const [projects, setProjects] = useState(listProjects)
  const [busy, setBusy] = useState<Busy | null>(null)
  const [problem, setProblem] = useState<Problem | null>(null)
  const [adding, setAdding] = useState(false)
  /** The landing's "See what's inside". The card on the shelf opens its own copy. */
  const [showingSample, setShowingSample] = useState(false)

  /** Files (or the sample) become a project: a fresh session, then a record named after the files. */
  async function create(load: (sessionId: string) => Promise<Catalog>, isSample: boolean) {
    setProblem(null)
    try {
      // ponytail: this tab holds one live session at a time (api.ts keeps a single id), so a new
      // project starts a fresh one and any other project's files are dropped with it.
      resetSession()
      const sessionId = await ensureSession()
      const catalog = await load(sessionId)
      if (!catalog?.tables?.length) {
        setProblem(NOTHING_READ)
        return
      }
      const fileNames = fileNamesFrom(catalog)
      onCreated(createProject({ name: projectName(fileNames, isSample), isSample, fileNames, sessionId }), catalog)
    } catch (error) {
      setProblem(problemFrom(error))
    } finally {
      setBusy(null)
    }
  }

  function onFiles(picked: File[]) {
    const { accepted, problems } = checkFiles(picked)
    if (problems.length) setProblem({ message: problems.join('\n'), nextStep: '', tone: 'warn' })
    if (!accepted.length) return
    setBusy({ kind: 'upload', files: accepted.length, fraction: 0 })
    void create((id) => uploadFiles(id, accepted, (fraction) => setBusy({ kind: 'upload', files: accepted.length, fraction })), false)
  }

  function onSample() {
    setBusy({ kind: 'sample' })
    void create(loadSample, true)
  }

  const notice = problem && (
    <Banner tone={problem.tone} nextStep={problem.nextStep} onDismiss={() => setProblem(null)}>
      {problem.message}
    </Banner>
  )

  // First visit: the landing, and nothing else to read past.
  if (projects.length === 0) {
    return (
      <div className="flex h-full flex-col">
        <Header />
        <main className="relative min-h-0 flex-1 overflow-y-auto">
          {notice && <div className="mx-auto w-full max-w-5xl px-4 pt-4 sm:px-6">{notice}</div>}
          <Landing busy={busy} onFiles={onFiles} onSample={onSample} onShowSample={() => setShowingSample(true)} />
          <SampleFilesDialog open={showingSample} onClose={() => setShowingSample(false)} onLoad={onSample} busy={busy !== null} />
        </main>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <Header />
      <main className="relative min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
          <h1 className="type-page text-ink">Your projects</h1>
          <p className="mt-1 measure type-body text-ink-2">Each project keeps its own files, its questions and everything you saved to its board.</p>

          <div className="mt-5">
            <Button variant="primary" aria-expanded={adding} aria-controls="new-project-files" onClick={() => setAdding((was) => !was)}>
              New project
            </Button>
          </div>

          <div id="new-project-files">
            {busy ? (
              <Card className="mt-4">
                <UploadProgress busy={busy} />
              </Card>
            ) : (
              adding && <DropZone onFiles={onFiles} className="mt-4" />
            )}
          </div>

          {notice && <div className="mt-4">{notice}</div>}

          <div className="stagger-children mt-6 grid grid-cols-1 items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <SampleCard onSample={onSample} busy={busy !== null} />
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} onChanged={() => setProjects(listProjects())} />
            ))}
          </div>

          <p className="mt-6 type-small text-ink-2">Projects are saved in this browser. Your files are never stored on our server.</p>
        </div>
      </main>
    </div>
  )
}
