// The automatic overview (§8). Every number on this page was computed by DuckDB from server
// templates: no model wrote a query, no model phrased a sentence, and it is the same page every
// time. That is worth saying once, in the badge beside the title — and worth having, because it
// is the half of the product that still works when every free model is busy.

import { useEffect, useState } from 'react'
import { ApiError, getCatalog, getDashboard } from '../../api'
import { plainTile } from '../../lib/tables'
import type { Catalog, Dashboard, DashboardSection, InsightTile, User } from '../../types'
import { projectPath, go } from '../../lib/route'
import { isTileSaved, toggleSavedTile } from '../../lib/projects'
import type { ProjectRecord } from '../../lib/projects'
import TileCard from '../tiles/TileCard'
import { SparkProvider } from '../tiles/Sparkline'
import { BENTO_GRID, CELL_CLASS, packBento, trendSeries } from '../tiles/layout'
import { Badge, Banner, Button, Card, EmptyState, PillTabs, Skeleton, toast } from '../ui'

export interface OverviewPageProps {
  /** null = the files are no longer loaded; nothing can be computed until they are re-attached. */
  sessionId: string | null
  project: ProjectRecord
  /** Sends a question to the Ask page and goes there. */
  onAsk: (question: string) => void
  /** Saves a tile to the board; App writes the record and hands it back as `project`. */
  onProjectChange: (next: ProjectRecord) => void
  /** Part of the shared page seam. This screen shows the same figures to everyone. */
  user?: User | null
  /** Part of the shared page seam: the Data drawer lives in the top bar. */
  onOpenData?: () => void
}

/** Every tile's prose in the analyst's words, done once here so a saved tile prints that way too. */
const inFileNames = (dashboard: Dashboard, catalog: Catalog | null): Dashboard =>
  catalog
    ? { ...dashboard, sections: dashboard.sections.map((section) => ({ ...section, tiles: section.tiles.map((tile) => plainTile(tile, catalog.tables)) })) }
    : dashboard

const sectionId = (title: string) => `section-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`

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
    // where the server wrote `salary_register_2025_register` (§12). It is computed, cached and
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
  // stored copy straight back, so the card's saved mark cannot drift from the board.
  const toggleSaved = (tile: InsightTile) => {
    const wasSaved = isTileSaved(project, tile.id)
    onProjectChange(toggleSavedTile(project, tile))
    toast(wasSaved ? 'Removed from the board' : 'Saved to the board')
  }

  const sections = dashboard?.sections.filter((section) => section.tiles.length > 0) ?? []

  return (
    <main className="mx-auto w-full max-w-[1120px] px-4 pb-20 sm:px-6">
      <header className="pt-8 sm:pt-12">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h1 className="text-heading-lg text-ink-deep">Overview</h1>
          <Badge tone="success">No AI involved</Badge>
        </div>
        <p className="mt-3 measure text-subtitle-md text-slate">
          Computed from your files the moment they landed, and the same every time you open it.
        </p>
      </header>

      {sessionId === null ? (
        // Expiry belongs to the shell (§6), which carries the banner and the way back. This page
        // says what is missing and points at the one place that can fix it.
        <EmptyState
          className="mt-10"
          glyph="upload"
          title="Nothing to compute yet"
          action={
            <Button variant="primary" onClick={() => go(projectPath(project.id))}>
              Re-attach your files
            </Button>
          }
        >
          Your files are not loaded, so there are no figures to show.
        </EmptyState>
      ) : error ? (
        // The server's own two sentences, whatever went wrong — this page never writes its own
        // version of them (§8). Only the button changes: asking again for files the server no
        // longer has would fail the same way, so a 404 points at the place they go back.
        <Banner
          tone="error"
          className="mt-8"
          nextStep={error.nextStep}
          action={
            error.status === 404 ? (
              <Button variant="primary" size="sm" onClick={() => go(projectPath(project.id))}>
                Re-attach your files
              </Button>
            ) : (
              <Button variant="primary" size="sm" onClick={() => setReloads((n) => n + 1)}>
                Try again
              </Button>
            )
          }
        >
          {error.message}
        </Banner>
      ) : loading && !dashboard ? (
        <LoadingBento />
      ) : sections.length === 0 ? (
        <EmptyState
          className="mt-10"
          glyph="sparkles"
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
        <>
          <SectionTabs sections={sections} loading={loading} onRefresh={() => setReloads((n) => n + 1)} />
          <div className="space-y-12">
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
        </>
      )}
    </main>
  )
}

/**
 * The sections as pills that stick under the top bar, lighting up as you scroll past them. They
 * are not links: the hash is the app's router, so a jump is a scroll, not a route.
 */
function SectionTabs({ sections, loading, onRefresh }: { sections: DashboardSection[]; loading: boolean; onRefresh: () => void }) {
  const [active, setActive] = useState(sectionId(sections[0]?.title ?? ''))
  const titles = sections.map((section) => section.title).join('|')

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const showing = entries.filter((entry) => entry.isIntersecting)
        if (showing.length === 0) return
        // The one nearest the top of the reading area is the one you are in.
        setActive(showing.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0].target.id)
      },
      // Below the top bar and its pills, and only the top 45% of the window counts: otherwise the
      // last section can never win, because it is never the topmost thing on screen.
      { rootMargin: '-140px 0px -55% 0px' },
    )
    for (const section of sections) {
      const node = document.getElementById(sectionId(section.title))
      if (node) observer.observe(node)
    }
    return () => observer.disconnect()
  }, [titles])

  const jump = (id: string) => {
    setActive(id)
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches
    document.getElementById(id)?.scrollIntoView({ behavior: still ? 'auto' : 'smooth', block: 'start' })
  }

  return (
    <div className="sticky top-16 z-20 -mx-4 mt-8 mb-6 flex items-center justify-between gap-3 bg-canvas/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
      {sections.length > 1 ? (
        <PillTabs
          label="Sections of this overview"
          size="sm"
          active={active}
          onChange={jump}
          tabs={sections.map((section) => ({ id: sectionId(section.title), label: section.title }))}
        />
      ) : (
        <span />
      )}
      <Button variant="quiet" size="sm" loading={loading} onClick={onRefresh}>
        Refresh
      </Button>
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
  const spark = trendSeries(section.tiles)

  return (
    // scroll-mt clears the top bar and the sticky pills when a tab jumps here.
    <section id={sectionId(section.title)} aria-labelledby={`${sectionId(section.title)}-title`} className="scroll-mt-36">
      <h2 id={`${sectionId(section.title)}-title`} className="text-heading-sm text-ink-deep">
        {section.title}
      </h2>
      {section.description && <p className="mt-1 measure text-body-md text-slate">{section.description}</p>}

      {/* The tiles rise in 50 ms apart, once, when the computed dashboard lands (§4). */}
      <SparkProvider value={spark}>
        <div className={`${BENTO_GRID} stagger-children mt-5`}>
          {packBento(section.tiles)
            .flat()
            .map(({ tile, cols }) => (
              <div key={tile.id} className={CELL_CLASS[cols]}>
                <TileCard tile={tile} onAsk={onAsk} saved={isSaved(tile.id)} onToggleSaved={() => onToggleSaved(tile)} />
              </div>
            ))}
        </div>
      </SparkProvider>
    </section>
  )
}

/** The shape of what is coming: a wide figure, two charts, one full-width tile. Said once, in words. */
function LoadingBento() {
  return (
    <div role="status" aria-live="polite" className="mt-10">
      <p className="sr-only">Computing your overview from your files.</p>
      <div className={BENTO_GRID}>
        <Card className={CELL_CLASS[4]}>
          <Skeleton className="h-4 w-28" />
          <Skeleton className="mt-5 h-10 w-44" />
        </Card>
        {[0, 1].map((i) => (
          <Card key={`chart-${i}`} className={CELL_CLASS[2]}>
            <Skeleton className="h-6 w-44" />
            <Skeleton className="mt-3 h-3 w-full max-w-64" />
            <Skeleton className="mt-6 h-48 w-full" />
          </Card>
        ))}
        <Card className={CELL_CLASS[4]}>
          <Skeleton className="h-6 w-56" />
          <Skeleton className="mt-6 h-40 w-full" />
        </Card>
      </div>
    </div>
  )
}
