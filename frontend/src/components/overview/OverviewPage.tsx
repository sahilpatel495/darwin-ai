// The automatic dashboard (§13). Every number on this page was computed by DuckDB from server
// templates: no model wrote a query, no model phrased a sentence, and it is the same page every
// time. That is worth saying once, quietly, under the title — and worth having, because it is the
// half of the product that still works when every free model is busy.

import { useEffect, useState } from 'react'
import { ApiError, getCatalog, getDashboard } from '../../api'
import { plainTile } from '../../lib/tables'
import type { Catalog, Dashboard, DashboardSection, InsightTile } from '../../types'
import { projectPath } from '../../lib/route'
import { isTileSaved, toggleSavedTile } from '../../lib/projects'
import type { ProjectRecord } from '../../lib/projects'
import TileCard from '../tiles/TileCard'
import { packTiles, SPAN_CLASS, TILE_GRID, tileSpan } from '../tiles/layout'
import { Banner, Button, Card, EmptyState, Skeleton, toast } from '../ui'

export interface OverviewPageProps {
  /** null = the files are no longer loaded; nothing can be computed until they are re-attached. */
  sessionId: string | null
  project: ProjectRecord
  /** Sends a question to the Ask page and goes there. */
  onAsk: (question: string) => void
  /** Saves a tile to the board; App writes the record and hands it back as `project`. */
  onProjectChange: (next: ProjectRecord) => void
}

/** Every tile's prose in the analyst's words, done once here so a saved tile prints that way too. */
const inFileNames = (dashboard: Dashboard, catalog: Catalog | null): Dashboard =>
  catalog
    ? { ...dashboard, sections: dashboard.sections.map((section) => ({ ...section, tiles: section.tiles.map((tile) => plainTile(tile, catalog.tables)) })) }
    : dashboard

export default function OverviewPage({ sessionId, project, onAsk, onProjectChange }: OverviewPageProps) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(sessionId !== null)
  const [reloads, setReloads] = useState(0)

  // The dashboard is derived from the catalog, so it is re-fetched whenever the project is opened
  // again (lastOpenedAt) — that is when links were kept or removed and definitions were edited.
  useEffect(() => {
    if (!sessionId) {
      setDashboard(null)
      setLoading(false)
      return
    }
    let live = true
    setLoading(true)
    setError(null)
    // The catalog rides along so every sentence on this page can say "Salary_Register_2025.xlsx"
    // where the server wrote `salary_register_2025_register` (§8). It is computed, cached and
    // free of AI, like the dashboard itself; if it fails the tiles still render, in SQL names.
    Promise.all([getDashboard(sessionId), getCatalog(sessionId).catch(() => null)])
      .then(([next, catalog]) => live && (setDashboard(inFileNames(next, catalog)), setLoading(false)))
      .catch((failure: unknown) => {
        if (!live) return
        setError(failure instanceof ApiError ? failure : new ApiError(0, 'The overview could not be computed.', 'Try again in a moment.'))
        setLoading(false)
      })
    return () => {
      live = false
    }
  }, [sessionId, project.lastOpenedAt, reloads])

  // The record is the only source of truth for what is on the board: App stores it and hands the
  // stored copy straight back, so the card's "Saved" mark cannot drift from the board.
  const toggleSaved = (tile: InsightTile) => {
    const wasSaved = isTileSaved(project, tile.id)
    onProjectChange(toggleSavedTile(project, tile))
    toast(wasSaved ? 'Removed from board' : 'Saved to board')
  }

  // A 404 means the server has forgotten the files, which is the same story as never having had
  // them (§6.6): the overview is computed live, so there is nothing to show read-only.
  const filesGone = sessionId === null || error?.status === 404
  const sections = dashboard?.sections.filter((section) => section.tiles.length > 0) ?? []

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="type-page text-ink">Overview</h1>
          <p className="mt-1 type-small text-ink-2">Computed from your files. No AI involved.</p>
        </div>
        {!filesGone && (
          <Button size="sm" loading={loading} onClick={() => setReloads((n) => n + 1)}>
            Refresh
          </Button>
        )}
      </header>

      {filesGone ? (
        <Banner
          tone="warn"
          className="mt-6"
          nextStep={
            <>
              Re-attach them on the <a href={projectPath(project.id)}>Ask page</a> and the overview comes back.
            </>
          }
        >
          Your files are no longer loaded. We never keep them.
        </Banner>
      ) : error ? (
        <Banner
          tone="error"
          className="mt-6"
          nextStep={error.nextStep}
          action={
            <Button variant="primary" size="sm" onClick={() => setReloads((n) => n + 1)}>
              Try again
            </Button>
          }
        >
          {error.message}
        </Banner>
      ) : loading && !dashboard ? (
        <LoadingGrid />
      ) : sections.length === 0 ? (
        <EmptyState
          className="mt-6"
          title="Nothing to summarise yet"
          action={
            <Button variant="primary" onClick={() => onAsk('What is in these files?')}>
              Ask a question instead
            </Button>
          }
        >
          These files have no columns the overview knows how to summarise on its own.
        </EmptyState>
      ) : (
        <div className="mt-6 space-y-8">
          {sections.map((section) => (
            <Section
              key={section.title}
              section={section}
              onAsk={onAsk}
              isSaved={(id) => isTileSaved(project, id)}
              onToggleSaved={toggleSaved}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function Section({
  section,
  onAsk,
  isSaved,
  onToggleSaved,
}: {
  section: DashboardSection
  onAsk: (question: string) => void
  isSaved: (tileId: string) => boolean
  onToggleSaved: (tile: InsightTile) => void
}) {
  return (
    <section>
      <h2 className="type-section text-ink">{section.title}</h2>
      {section.description && <p className="mt-0.5 measure type-small text-ink-2">{section.description}</p>}
      {/* The tiles rise in 40 ms apart, once, when the computed dashboard lands (§4). */}
      <div className={`${TILE_GRID} stagger-children mt-4`}>
        {packTiles(section.tiles).map((tile) => (
          <div key={tile.id} className={SPAN_CLASS[tileSpan(tile)]}>
            <TileCard tile={tile} onAsk={onAsk} saved={isSaved(tile.id)} onToggleSaved={() => onToggleSaved(tile)} />
          </div>
        ))}
      </div>
    </section>
  )
}

/** The shape of what is coming: four figures, then two charts. Announced once, in words. */
function LoadingGrid() {
  return (
    <div role="status" aria-live="polite" className="mt-6">
      <p className="sr-only">Computing your overview from your files.</p>
      <div className={TILE_GRID}>
        {[0, 1, 2, 3].map((i) => (
          <Card key={`kpi-${i}`} className={SPAN_CLASS.kpi}>
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-4 h-9 w-28" />
          </Card>
        ))}
        {[0, 1].map((i) => (
          <Card key={`chart-${i}`} className={SPAN_CLASS.half}>
            <Skeleton className="h-5 w-44" />
            <Skeleton className="mt-2 h-3 w-full max-w-64" />
            <Skeleton className="mt-5 h-44 w-full" />
          </Card>
        ))}
      </div>
    </div>
  )
}
