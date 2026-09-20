// Analyses: the guided, AI-free half of the product (§14). The analyst picks a kind, picks the
// columns, and the database computes it — the same templates the Overview runs, aimed by hand.
// No model is involved, so it is instant, identical every time, and it still works when every
// free model is rate limited.

import { useEffect, useMemo, useRef, useState } from 'react'
import { getAnalyses, runAnalysis } from '../../api'
import { csvFileName, downloadCsv, toCsv } from '../../lib/csv'
import { humanize } from '../../lib/format'
import { plainTile } from '../../lib/tables'
import { isTileSaved, toggleSavedTile } from '../../lib/projects'
import type { ProjectRecord } from '../../lib/projects'
import { go, projectPath } from '../../lib/route'
import type { AnalysisCatalog, AnalysisKind, InsightTile } from '../../types'
import TileCard from '../tiles/TileCard'
import TileDataDialog from '../tiles/TileDataDialog'
import { Banner, Button, Card, Chip, EmptyState, Skeleton, toast } from '../ui'
import type { Problem } from '../shell/problem'
import { problemFrom } from '../shell/problem'
import AnalysisForm from './AnalysisForm'
import { defaultOptions, previewSentence } from './form'
import KindIcon from './kindIcons'

export interface AnalysesPageProps {
  /** null = the files are no longer loaded; nothing can be run until they are re-attached. */
  sessionId: string | null
  project: ProjectRecord
  /** Sends a question to the Ask page and goes there. */
  onAsk: (question: string) => void
  /** Saves a tile to the board; App writes the record and hands it back as `project`. */
  onProjectChange: (next: ProjectRecord) => void
}

/** One run made in this visit: enough to put the result and the analyst's choices back. */
interface Run {
  id: string
  sentence: string
  tile: InsightTile
  kindKey: string
  inputs: Record<string, string>
  options: Record<string, string>
}

/**
 * Phones stack the gallery above the form, so choosing a kind has to bring the next step into
 * view. On desktop both columns are already on screen and scrolling would be noise.
 */
function revealOnPhone(node: HTMLElement | null): void {
  if (!node || typeof window === 'undefined' || window.matchMedia('(min-width: 1024px)').matches) return
  const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  node.scrollIntoView({ behavior: still ? 'auto' : 'smooth', block: 'start' })
}

export default function AnalysesPage({ sessionId, project, onAsk, onProjectChange }: AnalysesPageProps) {
  const [catalog, setCatalog] = useState<AnalysisCatalog | null>(null)
  const [loadProblem, setLoadProblem] = useState<Problem | null>(null)
  const [kindKey, setKindKey] = useState<string | null>(null)
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [options, setOptions] = useState<Record<string, string>>({})
  const [running, setRunning] = useState(false)
  const [runProblem, setRunProblem] = useState<Problem | null>(null)
  const [tile, setTile] = useState<InsightTile | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [dataOpen, setDataOpen] = useState(false)
  const formRef = useRef<HTMLDivElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!sessionId) return
    let live = true
    setLoadProblem(null)
    getAnalyses(sessionId)
      .then((next) => live && setCatalog(next))
      .catch((error) => live && setLoadProblem(problemFrom(error)))
    return () => {
      live = false
    }
  }, [sessionId])

  const kind = catalog?.kinds.find((k) => k.key === kindKey) ?? null

  // The words the analyst reads for every column, built once: "annual_ctc" is "Annual CTC".
  const labels = useMemo(
    () => Object.fromEntries((catalog?.columns ?? []).map((column) => [column.ref, humanize(column.label)])),
    [catalog],
  )
  const sentence = kind ? previewSentence(kind, inputs, options, labels) : ''

  // What a table is called in a caveat (§8). The analyses catalog already carries the file label
  // beside every column, so this needs no second request: "employees.ctc" gives the table name,
  // and `table_label` is what the analyst calls it.
  const named = useMemo(
    () =>
      [...new Map((catalog?.columns ?? []).map((column) => [column.ref.split('.')[0], column.table_label])).entries()].map(([name, label]) => ({
        name,
        source_file: label,
        sheet: null,
      })),
    [catalog],
  )

  const choose = (next: AnalysisKind) => {
    if (next.key !== kindKey) {
      // A result belongs to the analysis that produced it: leaving it under a different form
      // would invite the analyst to read it as the answer to the new one. The chips keep it.
      setTile(null)
      setDataOpen(false)
    }
    setKindKey(next.key)
    setInputs({})
    setOptions(defaultOptions(next))
    setRunProblem(null)
    revealOnPhone(formRef.current)
  }

  const run = async () => {
    if (!sessionId || !kind) return
    setRunning(true)
    setRunProblem(null)
    try {
      const result = plainTile(await runAnalysis(sessionId, { kind: kind.key, inputs, options }), named)
      setTile(result)
      // Same sentence run twice is one chip, moved to the front: the chips are a way back to a
      // result, not a log of clicks.
      setRuns((previous) => [
        { id: result.id + Date.now(), sentence, tile: result, kindKey: kind.key, inputs, options },
        ...previous.filter((item) => item.sentence !== sentence),
      ])
      revealOnPhone(resultRef.current)
    } catch (error) {
      setRunProblem(problemFrom(error))
      // The result on screen answered the choices as they were, not as they are now. Leaving it
      // under a refusal invites reading it as the answer to the question just asked; the chips
      // under it still put it back.
      setTile(null)
    } finally {
      setRunning(false)
    }
  }

  const reopen = (item: Run) => {
    setKindKey(item.kindKey)
    setInputs(item.inputs)
    setOptions(item.options)
    setTile(item.tile)
    setRunProblem(null)
  }

  const saved = Boolean(tile && isTileSaved(project, tile.id))
  const toggleSaved = () => {
    if (!tile) return
    onProjectChange(toggleSavedTile(project, tile))
    toast(saved ? 'Removed from the board' : 'Saved to board')
  }

  const download = () => {
    if (!tile?.table) return
    downloadCsv(csvFileName(sentence || tile.title), toCsv(tile.table.columns, tile.table.rows))
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="type-page text-ink">Analyses</h1>
      <p className="mt-1 measure type-small text-ink-2">No AI needed: you choose the columns, the database does the rest.</p>

      {!sessionId && (
        <Banner
          tone="warn"
          className="mt-5"
          nextStep="Re-attach them on the Ask page and this screen works again."
          action={
            <Button variant="primary" size="sm" onClick={() => go(projectPath(project.id))}>
              Go to Ask
            </Button>
          }
        >
          Your files are no longer loaded. We never keep them on our server.
        </Banner>
      )}

      {sessionId && loadProblem && (
        <Banner tone="error" className="mt-5" nextStep={loadProblem.nextStep}>
          {loadProblem.message}
        </Banner>
      )}

      {sessionId && !loadProblem && (
        <div className="mt-6 grid gap-6 lg:grid-cols-[20rem_minmax(0,1fr)]">
          <section aria-labelledby="analysis-kinds">
            <h2 id="analysis-kinds" className="type-section text-ink">
              Choose an analysis
            </h2>
            {catalog && catalog.kinds.length === 0 ? (
              <EmptyState className="mt-3">
                Nothing in these files can be measured or grouped yet, so there is no analysis to run.
              </EmptyState>
            ) : catalog ? (
              <ul className="stagger-children mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
                {catalog.kinds.map((item) => {
                  const active = item.key === kindKey
                  return (
                    <li key={item.key}>
                      <Card
                        as="button"
                        interactive
                        aria-pressed={active}
                        onClick={() => choose(item)}
                        className={active ? 'bg-blue-soft ring-1 ring-blue' : undefined}
                      >
                        <div className="flex gap-3">
                          <span
                            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-pill ${
                              active ? 'bg-blue text-white' : 'bg-blue-soft text-blue-ink'
                            }`}
                          >
                            <KindIcon kind={item.key} />
                          </span>
                          <div className="min-w-0">
                            <p className="type-section text-ink">{item.name}</p>
                            <p className="mt-0.5 type-small text-ink-2">{item.description}</p>
                            <p className="mt-1 type-small text-ink-2">e.g. {item.example}</p>
                          </div>
                        </div>
                      </Card>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
                {[0, 1, 2, 3].map((row) => (
                  <Card key={row}>
                    <Skeleton className="h-5 w-32" />
                    <Skeleton className="mt-2 h-4 w-full" />
                  </Card>
                ))}
              </div>
            )}
          </section>

          <div ref={formRef} className="min-w-0 scroll-mt-4">
            {kind && catalog ? (
              <AnalysisForm
                kind={kind}
                columns={catalog.columns}
                labels={labels}
                inputs={inputs}
                options={options}
                onInput={(key, ref) => setInputs((previous) => ({ ...previous, [key]: ref }))}
                onOption={(key, value) => setOptions((previous) => ({ ...previous, [key]: value }))}
                sentence={sentence}
                onRun={run}
                running={running}
                problem={runProblem}
              />
            ) : (
              <Card>
                <h2 className="type-card text-ink">Choose an analysis to start</h2>
                <p className="mt-1 measure type-body text-ink-2">
                  Every analysis here is a query this app writes itself, from the columns you choose. You see the sentence it
                  will run before you run it, and the SQL after.
                </p>
              </Card>
            )}

            <p role="status" className="sr-only">
              {running ? `Running ${sentence}` : tile ? `${tile.title} is ready` : ''}
            </p>

            <div ref={resultRef} className="scroll-mt-4">
              {running && (
                <Card className="mt-4">
                  <Skeleton className="h-6 w-56" />
                  <Skeleton className="mt-2 h-4 w-80 max-w-full" />
                  <Skeleton className="mt-4 h-56 w-full" />
                </Card>
              )}

              {!running && tile && (
                <div className="mt-4">
                  {/* compact: one result deserves its actions in the open, not folded into a menu. */}
                  <TileCard tile={tile} compact />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button variant="secondary" aria-pressed={saved} onClick={toggleSaved}>
                      {saved ? 'Saved' : 'Save to board'}
                    </Button>
                    {tile.table && tile.table.rows.length > 0 && (
                      <>
                        <Button variant="secondary" onClick={download}>
                          Download CSV
                        </Button>
                        <Button variant="secondary" onClick={() => setDataOpen(true)}>
                          View table and SQL
                        </Button>
                      </>
                    )}
                    {tile.ask && (
                      <Button variant="ghost" onClick={() => onAsk(tile.ask as string)}>
                        Continue in chat
                      </Button>
                    )}
                  </div>
                  {dataOpen && <TileDataDialog tile={tile} open={dataOpen} onClose={() => setDataOpen(false)} />}
                </div>
              )}
            </div>

            {runs.length > 0 && (
              <section aria-labelledby="analysis-runs" className="mt-6">
                <h2 id="analysis-runs" className="type-section text-ink">
                  Runs in this visit
                </h2>
                <div className="mt-2 flex flex-wrap gap-2">
                  {runs.map((item) => (
                    <Chip key={item.id} selected={item.tile === tile} onClick={() => reopen(item)}>
                      {item.sentence}
                    </Chip>
                  ))}
                </div>
              </section>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
