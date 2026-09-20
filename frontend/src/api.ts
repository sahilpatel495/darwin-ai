// The only file that talks to the backend. Lead-owned: it must match backend/app/main.py.
// Set VITE_MOCK=1 to develop the UI against ./fixtures with no backend running.

import type { AnalysisCatalog, AnalysisRequest, Answer, AuthResponse, MeResponse, User, AskRequest, Catalog, Dashboard, ErrorResponse, EvalReport, InsightTile, Metric, ResultTable, StepEvent } from './types'

const MOCK = import.meta.env.VITE_MOCK === '1'
const SESSION_KEY = 'verity.session'
const TOKEN_KEY = 'verity.token'
const USER_KEY = 'verity.user'

// ---- Accounts. The token is the only credential; it lives in localStorage and rides on every
// API call. With no token we silently become a guest, so "try the live demo" needs no sign-up.
const read = (key: string): string | null => {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}
const write = (key: string, value: string | null): void => {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* storage unavailable: the app still works for this page view */
  }
}
export const getToken = (): string | null => read(TOKEN_KEY)
export function getStoredUser(): User | null {
  try {
    return JSON.parse(read(USER_KEY) ?? 'null') as User | null
  } catch {
    return null
  }
}
function remember(auth: AuthResponse): AuthResponse {
  write(TOKEN_KEY, auth.token)
  write(USER_KEY, JSON.stringify(auth.user))
  return auth
}
function withAuth(init?: RequestInit): RequestInit {
  const token = getToken()
  if (!token) return init ?? {}
  return { ...init, headers: { ...(init?.headers as Record<string, string> | undefined), Authorization: `Bearer ${token}` } }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public nextStep: string,
  ) {
    super(message)
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  let body: Partial<ErrorResponse> = {}
  try {
    body = await res.json()
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(
    res.status,
    body.message ?? 'Something went wrong on our side.',
    body.next_step ?? 'Please try again in a moment.',
  )
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, withAuth(init))
  } catch {
    throw new ApiError(0, 'Could not reach the server.', 'Check your connection and try again.')
  }
  if (!res.ok) throw await toApiError(res)
  return res.json() as Promise<T>
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// Session id lives in sessionStorage (not a cookie: embedded hosts block third-party cookies).
// Sessions are in server memory, so a redeploy invalidates them: callers treat ApiError 404 as
// "session expired", call resetSession() and ask the user to upload again.
export async function ensureSession(): Promise<string> {
  if (MOCK) return 'mock-session'
  try {
    const saved = sessionStorage.getItem(SESSION_KEY)
    if (saved) return saved
  } catch {
    /* storage unavailable */
  }
  await ensureAuth()
  const { session_id } = await http<{ session_id: string }>('/api/sessions', { method: 'POST' })
  try {
    sessionStorage.setItem(SESSION_KEY, session_id)
  } catch {
    /* storage unavailable */
  }
  return session_id
}

// Forgets the session locally and asks the server to drop its tables now (fire and forget:
// the server also expires sessions on its own).
export function resetSession(): void {
  try {
    const saved = sessionStorage.getItem(SESSION_KEY)
    sessionStorage.removeItem(SESSION_KEY)
    if (saved && !MOCK) void fetch(`/api/sessions/${saved}`, withAuth({ method: 'DELETE', keepalive: true })).catch(() => {})
  } catch {
    /* storage unavailable */
  }
}

const fixture = async <T>(name: string, delayMs = 500): Promise<T> => {
  const mod = await import(`./fixtures/${name}.json`)
  await new Promise((r) => setTimeout(r, delayMs))
  return mod.default as T
}

export function uploadFiles(sessionId: string, files: File[], onProgress?: (fraction: number) => void): Promise<Catalog> {
  if (MOCK) return fixture<Catalog>('catalog', 900)
  // XHR rather than fetch: fetch cannot report upload progress.
  return new Promise((resolve, reject) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/sessions/${sessionId}/files`)
    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.onerror = () => reject(new ApiError(0, 'Upload failed before reaching the server.', 'Check your connection and try again.'))
    xhr.onload = () => {
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        /* non-JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(body as Catalog)
      const err = (body ?? {}) as Partial<ErrorResponse>
      reject(new ApiError(xhr.status, err.message ?? 'The upload was rejected.', err.next_step ?? 'Check the file and try again.'))
    }
    xhr.send(form)
  })
}

export const loadSample = (sessionId: string) =>
  MOCK ? fixture<Catalog>('catalog', 900) : http<Catalog>(`/api/sessions/${sessionId}/sample`, { method: 'POST' })

export const getCatalog = (sessionId: string) =>
  MOCK ? fixture<Catalog>('catalog', 100) : http<Catalog>(`/api/sessions/${sessionId}/catalog`)

export const setLinkStatus = (sessionId: string, linkId: string, status: 'active' | 'rejected') =>
  MOCK
    ? fixture<Catalog>('catalog', 200)
    : http<Catalog>(`/api/sessions/${sessionId}/links/${encodeURIComponent(linkId)}`, json('PATCH', { status }))

export const saveGlossary = (sessionId: string, glossary: Metric[]) =>
  MOCK ? fixture<Catalog>('catalog', 200) : http<Catalog>(`/api/sessions/${sessionId}/glossary`, json('PUT', glossary))

// The first rows of one uploaded table, for the analyst's own eyes. The server builds no prompt
// from them. In mock mode a fixture answer's table stands in.
export const previewTable = (sessionId: string, tableName: string, limit = 50) =>
  MOCK
    ? fixture<Answer>('answer_bar', 300).then((answer) => answer.table as ResultTable)
    : http<ResultTable>(`/api/sessions/${sessionId}/tables/${encodeURIComponent(tableName)}/preview?limit=${limit}`)

// The no-AI half: computed by templates on the server, instant, works while models are busy.
export const getDashboard = (sessionId: string) =>
  MOCK ? fixture<Dashboard>('dashboard', 600) : http<Dashboard>(`/api/sessions/${sessionId}/dashboard`)

export const getAnalyses = (sessionId: string) =>
  MOCK ? fixture<AnalysisCatalog>('analyses', 200) : http<AnalysisCatalog>(`/api/sessions/${sessionId}/analyses`)

export const runAnalysis = (sessionId: string, request: AnalysisRequest) =>
  MOCK ? fixture<InsightTile>('tile', 500) : http<InsightTile>(`/api/sessions/${sessionId}/analyses/run`, json('POST', request))

export const getEvalReport = () => (MOCK ? fixture<EvalReport>('eval_report', 300) : http<EvalReport>('/api/eval/report'))

const MOCK_ANSWERS: [RegExp, string][] = [
  [/salary/i, 'answer_clarify'],
  [/churn|customer/i, 'answer_refusal'],
  [/attrition/i, 'answer_kpi'],
  [/month|trend/i, 'answer_line'],
]

async function mockAsk(req: AskRequest, onStep: (s: StepEvent) => void): Promise<Answer> {
  const steps = await fixture<StepEvent[]>('steps', 0)
  for (const step of steps) {
    await new Promise((r) => setTimeout(r, 350))
    onStep(step)
  }
  const name = req.clarification ? 'answer_bar' : (MOCK_ANSWERS.find(([re]) => re.test(req.question))?.[1] ?? 'answer_bar')
  const answer = await fixture<Answer>(name, 200)
  return { ...answer, id: crypto.randomUUID(), question: req.question }
}

// Streams pipeline steps, resolves with the final answer. The server sends Server-Sent Events
// on the POST response: "event: step|answer|error" + "data: <json>", blank-line separated,
// with ": ping" comment lines as heartbeats.
export async function ask(sessionId: string, req: AskRequest, onStep: (s: StepEvent) => void, signal?: AbortSignal): Promise<Answer> {
  if (MOCK) return mockAsk(req, onStep)
  let res: Response
  try {
    res = await fetch(`/api/sessions/${sessionId}/ask`, withAuth({ ...json('POST', req), signal }))
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, 'Could not reach the server.', 'Check your connection and try again.')
  }
  if (!res.ok || !res.body) throw await toApiError(res)

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let cut: number
    while ((cut = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, cut)
      buffer = buffer.slice(cut + 2)
      const event = /^event: (.+)$/m.exec(block)?.[1]
      const data = /^data: (.+)$/m.exec(block)?.[1]
      if (!event || !data) continue // heartbeat
      const payload = JSON.parse(data)
      if (event === 'step') onStep(payload as StepEvent)
      else if (event === 'answer') return payload as Answer
      else if (event === 'error') throw new ApiError(500, payload.message, payload.next_step)
    }
  }
  throw new ApiError(0, 'The connection closed before the answer arrived.', 'Ask the question again.')
}


// ---- Accounts API (docs/DESIGN_SYSTEM.md section 9)
const MOCK_USER: User = { id: 'mock-user', kind: 'guest', name: 'Guest', email: null, role: null, created_at: '2026-09-21T00:00:00Z', onboarded: false }

/** Make sure there is a user. Silently becomes a guest when nobody is signed in. Against an older
 *  server without the accounts routes (a 404) the app carries on with no token. */
export async function ensureAuth(): Promise<User | null> {
  if (MOCK) return getStoredUser() ?? remember({ token: 'mock-token', user: MOCK_USER }).user
  const known = getStoredUser()
  if (getToken() && known) return known
  try {
    return remember(await http<AuthResponse>('/api/auth/guest', { method: 'POST' })).user
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null
    throw e
  }
}

export const signup = async (body: { email: string; password: string; name: string; role?: string | null }): Promise<User> =>
  MOCK
    ? remember({ token: 'mock-token', user: { ...MOCK_USER, kind: 'member', name: body.name, email: body.email, role: body.role ?? null } }).user
    : remember(await http<AuthResponse>('/api/auth/signup', json('POST', body))).user

export const login = async (body: { email: string; password: string }): Promise<User> =>
  MOCK
    ? remember({ token: 'mock-token', user: { ...MOCK_USER, kind: 'member', name: body.email.split('@')[0], email: body.email } }).user
    : remember(await http<AuthResponse>('/api/auth/login', json('POST', body))).user

export const getMe = (): Promise<MeResponse> =>
  MOCK
    ? Promise.resolve({ user: getStoredUser() ?? MOCK_USER, usage: { asks_this_hour: 6, asks_per_hour: 40, asks_today: 21, asks_per_day: 200 } })
    : http<MeResponse>('/api/auth/me')

export async function updateProfile(body: { name?: string; role?: string | null; onboarded?: boolean }): Promise<User> {
  const user = MOCK ? ({ ...(getStoredUser() ?? MOCK_USER), ...body } as User) : await http<User>('/api/auth/me', json('PATCH', body))
  write(USER_KEY, JSON.stringify(user))
  return user
}

/** Forget this browser's sign-in. Projects stay in the browser under the user's id. */
export async function logout(): Promise<void> {
  if (!MOCK) await http<unknown>('/api/auth/logout', { method: 'POST' }).catch(() => undefined)
  write(TOKEN_KEY, null)
  write(USER_KEY, null)
  resetSession()
}

export async function deleteAccount(): Promise<void> {
  if (!MOCK) await fetch('/api/auth/me', withAuth({ method: 'DELETE' }))
  write(TOKEN_KEY, null)
  write(USER_KEY, null)
  resetSession()
}
