// Projects live in this browser and nowhere else (§7). The server keeps no record of them, by
// design: it holds the files in memory for two hours and forgets them.
//
// Every read and write is wrapped, because localStorage throws in more situations than people
// expect: Safari private mode, a blocked third-party frame, a full quota. When it throws, the app
// keeps working and simply forgets — so nothing in here is allowed to be load-bearing.
//
// ponytail: localStorage, ~5 MB. Move to IndexedDB if a project needs more than 60 turns.

import { useCallback, useState } from 'react'
import type { Answer, Catalog, Metric } from '../types'

const KEY = 'verity.projects.v1'
const MAX_TURNS = 60
const MAX_TABLE_ROWS = 200

export interface Turn {
  id: string
  question: string
  answer: Answer
  askedAt: string
}

export interface ProjectRecord {
  id: string
  name: string
  createdAt: string
  lastOpenedAt: string
  isSample: boolean
  /** What to re-attach when the files are no longer loaded. */
  fileNames: string[]
  /** The server session holding the files. Null once it has expired. */
  sessionId: string | null
  /** Only when the analyst edited it; re-applied on re-attach. */
  glossary: Metric[] | null
  removedLinkIds: string[]
  /** Newest last, at most MAX_TURNS. */
  turns: Turn[]
  /** Order is the board's order. */
  savedAnswerIds: string[]
  tourDone?: boolean
}

// --- Pure helpers (tested in projects.test.mjs) ------------------------------------------------

/**
 * A stored answer is a receipt, not a copy of the data. 200 rows is enough to re-read the result
 * and re-download most of it; the model payloads after the first are the same prompt again with
 * one more message, and together they are what actually fills the quota.
 */
export function trimAnswer(answer: Answer): Answer {
  const table =
    answer.table && answer.table.rows.length > MAX_TABLE_ROWS
      ? {
          ...answer.table,
          rows: answer.table.rows.slice(0, MAX_TABLE_ROWS),
          display: answer.table.display.slice(0, MAX_TABLE_ROWS),
          truncated: true,
        }
      : answer.table
  const payloads = answer.work.payloads.map((payload, i) => (i === 0 ? payload : { ...payload, messages: [] }))
  return { ...answer, table, work: { ...answer.work, payloads } }
}

/** Newest turns win: a project that has run for an hour keeps its last hour. */
export function trimTurns(turns: Turn[]): Turn[] {
  return turns.slice(-MAX_TURNS).map((turn) => ({ ...turn, answer: trimAnswer(turn.answer) }))
}

/**
 * Frees space after a quota error by dropping the oldest half of the biggest project's turns.
 * Returns null when no project has a turn left to drop, so the caller stops trying.
 */
export function shrink(list: ProjectRecord[]): ProjectRecord[] | null {
  let biggest = -1
  let size = 0
  list.forEach((project, i) => {
    const length = JSON.stringify(project).length
    if (project.turns.length > 0 && length > size) {
      size = length
      biggest = i
    }
  })
  if (biggest < 0) return null
  const turns = list[biggest].turns
  return list.map((project, i) => (i === biggest ? { ...project, turns: turns.slice(Math.ceil(turns.length / 2)) } : project))
}

/** §6.2: the project is named after its first file, the way the analyst would say it out loud. */
export function projectName(fileNames: string[], isSample = false): string {
  if (isSample) return 'Sample HR company'
  const first = fileNames[0]
  if (!first) return 'Untitled project'
  const base = first.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim() || first
  const rest = fileNames.length - 1
  return rest > 0 ? `${base} and ${rest} more` : base
}

/** "12 questions, 3 saved" — what the row says about a project without opening it. */
export function projectSummary(record: Pick<ProjectRecord, 'turns' | 'savedAnswerIds'>): string {
  const questions = record.turns.length
  if (questions === 0) return 'No questions yet'
  const asked = `${questions} ${questions === 1 ? 'question' : 'questions'}`
  return record.savedAnswerIds.length > 0 ? `${asked}, ${record.savedAnswerIds.length} saved` : asked
}

/** "Opened today" / "Opened yesterday" / "Opened on 12 September". */
export function lastOpened(iso: string, now = new Date()): string {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return 'Opened earlier'
  const days = Math.round((startOfDay(now) - startOfDay(then)) / 86_400_000)
  if (days <= 0) return 'Opened today'
  if (days === 1) return 'Opened yesterday'
  const sameYear = then.getFullYear() === now.getFullYear()
  return `Opened on ${then.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', ...(sameYear ? {} : { year: 'numeric' }) })}`
}

const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()

/** The files the analyst actually gave us. Combined views are ours, not theirs, so they are left out. */
export function fileNamesFrom(catalog: Catalog): string[] {
  return [...new Set(catalog.tables.filter((table) => !table.is_view).map((table) => table.source_file))]
}

// --- Storage ------------------------------------------------------------------------------------

/** Anything that is not a list of things with an id and a turns array is not ours. */
function isRecord(value: unknown): value is ProjectRecord {
  const record = value as ProjectRecord
  return !!record && typeof record.id === 'string' && typeof record.name === 'string' && Array.isArray(record.turns)
}

function readAll(): ProjectRecord[] {
  try {
    const raw = localStorage.getItem(KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter(isRecord) : []
  } catch {
    return [] // storage unavailable, or someone else's data under our key
  }
}

function writeAll(list: ProjectRecord[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(list))
    return
  } catch {
    /* quota exceeded, or storage unavailable */
  }
  const smaller = shrink(list)
  if (!smaller) return
  try {
    localStorage.setItem(KEY, JSON.stringify(smaller))
  } catch {
    /* one retry is enough: the app works without history */
  }
}

/** Newest first, which is the order a person looks for their work in. */
export function listProjects(): ProjectRecord[] {
  return readAll().sort((a, b) => b.lastOpenedAt.localeCompare(a.lastOpenedAt))
}

export function getProject(id: string): ProjectRecord | null {
  return readAll().find((project) => project.id === id) ?? null
}

// crypto.randomUUID needs a secure context; the fallback keeps a plain-http demo working.
const newId = (): string =>
  typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `p-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`

export function createProject(input: { name: string; isSample: boolean; fileNames: string[]; sessionId: string }): ProjectRecord {
  const now = new Date().toISOString()
  const record: ProjectRecord = {
    id: newId(),
    name: input.name,
    createdAt: now,
    lastOpenedAt: now,
    isSample: input.isSample,
    fileNames: input.fileNames,
    sessionId: input.sessionId,
    glossary: null,
    removedLinkIds: [],
    turns: [],
    savedAnswerIds: [],
  }
  writeAll([record, ...readAll()])
  return record
}

/** Returns the saved record, so callers render exactly what is stored rather than what they sent. */
export function updateProject(id: string, patch: Partial<ProjectRecord>): ProjectRecord | null {
  const list = readAll()
  const index = list.findIndex((project) => project.id === id)
  if (index < 0) return null
  const next: ProjectRecord = { ...list[index], ...patch }
  if (patch.turns) next.turns = trimTurns(patch.turns)
  list[index] = next
  writeAll(list)
  return next
}

export function deleteProject(id: string): void {
  writeAll(readAll().filter((project) => project.id !== id))
}

/**
 * The record for one project, and a way to change it.
 *
 * Read once per mount — every screen that uses this is keyed by the project id, so a different
 * project is a different component. Changes are applied here and written through: storage is
 * best-effort, so a browser with it switched off still runs the whole product for one sitting and
 * simply forgets afterwards.
 *
 * `fallback` is the record of a project created moments ago, for exactly that case: it was never
 * stored, so nothing would be found to open.
 */
export function useProject(id: string, fallback?: ProjectRecord | null): [ProjectRecord | null, (patch: Partial<ProjectRecord>) => void] {
  const [record, setRecord] = useState<ProjectRecord | null>(() => getProject(id) ?? (fallback?.id === id ? fallback : null))

  const update = useCallback(
    (patch: Partial<ProjectRecord>) =>
      setRecord((current) => {
        if (!current) return current
        // The stored record wins when there is one, so the screen shows what a reload would show
        // (turns past 60 are already gone). Without storage, the merge keeps the sitting working.
        return updateProject(id, patch) ?? { ...current, ...patch }
      }),
    [id],
  )

  return [record, update]
}
