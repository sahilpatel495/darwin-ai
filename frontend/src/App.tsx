// The whole router (§6) and the one shell around it. Twelve hash routes and the primitives
// gallery, chosen by the hash: no router library, no state library.
//
// Three things live here and nowhere else, because they are true of every screen:
//  - who is signed in (`useSession`), which decides whether a visitor sees the landing or an
//    analyst sees their projects, and which shelf of projects `lib/projects` reads;
//  - the command palette and its ⌘K, because the search pill is in the bar that is always up;
//  - the handover of a question from one screen to another, which has to survive the navigation
//    between them.
//
// Everything inside a project — the files, the Data drawer, and the one answer to "your files are
// no longer loaded" — belongs to ProjectShell, so the four tabs share one of each.

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import AuthPage from './components/auth/AuthPage'
import Home from './components/home/Home'
import { createFromFiles, createFromSample, NothingRead } from './components/home/create'
import Landing from './components/marketing/Landing'
import { MarketingFooter, MarketingNav } from './components/marketing/MarketingChrome'
import Welcome from './components/onboarding/Welcome'
import UploadProgress from './components/upload/UploadProgress'
import type { LoadSource } from './components/onboarding/Welcome'
import CommandPalette from './components/shell/CommandPalette'
import MobileTabBar from './components/shell/MobileTabBar'
import ProjectShell from './components/shell/ProjectShell'
import TopBar from './components/shell/TopBar'
import { NOTHING_READ, problemFrom } from './components/shell/problem'
import type { Problem } from './components/shell/problem'
import SettingsPage from './components/settings/SettingsPage'
import Gallery from './components/ui/Gallery'
import { Toaster, toast } from './components/ui'
import { getStoredUser } from './api'
import { getProject, listProjects, onProjectsChanged, scopeProjectsTo } from './lib/projects'
import type { ProjectRecord } from './lib/projects'
import { go, guard, HOME, isProjectRoute, overviewPath, parseRoute, projectPath, PROJECTS, routeProjectId, WELCOME } from './lib/route'
import type { Route } from './lib/route'
import { useSession } from './lib/session'
import HowItWorks from './pages/HowItWorks'
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

/** One scrollable page for the screens that are not a project's own full-height layout. */
const Page = ({ children }: { children: React.ReactNode }) => (
  <main className="mx-auto w-full max-w-[1120px] px-4 py-8 sm:px-6 sm:py-12">{children}</main>
)

export default function App() {
  const route = useRoute()
  const session = useSession()
  const [fresh, setFresh] = useState<{ project: ProjectRecord; catalog: Catalog } | null>(null)
  const lastProjectId = useRef<string | null>(null)
  // A question handed over from another screen or the palette. State, not a ref: the workspace
  // needs it to survive until its files have loaded, which is several renders after the click.
  const [pending, setPending] = useState<string | null>(null)
  const [dataOpen, setDataOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [demoBusy, setDemoBusy] = useState(false)
  const [demoProblem, setDemoProblem] = useState<Problem | null>(null)

  // Projects belong to a person (§10). Set during render, before any child reads the shelf: it is
  // a pointer, not state, and pointing it twice at the same person does nothing.
  scopeProjectsTo(session.user?.id ?? null)

  // Any write anywhere re-reads the record here: renaming in a card renames the project in the
  // top bar, and saving a tile lights the Saved tab, without either screen knowing this exists.
  const [, reread] = useReducer((n: number) => n + 1, 0)
  useEffect(() => onProjectsChanged(reread), [])

  const signedIn = session.status === 'ready'
  const projects = signedIn ? listProjects() : []

  useEffect(() => {
    const id = routeProjectId(route)
    if (id) lastProjectId.current = id
    setDataOpen(false) // a drawer left open across a page change is a drawer nobody asked for
    setSearchOpen(false)
    // The handover belongs to one visit to one project: it is dropped once that workspace has been
    // opened and left, so coming back asks the server whether the files are still there. It is
    // deliberately not dropped before then — this effect and the hashchange that follows `go()` are
    // two queued tasks, and the handover must not depend on which of them runs first.
    const used = fresh !== null && lastProjectId.current === fresh.project.id
    if (used && !(route.name === 'project' && route.id === fresh.project.id)) setFresh(null)
  }, [route, fresh])

  // §6: a visitor cannot open somebody's work, and a member has no use for the two auth screens.
  // A guest is signed in but still needs sign-up — it is how they keep what they have done — so
  // the guard is told which they are. Held until the session has answered, so nobody is bounced
  // off their own bookmark while the token is still being checked.
  const isGuest = session.user !== null && session.user.kind !== 'member'
  useEffect(() => {
    if (session.status === 'starting') return
    // The hash is the truth; `route` is a render behind it. Signing up sets the hash to #/welcome
    // and turns `signedIn` on in the same tick, so this effect used to run once with the route it
    // still thought it was on — #/signup — and send a brand-new member to their projects, over the
    // top of the onboarding they were already on their way to. Nobody ever saw the three steps.
    if (parseRoute(location.hash).name !== route.name) return
    const elsewhere = guard(route, signedIn, isGuest)
    if (elsewhere) go(elsewhere)
  }, [route, session.status, signedIn, isGuest])

  // Onboarding runs once (§7), and once means once per visit rather than once per navigation: a
  // rule that redirected every arrival at `#/home` would be a room with no door.
  const welcomed = useRef(false)
  useEffect(() => {
    if (welcomed.current || !session.user || session.user.onboarded) return
    welcomed.current = true
    if (route.name === 'home') go(WELCOME)
  }, [route.name, session.user])

  // ⌘K is the search pill's keyboard twin, bound here because the bar is on every screen.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'k' || !(event.metaKey || event.ctrlKey)) return
      event.preventDefault()
      setSearchOpen((was) => !was)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

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

  const opened = useCallback((project: ProjectRecord, catalog: Catalog) => {
    setFresh({ project, catalog })
    go(projectPath(project.id))
  }, [])

  /** The evaluator's path (§7): a guest account, the sample company, and a question, in one press. */
  const tryDemo = useCallback(async () => {
    setDemoBusy(true)
    setDemoProblem(null)
    // The demo is its own introduction, so it does not detour through onboarding: without this the
    // guest account arrives a second before the sample does and the welcome screen flashes past.
    welcomed.current = true
    try {
      await session.continueAsGuest()
      // Pointed at the new guest's shelf before anything is written to it. Read from api.ts rather
      // than from `session.user`, which is a render away: the record below is created several
      // awaits later, and it must not land on the shelf we were reading a moment ago.
      scopeProjectsTo(getStoredUser()?.id ?? null)
      const { project, catalog } = await createFromSample()
      opened(project, catalog)
    } catch (error) {
      const problem = error instanceof NothingRead ? NOTHING_READ : problemFrom(error)
      setDemoProblem(problem)
      // The banner belongs to the landing page — but by the time the sample can fail, the guest
      // account already exists, so the landing has been replaced by their (empty) projects screen
      // and nobody ever reads it. Pressing "Try the live demo" and arriving nowhere, silently, is
      // the worst version of this. The toast follows them to whichever screen they landed on.
      toast(problem.nextStep ? `${problem.message} ${problem.nextStep}` : problem.message, 'error')
    } finally {
      setDemoBusy(false)
    }
  }, [session, opened])

  const askIn = useCallback((projectId: string, question: string) => {
    setPending(question)
    go(projectPath(projectId))
  }, [])

  /** The project onboarding made, so its last step can ask a question in it or open its overview. */
  const onboarded = useRef<ProjectRecord | null>(null)

  /** Onboarding brings the files; project records are the app's, so it is made here (§7 step 2). */
  const onboardingLoad = useCallback(async (source: LoadSource): Promise<Catalog> => {
    const created = source.kind === 'sample' ? await createFromSample() : await createFromFiles(source.files, () => {})
    onboarded.current = created.project
    // Held so the workspace opens on the catalog that was just read rather than fetching it again.
    setFresh(created)
    return created.catalog
  }, [])

  /** Signed in, signed up or continuing as a guest. Somebody new is shown the three steps; anyone
   *  who has been through them already goes straight to their work. Read from api.ts, because
   *  `session.user` is a render away and this runs inside the form's own handler. */
  const onAuthed = useCallback(() => {
    const next = getStoredUser()
    welcomed.current = true // this decision is the one the effect below would otherwise make
    go(next && !next.onboarded ? WELCOME : PROJECTS)
  }, [])

  // The gallery is the design system's own page: full width, no product chrome around it.
  if (route.name === 'gallery') return <Gallery /> // components/ui/README.md

  const projectId = routeProjectId(route)
  const project = projectId ? (fresh?.project.id === projectId ? fresh.project : getProject(projectId)) : null

  let screen: React.ReactNode
  if (session.status === 'starting') {
    // The token is being checked. Anything drawn now would be the wrong screen for somebody: a
    // member would see the landing for a moment, a visitor would see an empty projects shelf.
    screen = <div className="min-h-[60vh]" />
  } else if (!signedIn) {
    // Everything a visitor can reach. The guard above has already sent them here from anywhere
    // else, and `starting` draws the landing's frame without its contents rather than a spinner.
    switch (route.name) {
      case 'signin':
      case 'signup':
        screen = <AuthPage mode={route.name} session={session} user={session.user} onAuthed={onAuthed} />
        break
      case 'how':
        screen = <HowItWorks />
        break
      case 'trust':
        screen = (
          <Page>
            <TrustReport />
          </Page>
        )
        break
      default:
        screen = <Landing onTryDemo={() => void tryDemo()} loading={demoBusy} error={demoProblem} onDismissError={() => setDemoProblem(null)} />
    }
  } else {
    switch (route.name) {
      // A guest upgrading in place. The guard lets only a guest this far, and AuthPage is handed
      // the guest's own user so signing up keeps their id, their projects and their questions.
      case 'signin':
      case 'signup':
        screen = <AuthPage mode={route.name} session={session} user={session.user} onAuthed={onAuthed} />
        break
      case 'welcome':
        screen = (
          <Welcome
            user={session.user}
            session={session}
            catalog={fresh?.catalog ?? null}
            onLoad={onboardingLoad}
            onAsk={(question) => onboarded.current && askIn(onboarded.current.id, question)}
            onOverview={() => onboarded.current && go(overviewPath(onboarded.current.id))}
            onSkip={() => go(onboarded.current ? projectPath(onboarded.current.id) : PROJECTS)}
          />
        )
        break
      case 'how':
        screen = <HowItWorks />
        break
      case 'trust':
        screen = (
          <Page>
            <TrustReport />
          </Page>
        )
        break
      case 'settings':
        screen = <SettingsPage session={session} />
        break
      case 'project':
      case 'overview':
      case 'analyses':
      case 'board':
        screen = (
          <ProjectShell
            key={route.id}
            route={route}
            projectId={route.id}
            user={session.user}
            initialProject={fresh?.project.id === route.id ? fresh.project : null}
            initialCatalog={fresh?.project.id === route.id ? fresh.catalog : null}
            pendingQuestion={pending}
            // Dropped the moment the workspace has asked it, so coming back to this project later
            // does not re-ask a question the analyst has already had answered.
            onQuestionTaken={() => setPending(null)}
            onAsk={(question) => askIn(route.id, question)}
            onAnswered={session.refreshUsage}
            dataOpen={dataOpen}
            onDataOpenChange={setDataOpen}
          />
        )
        break
      default:
        screen = <Home user={session.user} onCreated={opened} />
    }
    // "Try the live demo" signs the visitor in as a guest a few seconds before the sample company
    // has been read (about eight seconds on the free host). Without this they are dropped on an
    // empty projects screen with no sign that anything is happening, press the sample card as
    // well, and the two reads collide. One screen, one sentence, until the workspace opens.
    if (demoBusy && route.name === 'home') {
      screen = (
        <Page>
          <div role="status" className="mx-auto max-w-[560px] pt-16 text-center">
            <h1 className="text-heading-lg text-ink-deep">Opening the sample company</h1>
            <p className="mt-3 text-body-md text-slate">Reading six messy spreadsheets and finding the links between them. About ten seconds.</p>
            <div className="mt-8 text-left">
              <UploadProgress busy={{ kind: 'sample' }} />
            </div>
          </div>
        </Page>
      )
    }
  }

  const onProjectPage = isProjectRoute(route) && project !== null
  // A visitor reading How it works or Trust is on a marketing page, so it gets the marketing
  // frame — both halves of it. The footer is not decoration here: it carries the line that says
  // this is an independent prototype, which every page a visitor can reach has to state.
  const marketingChrome = !signedIn && (route.name === 'how' || route.name === 'trust')

  // The Ask tab is the one screen that must be exactly as tall as the window: the conversation
  // scrolls inside it and the composer stays docked at the bottom however long the thread gets.
  // With `min-h-full` the wrapper grows with the conversation, the page scrolls instead, and the
  // composer scrolls away with it. Every other screen is a document and grows freely.
  const askScreen = onProjectPage && route.name === 'project'

  return (
    <div className={`flex flex-col ${askScreen ? 'h-dvh overflow-hidden print:h-auto print:overflow-visible' : 'min-h-full'}`}>
      {/* The landing and the auth screens bring their own chrome (§7), so the only bar drawn here
          is the app's — plus the marketing nav for a visitor reading How it works or Trust. */}
      {/* A guest upgrading is on the auth screen, which brings its own full-height chrome (§7):
          the app bar on top of it would push the split layout down and cut off the first field. */}
      {signedIn && route.name !== 'signin' && route.name !== 'signup' ? (
        <TopBar
          route={route}
          project={onProjectPage ? project : null}
          projects={projects}
          user={session.user}
          onOpenData={onProjectPage ? () => setDataOpen(true) : undefined}
          onOpenSearch={() => setSearchOpen(true)}
          onSignOut={() => void session.signOut().then(() => go(HOME))}
        />
      ) : (
        marketingChrome && <MarketingNav />
      )}

      {/* Keyed by the route so the incoming page fades in and rises 12px (§4); nothing animates on
          the way out, so leaving is instant. The bottom padding is the phone's tab bar, which is
          fixed and so takes no space of its own. */}
      {/* The reader is part of the key: projects live on one shelf per person (§10), so signing in
          as somebody else is a different screen and not the same one with different words. */}
      <div
        key={`${session.user?.id ?? 'none'}:${route.name}:${projectId ?? ''}`}
        className={`page-enter flex min-h-0 flex-1 flex-col ${onProjectPage ? 'pb-[calc(env(safe-area-inset-bottom,0px)+4.5rem)] md:pb-0' : ''}`}
      >
        {screen}
      </div>

      {marketingChrome && <MarketingFooter />}

      {onProjectPage && project && <MobileTabBar route={route} projectId={project.id} />}

      <CommandPalette
        open={searchOpen && signedIn}
        onClose={() => setSearchOpen(false)}
        projects={projects}
        project={project}
        onAsk={askIn}
      />
      <Toaster />
    </div>
  )
}
