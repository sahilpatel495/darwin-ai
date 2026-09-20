// Home (§6.1). With no projects it is the landing — the product's promise, shown. With projects it
// is the register of them: ruled rows, the two ways to start a new one above.

import { useState } from 'react'
import { ensureSession, loadSample, resetSession, uploadFiles } from '../../api'
import { createProject, fileNamesFrom, listProjects, projectName } from '../../lib/projects'
import type { ProjectRecord } from '../../lib/projects'
import type { Catalog } from '../../types'
import { Banner, Button } from '../ui'
import DropZone from '../upload/DropZone'
import Landing from '../upload/Landing'
import UploadProgress from '../upload/UploadProgress'
import type { Busy } from '../upload/UploadProgress'
import { checkFiles } from '../upload/files'
import Header from '../shell/Header'
import { NOTHING_READ, problemFrom } from '../shell/problem'
import type { Problem } from '../shell/problem'
import ProjectRow from './ProjectRow'

interface HomeProps {
  /** The workspace opens on the catalog that has just been read, without fetching it again. */
  onCreated: (project: ProjectRecord, catalog: Catalog) => void
}

export default function Home({ onCreated }: HomeProps) {
  const [projects, setProjects] = useState(listProjects)
  const [busy, setBusy] = useState<Busy | null>(null)
  const [problem, setProblem] = useState<Problem | null>(null)
  const [adding, setAdding] = useState(false)

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
          <Landing busy={busy} onFiles={onFiles} onSample={onSample} />
        </main>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <Header />
      <main className="relative min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-4xl px-4 py-10 sm:px-6">
          <h1 className="type-headline text-ink">Your projects</h1>
          <p className="mt-3 measure type-body text-ink-soft">
            Each project keeps its own files, its questions and the answers you saved.
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-2">
            <Button variant="primary" aria-expanded={adding} aria-controls="new-project-files" onClick={() => setAdding((was) => !was)}>
              New project
            </Button>
            <Button onClick={onSample} disabled={busy !== null}>
              Try with sample HR data
            </Button>
          </div>

          {notice && <div className="mt-4">{notice}</div>}

          <div id="new-project-files">
            {busy ? <UploadProgress busy={busy} className="mt-5" /> : adding && <DropZone onFiles={onFiles} className="mt-5" />}
          </div>

          <ul className="mt-8 border-t border-rule">
            {projects.map((project) => (
              <ProjectRow key={project.id} project={project} onChanged={() => setProjects(listProjects())} />
            ))}
          </ul>

          <p className="mt-4 type-small text-ink-soft">Projects are saved in this browser. Your files are never stored on our server.</p>
        </div>
      </main>
    </div>
  )
}
