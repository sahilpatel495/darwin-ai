// "View table and SQL" behind a tile's menu (§13): the exact rows, and the query that produced
// them. Nothing on the automatic dashboard is written by a model, and this is where an analyst
// checks that for themselves before quoting a figure.

import DataTable from '../charts/DataTable'
import { Button, Dialog, toast } from '../ui'
import { humanize } from '../../lib/format'
import type { InsightTile } from '../../types'

interface TileDataDialogProps {
  tile: InsightTile
  open: boolean
  onClose: () => void
}

/** "employees", "salary register and reviews" — the files read, as a sentence, never a list. */
function sentenceList(items: string[]): string {
  if (items.length <= 1) return items[0] ?? ''
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}

export default function TileDataDialog({ tile, open, onClose }: TileDataDialogProps) {
  if (!tile.table) return null

  // The Clipboard API is missing on http and in some embedded browsers, and it rejects when the
  // page is not focused — so the failure says what to do instead rather than nothing at all.
  const copySql = () => {
    navigator.clipboard
      ?.writeText(tile.sql)
      .then(() => toast('Query copied'))
      .catch(() => toast('Could not copy the query. Select it and copy it with your keyboard.', 'error'))
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="xl"
      title={tile.title}
      description={tile.tables_used.length > 0 ? `Read from ${sentenceList(tile.tables_used.map(humanize))}.` : undefined}
      footer={<Button onClick={onClose}>Close</Button>}
    >
      <p className="measure text-body-md text-ink">{tile.statement}</p>
      <div className="mt-5">
        <DataTable table={tile.table} caption={tile.title} />
      </div>
      {tile.sql && (
        <div className="mt-8">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-subtitle-lg text-ink-deep">The query that computed this</h3>
            <Button size="sm" onClick={copySql}>
              Copy query
            </Button>
          </div>
          {/* Mono is for SQL and nothing else (§3). */}
          <pre className="mt-3 overflow-x-auto rounded-xl bg-surface-soft p-4 text-code text-ink">{tile.sql}</pre>
        </div>
      )}
    </Dialog>
  )
}
