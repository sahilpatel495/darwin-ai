// Projects live in this browser and nowhere else (§7). The server keeps no record of them, by
// design: it holds the files in memory for two hours and forgets them.
//
// Every read and write is wrapped, because localStorage throws in more situations than people
// expect: Safari private mode, a blocked third-party frame, a full quota. When it throws, the app
// keeps working and simply forgets — so nothing in here is allowed to be load-bearing.
//
// ponytail: localStorage, ~5 MB. Move to IndexedDB if a project needs more than 60 turns.

import { useCallback, useState } from 'react'
import type { Answer, Catalog, InsightTile, Metric, ResultTable } from '../types'

/** One shelf of projects per person (§10), so signing in as somebody else shows their work and
 *  not yours. A guest is a person too: their id is what they keep when they sign up. */
const PREFIX = 'darwinlens.projects.v1'
/** Everything stored before there were accounts, and before the rename. Moved across once. */
const LEGACY_KEY = 'verity.projects.v1'
const MAX_TURNS = 60
const MAX_TABLE_ROWS = 200
/** A board of 24 tiles already prints to about eight pages. Past that it is a document, not a board. */
const MAX_SAVED_TILES = 24
/** Fired after every write, so the shell can re-read a record another screen has just changed. */
const CHANGED = 'darwinlens:projects-changed'

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
  /** Tiles kept from Overview and Analyses (§15). Order is the board's order, newest last. */
  savedTiles: InsightTile[]
  /** Hints already dismissed (§10). Replaces the tour, which is gone. */
  tipsSeen: string[]
}

// --- Pure helpers (tested in projects.test.mjs) ------------------------------------------------

/** Anything stored keeps at most 200 rows: enough to re-read the result and download most of it. */
function trimTable(table: ResultTable | null): ResultTable | null {
  if (!table || table.rows.length <= MAX_TABLE_ROWS) return table
  return { ...table, rows: table.rows.slice(0, MAX_TABLE_ROWS), display: table.display.slice(0, MAX_TABLE_ROWS), truncated: true }
}

/**
 * A stored answer is a receipt, not a copy of the data. The model payloads after the first are
 * the same prompt again with one more message, and together they are what fills the quota.
 */
export function trimAnswer(answer: Answer): Answer {
  const payloads = answer.work.payloads.map((payload, i) => (i === 0 ? payload : { ...payload, messages: [] }))
  return { ...answer, table: trimTable(answer.table), work: { ...answer.work, payloads } }
}

/** A saved tile is a receipt too: the same 200 rows, and nothing else to drop. */
export function trimTile(tile: InsightTile): InsightTile {
  return { ...tile, table: trimTable(tile.table) }
}

export function isTileSaved(project: Pick<ProjectRecord, 'savedTiles'>, tileId: string): boolean {
  return (project.savedTiles ?? []).some((tile) => tile.id === tileId)
}

/**
 * Save a tile to the board, or take it off again — the same control either way, so a tile card
 * needs one button and not two. Pure: the caller stores what comes back.
 */
export function toggleSavedTile(project: ProjectRecord, tile: InsightTile): ProjectRecord {
  const tiles = project.savedTiles ?? []
  if (isTileSaved(project, tile.id)) return { ...project, savedTiles: tiles.filter((saved) => saved.id !== tile.id) }
  // Past the cap the oldest tile goes, which is the one the analyst saved furthest from this thought.
  return { ...project, savedTiles: [...tiles, trimTile(tile)].slice(-MAX_SAVED_TILES) }
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

/** "12 questions, 3 saved" — what the card says about a project without opening it. */
export function projectSummary(record: Pick<ProjectRecord, 'turns' | 'savedAnswerIds' | 'savedTiles'>): string {
  const questions = record.turns.length
  // The board holds both kinds, so "saved" counts both: one number for one screen.
  const saved = record.savedAnswerIds.length + (record.savedTiles ?? []).length
  if (questions === 0) return saved > 0 ? `${saved} saved` : 'No questions yet'
  const asked = `${questions} ${questions === 1 ? 'question' : 'questions'}`
  return saved > 0 ? `${asked}, ${saved} saved` : asked
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

/**
 * Questions asked per day over the last `days` days, oldest first — the shape behind the sparkline
 * on a project card (§8). A flat line is the truth about a project nobody has opened, so it is not
 * hidden: the card says "no questions yet" beside it.
 */
export function activity(turns: readonly Turn[], days = 14, now = new Date()): number[] {
  const today = startOfDay(now)
  const counts = new Array<number>(days).fill(0)
  for (const turn of turns) {
    const asked = new Date(turn.askedAt).getTime()
    if (Number.isNaN(asked)) continue
    const ago = Math.round((today - startOfDay(new Date(asked))) / 86_400_000)
    if (ago >= 0 && ago < days) counts[days - 1 - ago] += 1
  }
  return counts
}

/** A hint dismissed, on the record where the next visit will find it (§10). Pure. */
export function withTipSeen(project: ProjectRecord, tipId: string): ProjectRecord {
  const seen = project.tipsSeen ?? []
  return seen.includes(tipId) ? project : { ...project, tipsSeen: [...seen, tipId] }
}

/** The files the analyst actually gave us. Combined views are ours, not theirs, so they are left out. */
export function fileNamesFrom(catalog: Catalog): string[] {
  return [...new Set(catalog.tables.filter((table) => !table.is_view).map((table) => table.source_file))]
}

// --- Storage ------------------------------------------------------------------------------------

/** Whose shelf we are reading. Null until the shell knows, and for a server with no accounts. */
let userId: string | null = null
const key = () => `${PREFIX}.${userId ?? 'local'}`

/**
 * Point every read and write at this person's shelf. Called by the shell as soon as it knows who
 * is here, and again whenever that changes.
 *
 * The first person to arrive inherits whatever this browser stored before there were accounts:
 * their projects are the ones that were on the screen a moment ago, and nobody else can claim
 * them. It happens once, because the old key is removed as it is read.
 *
 * It announces nothing on purpose: the shell calls this while it renders, before any screen has
 * read the shelf, and an event fired there would be a setState in the middle of a render. The
 * screens are keyed by the reader instead, so a different person is a different mount.
 */
export function scopeProjectsTo(nextUserId: string | null): void {
  if (nextUserId === userId) return
  userId = nextUserId
  try {
    if (localStorage.getItem(key()) === null) {
      const inherited = localStorage.getItem(LEGACY_KEY)
      if (inherited !== null) {
        localStorage.setItem(key(), inherited)
        localStorage.removeItem(LEGACY_KEY)
      }
    }
  } catch {
    /* storage unavailable: there is nothing to inherit and nowhere to put it */
  }
}

/** Anything that is not a list of things with an id and a turns array is not ours. */
function isRecord(value: unknown): value is ProjectRecord {
  const record = value as ProjectRecord
  return !!record && typeof record.id === 'string' && typeof record.name === 'string' && Array.isArray(record.turns)
}

function readAll(): ProjectRecord[] {
  try {
    const raw = localStorage.getItem(key())
    const parsed: unknown = raw ? JSON.parse(raw) : []
    // savedTiles and tipsSeen arrived after the records that are already on disk: a record stored
    // before them has neither, and every screen is allowed to read both without checking.
    return Array.isArray(parsed)
      ? parsed.filter(isRecord).map((record) => ({ ...record, savedTiles: record.savedTiles ?? [], tipsSeen: record.tipsSeen ?? [] }))
      : []
  } catch {
    return [] // storage unavailable, or someone else's data under our key
  }
}

/** Tell the shell a record changed: renaming in the header renames the project in the nav rail. */
function announce(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(CHANGED))
}

/** Subscribe to any write. Returns the unsubscribe, so an effect can just return it. */
export function onProjectsChanged(listener: () => void): () => void {
  window.addEventListener(CHANGED, listener)
  return () => window.removeEventListener(CHANGED, listener)
}

function writeAll(list: ProjectRecord[]): void {
  try {
    localStorage.setItem(key(), JSON.stringify(list))
    return
  } catch {
    /* quota exceeded, or storage unavailable */
  } finally {
    // Announced either way: the screen that asked for the change has already applied it in state,
    // and the others must show the same thing whether or not the disk took it.
    announce()
  }
  const smaller = shrink(list)
  if (!smaller) return
  try {
    localStorage.setItem(key(), JSON.stringify(smaller))
  } catch {
    /* one retry is enough: the app works without history */
  }
}

/** Newest first, which is the order a person looks for their work in. */
export function listProjects(): ProjectRecord[] {
  return readAll().sort((a, b) => b.lastOpenedAt.localeCompare(a.lastOpenedAt))
}

/** Everything this person has in this browser, gone. The server side is `deleteAccount()`. */
export function clearProjects(): void {
  writeAll([])
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
    savedTiles: [],
    tipsSeen: [],
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
  if (patch.savedTiles) next.savedTiles = patch.savedTiles.slice(-MAX_SAVED_TILES).map(trimTile)
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
    (patch: Partial<ProjectRecord>) => {
      // The write happens here and not inside the updater: a state updater must be pure, and this
      // one announced the change while React was rendering, which React reports as a setState in
      // the middle of another component's render. updateProject reads storage itself, so it needs
      // nothing from the current state.
      const stored = updateProject(id, patch)
      // The stored record wins when there is one, so the screen shows what a reload would show
      // (turns past 60 are already gone). Without storage, the merge keeps the sitting working.
      setRecord((current) => (current ? (stored ?? { ...current, ...patch }) : current))
    },
    [id],
  )

  return [record, update]
}
