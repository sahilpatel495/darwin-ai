// The whole router (§6): the v3 hash routes plus the primitives gallery. No router library,
// because there is nothing here a library would do for us. Pure, so route.test.mjs runs it in
// Node; the hashchange listener lives in App.tsx.

export type Route =
  | { name: 'home' } // `#/` — the landing page signed out, your projects signed in (§6)
  | { name: 'signin' }
  | { name: 'signup' }
  | { name: 'welcome' }
  | { name: 'project'; id: string }
  | { name: 'overview'; id: string }
  | { name: 'analyses'; id: string }
  | { name: 'board'; id: string }
  | { name: 'how' }
  | { name: 'trust' }
  | { name: 'settings' }
  | { name: 'gallery' }

export const HOME = '#/'
/** The same screen as `#/` for someone signed in. Both exist because §6 names both. */
export const PROJECTS = '#/home'
export const SIGNIN = '#/signin'
export const SIGNUP = '#/signup'
export const WELCOME = '#/welcome'
export const HOW = '#/how'
export const TRUST = '#/trust'
export const SETTINGS = '#/settings'
export const GALLERY = '#/ui'

export const projectPath = (id: string) => `#/p/${encodeURIComponent(id)}`
export const overviewPath = (id: string) => `${projectPath(id)}/overview`
export const analysesPath = (id: string) => `${projectPath(id)}/analyses`
export const boardPath = (id: string) => `${projectPath(id)}/board`

/** A hand-typed or truncated hash can hold a stray %, which decodeURIComponent throws on. */
function decode(part: string): string {
  try {
    return decodeURIComponent(part)
  } catch {
    return part
  }
}

// The third segment of #/p/<id>/<page>. Anything else — a typo, a page we dropped — is the
// project's own ask page, which is where someone with a stale link wants to end up anyway.
const PAGES = { overview: 'overview', analyses: 'analyses', board: 'board' } as const

// The pages that are only a name. `home` is the fallback, so it is not in the table.
const TOP = {
  home: 'home',
  signin: 'signin',
  signup: 'signup',
  welcome: 'welcome',
  how: 'how',
  trust: 'trust',
  settings: 'settings',
  ui: 'gallery',
} as const

/** Anything unrecognised is home: a stale bookmark should land somewhere useful, not nowhere. */
export function parseRoute(hash: string): Route {
  const [first, second, third] = hash.replace(/^#\/?/, '').split('/')
  if (first === 'p' && second) {
    const id = decode(second)
    const page = PAGES[third as keyof typeof PAGES]
    return page ? { name: page, id } : { name: 'project', id }
  }
  const top = TOP[first as keyof typeof TOP]
  return top ? ({ name: top } as Route) : { name: 'home' }
}

/** The id of the project a route is about, or null for the routes that are about none. */
export function routeProjectId(route: Route): string | null {
  return 'id' in route ? route.id : null
}

/** The screens a visitor with no account can open: the landing, the two auth screens and the two
 *  pages that explain the product. Everything else is about work that belongs to somebody. */
const OPEN: Route['name'][] = ['home', 'signin', 'signup', 'how', 'trust', 'gallery']

/**
 * Where this route should send someone instead, or null to let them stay (§6).
 *
 * Two rules and no more: a visitor cannot open somebody's work, and a MEMBER has no use for the
 * two auth screens. Onboarding is deliberately NOT here — it is sent once per visit by the shell,
 * because a rule that redirected every visit to `#/home` could never be left.
 *
 * `guest` is the whole reason the second rule names members rather than everyone signed in. A
 * guest holds a token, so they are signed in — and sign-up is the one screen they most need:
 * "Create an account" in the avatar menu, the card in Settings and the landing all send them
 * there to keep the work they have already done. Bouncing them to their projects made that button
 * do nothing at all.
 */
export function guard(route: Route, signedIn: boolean, guest = false): string | null {
  if (!signedIn) return OPEN.includes(route.name) ? null : HOME
  if (!guest && (route.name === 'signin' || route.name === 'signup')) return PROJECTS
  return null
}

/** True while the route is one of the four tabs inside a project (§6). */
export const isProjectRoute = (route: Route): boolean =>
  route.name === 'project' || route.name === 'overview' || route.name === 'analyses' || route.name === 'board'

/** Navigate. A hash assignment, so Back and Forward keep working without any history code. */
export function go(path: string): void {
  location.hash = path
}
