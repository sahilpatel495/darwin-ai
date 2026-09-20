// Analyses: the guided, AI-free half of the product (§8). The analyst picks a kind, fills in a
// sentence, and the database computes it — the same templates the Overview runs, aimed by hand.
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
import type { AnalysisCatalog, AnalysisKind, InsightTile, User } from '../../types'
import TileCard from '../tiles/TileCard'
import TileDataDialog from '../tiles/TileDataDialog'
import { Badge, Banner, Button, Card, Chip, EmptyState, Skeleton, cx, toast } from '../ui'
import type { Problem } from '../shell/problem'
import { problemFrom } from '../shell/problem'
import SentenceBuilder from './SentenceBuilder'
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
  /** Part of the shared page seam. Every analyst sees the same analyses. */
  user?: User | null
  /** Part of the shared page seam: the Data drawer lives in the top bar. */
  onOpenData?: () => void
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
 * Bring the next step into view after a choice that changed what is below the fold — and only
 * then: scrolling something the analyst is already looking at reads as the page twitching.
 */
function reveal(node: HTMLElement | null): void {
  if (!node || typeof window === 'undefined') return
  const box = node.getBoundingClientRect()
  if (box.top >= 80 && box.bottom <= window.innerHeight) return
  const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  node.scrollIntoView({ behavior: still ? 'auto' : 'smooth', block: 'start' })
}

export default function AnalysesPage({ sessionId, project, onAsk, onProjectChange }: AnalysesPageProps) {
  const [catalog, setCatalog] = useState<AnalysisCatalog | null>(null)
  const [loadProblem, setLoadProblem] = useState<Problem | null>(null)
  const [kindKey, setKindKey] = useState<string | null>(null)
  const [chosen, setChosen] = useState(false) // the analyst picked a kind, rather than it opening on one
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [options, setOptions] = useState<Record<string, string>>({})
  const [running, setRunning] = useState(false)
  const [runProblem, setRunProblem] = useState<Problem | null>(null)
  const [tile, setTile] = useState<InsightTile | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [dataOpen, setDataOpen] = useState(false)
  const builderRef = useRef<HTMLDivElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!sessionId) return
    let live = true
    setLoadProblem(null)
    getAnalyses(sessionId)
      .then((next) => {
        if (!live) return
        setCatalog(next)
        // The screen opens on the first analysis with its sentence already there: an empty card
        // saying "choose something" is a screen with nothing on it.
        const first = next.kinds[0]
        if (first) {
          setKindKey(first.key)
          setOptions(defaultOptions(first))
        }
      })
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
      // A result belongs to the analysis that produced it: leaving it under a different sentence
      // would invite the analyst to read it as the answer to the new one. The chips keep it.
      setTile(null)
      setDataOpen(false)
    }
    setKindKey(next.key)
    setChosen(true)
    setInputs({})
    setOptions(defaultOptions(next))
    setRunProblem(null)
    reveal(builderRef.current)
  }

  const run = async () => {
    if (!sessionId || !kind) return
    setRunning(true)
    setRunProblem(null)
    try {
      const result = plainTile(await runAnalysis(sessionId, { kind: kind.key, inputs, options }), named)
      setTile(result)
      // The same sentence run twice is one chip, moved to the front: the chips are a way back to
      // a result, not a log of clicks.
      setRuns((previous) => [
        { id: result.id + Date.now(), sentence, tile: result, kindKey: kind.key, inputs, options },
        ...previous.filter((item) => item.sentence !== sentence),
      ])
      reveal(resultRef.current)
    } catch (error) {
      setRunProblem(problemFrom(error))
      // The result on screen answered the choices as they were, not as they are now. Leaving it
      // under a refusal invites reading it as the answer to what was just asked; the chips under
      // it still put it back.
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
    toast(saved ? 'Removed from the board' : 'Saved to the board')
  }

  const download = () => {
    if (!tile?.table) return
    downloadCsv(csvFileName(sentence || tile.title), toCsv(tile.table.columns, tile.table.rows))
  }

  return (
    <main className="mx-auto w-full max-w-[1120px] px-4 pb-20 sm:px-6">
      <header className="pt-8 sm:pt-12">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h1 className="text-heading-lg text-ink-deep">Analyses</h1>
          <Badge tone="success">No AI needed</Badge>
        </div>
        <p className="mt-3 measure text-subtitle-md text-slate">
          Say what you want measured and the database works it out, the same way every time.
        </p>
      </header>

      {!sessionId ? (
        <EmptyState
          className="mt-10"
          glyph="upload"
          title="Nothing to analyse yet"
          action={
            <Button variant="primary" onClick={() => go(projectPath(project.id))}>
              Re-attach your files
            </Button>
          }
        >
          Your files are not loaded, so there are no columns to choose from.
        </EmptyState>
      ) : loadProblem ? (
        <Banner tone="error" className="mt-8" nextStep={loadProblem.nextStep}>
          {loadProblem.message}
        </Banner>
      ) : (
        <>
          <section aria-labelledby="analysis-kinds" className="mt-10">
            <h2 id="analysis-kinds" className="text-heading-sm text-ink-deep">
              Choose an analysis
            </h2>
            {catalog && catalog.kinds.length === 0 ? (
              <EmptyState className="mt-4" glyph="table">
                Nothing in these files can be measured or grouped yet, so there is no analysis to run.
              </EmptyState>
            ) : catalog ? (
              <ul className="stagger-children mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {catalog.kinds.map((item) => {
                  const active = item.key === kindKey
                  return (
                    <li key={item.key}>
                      <Card
                        as="button"
                        radius="xl"
                        interactive
                        aria-pressed={active}
                        onClick={() => choose(item)}
                        className={cx('h-full', active && 'border-primary bg-primary-soft')}
                      >
                        <div className="flex items-start gap-3">
                          <span
                            className={cx(
                              'flex size-10 shrink-0 items-center justify-center rounded-circle',
                              active ? 'bg-primary text-white' : 'bg-surface-soft text-primary-deep',
                            )}
                          >
                            <KindIcon kind={item.key} size={22} />
                          </span>
                          <div className="min-w-0">
                            <p className="text-subtitle-lg text-ink-deep">{item.name}</p>
                            <p className="mt-0.5 text-body-sm text-slate">{item.description}</p>
                            <p className="mt-1 text-body-sm text-steel">e.g. {item.example}</p>
                          </div>
                        </div>
                      </Card>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {[0, 1, 2, 3, 4, 5].map((row) => (
                  <Card key={row} radius="xl">
                    <Skeleton className="h-5 w-32" />
                    <Skeleton className="mt-3 h-4 w-full" />
                  </Card>
                ))}
              </div>
            )}
          </section>

          <div ref={builderRef} className="mt-10 scroll-mt-24">
            {kind && catalog && (
              <SentenceBuilder
                kind={kind}
                columns={catalog.columns}
                labels={labels}
                inputs={inputs}
                options={options}
                onInput={(key, ref) => setInputs((previous) => ({ ...previous, [key]: ref }))}
                onOption={(key, value) => setOptions((previous) => ({ ...previous, [key]: value }))}
                onRun={run}
                running={running}
                problem={runProblem}
                autoFocus={chosen}
              />
            )}
          </div>

          <p role="status" className="sr-only">
            {running ? `Running ${sentence}` : tile ? `${tile.title} is ready` : ''}
          </p>

          <div ref={resultRef} className="scroll-mt-24">
            {running && (
              <Card className="mt-6">
                <Skeleton className="h-7 w-64" />
                <Skeleton className="mt-3 h-4 w-80 max-w-full" />
                <Skeleton className="mt-6 h-56 w-full" />
              </Card>
            )}

            {!running && tile && (
              <div className="mt-6">
                {/* compact: one result deserves its actions in the open, not folded into a toolbar. */}
                <TileCard tile={tile} compact />
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button variant="primary" aria-pressed={saved} onClick={toggleSaved}>
                    {saved ? 'Saved to the board' : 'Save to the board'}
                  </Button>
                  {tile.table && tile.table.rows.length > 0 && (
                    <>
                      <Button variant="ghost" onClick={download}>
                        Download CSV
                      </Button>
                      <Button variant="ghost" onClick={() => setDataOpen(true)}>
                        Table and SQL
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
            <section aria-labelledby="analysis-runs" className="mt-12">
              <h2 id="analysis-runs" className="text-heading-sm text-ink-deep">
                Run in this visit
              </h2>
              <div className="mt-4 flex flex-wrap gap-2">
                {runs.map((item) => (
                  <Chip key={item.id} selected={item.tile === tile} onClick={() => reopen(item)}>
                    {item.sentence}
                  </Chip>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </main>
  )
}
