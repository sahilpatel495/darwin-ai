// The whole router (§6). Four screens and the primitives gallery, chosen by the hash: no router
// library, no state library. Each screen owns its own state and its own header, so nothing here
// has to know what a catalog or a session is.
//
// The one exception is the catalog of a project that has just been created: it is already in
// memory, and handing it to the workspace is what keeps "sample data, then a question" the same
// length it has always been.

import { useEffect, useMemo, useRef, useState } from 'react'
import Board from './components/board/Board'
import Home from './components/home/Home'
import Header from './components/shell/Header'
import Workspace from './components/shell/Workspace'
import Gallery from './components/ui/Gallery'
import { getProject } from './lib/projects'
import type { ProjectRecord } from './lib/projects'
import { go, HOME, parseRoute, projectPath } from './lib/route'
import TrustReport from './pages/TrustReport'
import type { Catalog } from './types'

function useRoute() {
  const [hash, setHash] = useState(location.hash)
  useEffect(() => {
    const onHashChange = () => setHash(location.hash)
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])
  // Memoised so effects that depend on the route do not re-run on every render.
  return useMemo(() => parseRoute(hash), [hash])
}

/** The Trust Report is read from somewhere, so it offers the way back to that somewhere. */
function TrustPage({ fromProjectId }: { fromProjectId: string | null }) {
  const project = fromProjectId ? getProject(fromProjectId) : null
  return (
    <div className="flex h-full flex-col">
      <Header back={project ? { href: projectPath(project.id), label: `Back to ${project.name}` } : { href: HOME, label: 'Back to your projects' }} />
      <main className="relative min-h-0 flex-1 overflow-y-auto">
        <TrustReport />
      </main>
    </div>
  )
}

export default function App() {
  const route = useRoute()
  const [fresh, setFresh] = useState<{ project: ProjectRecord; catalog: Catalog } | null>(null)
  const lastProjectId = useRef<string | null>(null)

  useEffect(() => {
    if (route.name === 'project' || route.name === 'board') lastProjectId.current = route.id
    // The handover belongs to one visit to one project: it is dropped once that workspace has been
    // opened and left, so coming back asks the server whether the files are still there. It is
    // deliberately not dropped before then — this effect and the hashchange that follows `go()` are
    // two queued tasks, and the handover must not depend on which of them runs first.
    const used = fresh !== null && lastProjectId.current === fresh.project.id
    if (used && !(route.name === 'project' && route.id === fresh.project.id)) setFresh(null)
  }, [route, fresh])

  // A file dropped beside a drop zone would otherwise make the browser open it and leave the app.
  useEffect(() => {
    const keepPage = (event: DragEvent) => event.preventDefault()
    window.addEventListener('dragover', keepPage)
    window.addEventListener('drop', keepPage)
    return () => {
      window.removeEventListener('dragover', keepPage)
      window.removeEventListener('drop', keepPage)
    }
  }, [])

  switch (route.name) {
    case 'gallery':
      return <Gallery /> // components/ui/README.md
    case 'trust':
      return <TrustPage fromProjectId={lastProjectId.current} />
    case 'board':
      return <Board key={route.id} projectId={route.id} />
    case 'project': {
      // The record travels with the catalog: a browser with storage switched off has nothing to
      // find on disk, and the project just created must still open.
      const handover = fresh?.project.id === route.id ? fresh : null
      return <Workspace key={route.id} projectId={route.id} initialProject={handover?.project ?? null} initialCatalog={handover?.catalog ?? null} />
    }
    default:
      return (
        <Home
          onCreated={(project, catalog) => {
            setFresh({ project, catalog })
            go(projectPath(project.id))
          }}
        />
      )
  }
}
