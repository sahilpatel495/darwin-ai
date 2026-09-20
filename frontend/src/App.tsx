// The whole router (§6) and the one shell around it. Seven screens and the primitives gallery,
// chosen by the hash: no router library, no state library. Each screen owns its own state, so
// nothing here has to know what a catalog or a session is.
//
// Three exceptions, all about not losing something the analyst already has:
//  - the catalog of a project just created is already in memory, and handing it to the workspace
//    is what keeps "sample data, then a question" the same length it has always been;
//  - a question sent from Overview or Analyses is held here until the Ask page it lands on has
//    its files loaded and can run it (§13, §14);
//  - a change any screen makes to a project record is announced by lib/projects, so the nav rail
//    shows the name the analyst has just typed rather than the one on disk when this rendered.

import { useEffect, useMemo, useReducer, useRef, useState } from 'react'
import AnalysesPage from './components/analyses/AnalysesPage'
import Board from './components/board/Board'
import Home from './components/home/Home'
import OverviewPage from './components/overview/OverviewPage'
import Header from './components/shell/Header'
import MissingProject from './components/shell/MissingProject'
import Workspace from './components/shell/Workspace'
import Gallery from './components/ui/Gallery'
import { AnalysesIcon, AskIcon, HomeIcon, NavRail, OverviewIcon, SavedIcon, Toaster, TrustIcon } from './components/ui'
import type { NavItemSpec } from './components/ui'
import { getProject, onProjectsChanged, updateProject } from './lib/projects'
import type { ProjectRecord } from './lib/projects'
import { analysesPath, boardPath, go, HOME, overviewPath, parseRoute, projectPath, routeProjectId, TRUST } from './lib/route'
import type { Route } from './lib/route'
import TrustReport from './pages/TrustReport'
import type { Catalog } from './types'

function useRoute(): Route {
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

/** One scrollable page for the screens that are not the workspace's own full-height layout. */
function Page({ project, onRename, children }: { project: ProjectRecord; onRename: (name: string) => void; children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <Header project={{ id: project.id, name: project.name }} onRename={onRename} />
      <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  )
}

/** Which nav item is lit. The gallery lights none: it is the design system, not a destination. */
const NAV_ACTIVE: Record<Route['name'], string> = {
  home: 'home',
  project: 'ask',
  overview: 'overview',
  analyses: 'analyses',
  board: 'saved',
  trust: 'trust',
  gallery: '',
}

export default function App() {
  const route = useRoute()
  const [fresh, setFresh] = useState<{ project: ProjectRecord; catalog: Catalog } | null>(null)
  const lastProjectId = useRef<string | null>(null)
  // A question handed over from Overview or Analyses. State, not a ref: the workspace needs it to
  // survive until its files have loaded, which is several renders after the click.
  const [pending, setPending] = useState<string | null>(null)
  // The record as a page has just changed it, for the browser that has nowhere to store it. It
  // belongs to one visit to one page, so it is dropped whenever the route changes.
  const [local, setLocal] = useState<ProjectRecord | null>(null)

  // Any write anywhere re-reads the record here: renaming in the workspace header renames the
  // project in the rail, and saving a tile lights the Saved tab, without either screen knowing
  // this component exists.
  const [, reread] = useReducer((n: number) => n + 1, 0)
  useEffect(() => onProjectsChanged(reread), [])

  useEffect(() => {
    const id = routeProjectId(route)
    if (id) lastProjectId.current = id
    setLocal(null)
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

  // The gallery is the design system's own page: full width, no product chrome around it.
  if (route.name === 'gallery') return <Gallery /> // components/ui/README.md

  const projectId = routeProjectId(route)
  const stored = projectId ? (fresh?.project.id === projectId ? fresh.project : getProject(projectId)) : null
  const project = local?.id === projectId ? local : stored

  const askFrom = (id: string) => (question: string) => {
    setPending(question)
    go(projectPath(id))
  }

  /** A page changed the record (§10): store it, and keep it on screen either way. */
  const onProjectChange = (next: ProjectRecord) => setLocal(updateProject(next.id, next) ?? next)

  const items: NavItemSpec[] = [
    { id: 'home', label: 'Home', href: HOME, icon: <HomeIcon /> },
    { id: 'ask', label: 'Ask', href: project ? projectPath(project.id) : HOME, icon: <AskIcon />, disabled: !project },
    { id: 'overview', label: 'Overview', href: project ? overviewPath(project.id) : HOME, icon: <OverviewIcon />, disabled: !project },
    { id: 'analyses', label: 'Analyses', href: project ? analysesPath(project.id) : HOME, icon: <AnalysesIcon />, disabled: !project },
    { id: 'saved', label: 'Saved', href: project ? boardPath(project.id) : HOME, icon: <SavedIcon />, disabled: !project },
    // The tour's fourth step points here (§10). The header no longer carries a Trust link, so this
    // is the only element with that anchor.
    { id: 'trust', label: 'Trust', href: TRUST, icon: <TrustIcon />, anchorProps: { 'data-tour': 'trust' } },
  ].map((item) => ({ ...item, disabledReason: 'Open a project first' }))

  let screen: React.ReactNode
  switch (route.name) {
    case 'trust':
      screen = <TrustPage fromProjectId={lastProjectId.current} />
      break
    case 'board':
      screen = <Board key={route.id} projectId={route.id} />
      break
    case 'overview':
    case 'analyses': {
      if (!project) {
        screen = <MissingProject />
        break
      }
      const Screen = route.name === 'overview' ? OverviewPage : AnalysesPage
      screen = (
        <Page project={project} onRename={(name) => onProjectChange({ ...project, name })}>
          <Screen sessionId={project.sessionId} project={project} onAsk={askFrom(project.id)} onProjectChange={onProjectChange} />
        </Page>
      )
      break
    }
    case 'project': {
      // The record travels with the catalog: a browser with storage switched off has nothing to
      // find on disk, and the project just created must still open.
      const handover = fresh?.project.id === route.id ? fresh : null
      screen = (
        <Workspace
          key={route.id}
          projectId={route.id}
          initialProject={handover?.project ?? null}
          initialCatalog={handover?.catalog ?? null}
          initialQuestion={pending}
          // Dropped the moment the workspace has asked it, so coming back to this project later
          // does not re-ask a question the analyst has already had answered.
          onQuestionTaken={() => setPending(null)}
        />
      )
      break
    }
    default:
      screen = (
        <Home
          onCreated={(created, catalog) => {
            setFresh({ project: created, catalog })
            go(projectPath(created.id))
          }}
        />
      )
  }

  return (
    <div className="flex h-full">
      {/* Appearance lives in the header's settings, which is on every screen at every width; the
          rail is 72px of navigation and nothing else. */}
      <NavRail items={items} active={NAV_ACTIVE[route.name]} project={project ? { name: project.name, href: projectPath(project.id) } : null} />
      {/* Keyed by the route so the incoming page fades in and rises 8px (§4); nothing animates on
          the way out, so leaving is instant. The bottom padding is the phone's tab bar, which is
          fixed and so takes no space of its own. */}
      <div key={`${route.name}:${projectId ?? ''}`} className="page-enter min-h-0 min-w-0 flex-1 pb-[calc(env(safe-area-inset-bottom,0px)+3.75rem)] md:pb-0">
        {screen}
      </div>
      <Toaster />
    </div>
  )
}
