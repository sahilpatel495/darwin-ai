// The whole router (§6): six hash routes plus the primitives gallery. No router library, because
// there is nothing here a library would do for us. Pure, so route.test.mjs runs it in Node; the
// hashchange listener lives in App.tsx.

export type Route =
  | { name: 'home' }
  | { name: 'project'; id: string }
  | { name: 'overview'; id: string }
  | { name: 'analyses'; id: string }
  | { name: 'board'; id: string }
  | { name: 'trust' }
  | { name: 'gallery' }

export const HOME = '#/'
export const TRUST = '#/trust'
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

/** Anything unrecognised is home: a stale bookmark should land somewhere useful, not nowhere. */
export function parseRoute(hash: string): Route {
  const [first, second, third] = hash.replace(/^#\/?/, '').split('/')
  if (first === 'trust') return { name: 'trust' }
  if (first === 'ui') return { name: 'gallery' }
  if (first === 'p' && second) {
    const id = decode(second)
    const page = PAGES[third as keyof typeof PAGES]
    return page ? { name: page, id } : { name: 'project', id }
  }
  return { name: 'home' }
}

/** The id of the project a route is about, or null for the routes that are about none. */
export function routeProjectId(route: Route): string | null {
  return 'id' in route ? route.id : null
}

/** Navigate. A hash assignment, so Back and Forward keep working without any history code. */
export function go(path: string): void {
  location.hash = path
}
