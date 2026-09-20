// The whole router (§6): four hash routes plus the primitives gallery. No router library, because
// there is nothing here a library would do for us. Pure, so route.test.mjs runs it in Node; the
// hashchange listener lives in App.tsx.

export type Route =
  | { name: 'home' }
  | { name: 'project'; id: string }
  | { name: 'board'; id: string }
  | { name: 'trust' }
  | { name: 'gallery' }

export const HOME = '#/'
export const TRUST = '#/trust'
export const projectPath = (id: string) => `#/p/${encodeURIComponent(id)}`
export const boardPath = (id: string) => `#/p/${encodeURIComponent(id)}/board`

/** A hand-typed or truncated hash can hold a stray %, which decodeURIComponent throws on. */
function decode(part: string): string {
  try {
    return decodeURIComponent(part)
  } catch {
    return part
  }
}

/** Anything unrecognised is home: a stale bookmark should land somewhere useful, not nowhere. */
export function parseRoute(hash: string): Route {
  const [first, second, third] = hash.replace(/^#\/?/, '').split('/')
  if (first === 'trust') return { name: 'trust' }
  if (first === 'ui') return { name: 'gallery' }
  if (first === 'p' && second) {
    const id = decode(second)
    return third === 'board' ? { name: 'board', id } : { name: 'project', id }
  }
  return { name: 'home' }
}

/** Navigate. A hash assignment, so Back and Forward keep working without any history code. */
export function go(path: string): void {
  location.hash = path
}
