// Your projects (§8). One greeting, one black pill, and a shelf of work — the sample company
// first, so the way in is never below the fold.
//
// There is no landing page here any more: a visitor never gets this far (§6), so everything on
// this screen can assume somebody is signed in and has, or is about to have, work of their own.

import { useEffect, useState } from 'react'
import { listProjects, onProjectsChanged } from '../../lib/projects'
import type { ProjectRecord } from '../../lib/projects'
import type { Catalog, User } from '../../types'
import { Banner, Button, Card, EmptyState } from '../ui'
import DropZone from '../upload/DropZone'
import UploadProgress from '../upload/UploadProgress'
import type { Busy } from '../upload/UploadProgress'
import { checkFiles } from '../upload/files'
import { NOTHING_READ, problemFrom } from '../shell/problem'
import type { Problem } from '../shell/problem'
import { createFromFiles, createFromSample, NothingRead } from './create'
import ProjectCard from './ProjectCard'
import SampleCard from './SampleCard'

interface HomeProps {
  user: User | null
  /** The workspace opens on the catalog that has just been read, without fetching it again. */
  onCreated: (project: ProjectRecord, catalog: Catalog) => void
}

/** "Good morning" is what a person says at nine, and this screen is the first thing they see. */
function greeting(user: User | null, now = new Date()): string {
  const hour = now.getHours()
  const part = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const first = user?.kind === 'member' ? user.name.trim().split(/\s+/)[0] : ''
  return first ? `${part}, ${first}` : part
}

export default function Home({ user, onCreated }: HomeProps) {
  const [projects, setProjects] = useState(listProjects)
  const [busy, setBusy] = useState<Busy | null>(null)
  const [problem, setProblem] = useState<Problem | null>(null)
  const [adding, setAdding] = useState(false)

  // Signing in as somebody else changes whose shelf this is, and deleting a project changes what
  // is on it. Either way the list is re-read rather than kept.
  useEffect(() => onProjectsChanged(() => setProjects(listProjects())), [])

  async function create(work: Promise<{ project: ProjectRecord; catalog: Catalog }>) {
    setProblem(null)
    try {
      const { project, catalog } = await work
      onCreated(project, catalog)
    } catch (error) {
      setProblem(error instanceof NothingRead ? NOTHING_READ : problemFrom(error))
    } finally {
      setBusy(null)
    }
  }

  function onFiles(picked: File[]) {
    const { accepted, problems } = checkFiles(picked)
    if (problems.length) setProblem({ message: problems.join('\n'), nextStep: '', tone: 'warn' })
    if (!accepted.length) return
    setBusy({ kind: 'upload', files: accepted.length, fraction: 0 })
    void create(createFromFiles(accepted, (fraction) => setBusy({ kind: 'upload', files: accepted.length, fraction })))
  }

  function onSample() {
    setBusy({ kind: 'sample' })
    void create(createFromSample())
  }

  return (
    <main className="mx-auto w-full max-w-[1120px] px-4 py-10 sm:px-6 sm:py-14">
      <h1 className="text-display-lg text-ink-deep">{greeting(user)}</h1>
      <p className="mt-4 measure text-subtitle-md text-slate">
        Every project keeps its own files, the questions you asked about them, and the report you built from the answers.
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <Button variant="primary" aria-expanded={adding} aria-controls="new-project-files" onClick={() => setAdding((was) => !was)}>
          New project
        </Button>
        <p className="text-body-sm text-steel">CSV, TSV or Excel — the exports you already have, as they are.</p>
      </div>

      <div id="new-project-files">
        {busy ? (
          <Card className="mt-5">
            <UploadProgress busy={busy} />
          </Card>
        ) : (
          adding && <DropZone onFiles={onFiles} className="mt-5" />
        )}
      </div>

      {problem && (
        <Banner tone={problem.tone} nextStep={problem.nextStep} onDismiss={() => setProblem(null)} className="mt-5">
          {problem.message}
        </Banner>
      )}

      {projects.length === 0 && !adding && !busy && (
        <EmptyState glyph="upload" className="mt-8" action={<Button variant="primary" onClick={() => setAdding(true)}>Add your files</Button>}>
          Nothing here yet. Drop in a messy export, or open the sample company below and ask it something.
        </EmptyState>
      )}

      {/* Each card is its own <article>, so the grid is a plain div rather than a list of one-item
          list items. The stagger runs once, on the children it can see (§4). */}
      <div className="stagger-children mt-8 grid grid-cols-1 items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <SampleCard onSample={onSample} busy={busy !== null} />
        {projects.map((project) => (
          <ProjectCard key={project.id} project={project} onChanged={() => setProjects(listProjects())} />
        ))}
      </div>

      <p className="mt-8 text-body-sm text-steel">Projects are saved in this browser, under your account. Your files are never stored on our server.</p>
    </main>
  )
}
