// The third onboarding step's script, written from the catalog the server just produced (§7).
//
// This is the education. Instead of a paragraph claiming DarwinLens cleans files and hides
// personal data, the analyst watches it say what it did to *their* files, with their counts:
// "3 title rows skipped, 1 total row dropped", "2 columns kept away from the AI". A claim they
// can check against the Data drawer thirty seconds later is worth more than any amount of prose.
//
// Every number here comes out of the catalog. Nothing is estimated and nothing is rounded up —
// if a file needed no cleaning, the line says so rather than inventing work.
//
// Pure and import-free at runtime, so reading.test.mjs runs it in Node.

import type { Catalog } from '../../types'
import type { GlyphName } from '../graphics/Glyph'

export interface ReadingStage {
  id: 'read' | 'clean' | 'links' | 'combined' | 'hidden'
  /** What happened, as a finished action. */
  label: string
  /** The counts behind it, in one line. Never empty. */
  detail: string
  glyph: GlyphName
}

const plural = (n: number, one: string, many = `${one}s`): string => `${n} ${n === 1 ? one : many}`

/** "a, b and c" — an Oxford-less list, because these are read aloud as a sentence. */
function sentenceList(parts: string[]): string {
  if (parts.length <= 1) return parts[0] ?? ''
  return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`
}

/** The label an analyst gave a column, falling back to the raw name for a column we cannot find. */
function columnLabel(catalog: Catalog, tableName: string, column: string): string {
  const table = catalog.tables.find((t) => t.name === tableName)
  return table?.columns.find((c) => c.name === column)?.label ?? column
}

/**
 * Four to five ticks, always in this order and always all present: a stage with nothing to report
 * says so. Dropping the empty ones would make the sequence a different length for every upload,
 * which is exactly the kind of jump that makes a progress animation feel broken.
 */
export function readingStages(catalog: Catalog): ReadingStage[] {
  // A combined view is not a file the analyst brought; counting it would report more files than
  // they dropped in.
  const files = catalog.tables.filter((t) => !t.is_view)
  const rows = files.reduce((sum, t) => sum + t.row_count, 0)

  const titleRows = files.reduce((sum, t) => sum + t.health.skipped_title_rows, 0)
  const totalRows = files.reduce((sum, t) => sum + t.health.dropped_total_rows, 0)
  const duplicates = files.reduce((sum, t) => sum + (t.health.duplicates_removed ? t.health.duplicate_rows : 0), 0)
  const converted = files.reduce((sum, t) => sum + t.health.coercions.length, 0)

  const cleaned: string[] = []
  if (titleRows) cleaned.push(`${plural(titleRows, 'title row')} skipped`)
  if (totalRows) cleaned.push(`${plural(totalRows, 'total row')} dropped`)
  if (duplicates) cleaned.push(`${plural(duplicates, 'repeated row')} removed`)
  if (converted) cleaned.push(`${plural(converted, 'column')} of ₹ amounts and dates read properly`)

  const links = catalog.relationships.filter((r) => r.status === 'active')
  const unions = catalog.unions.filter((u) => u.status === 'active')
  const combinedFiles = unions.reduce((sum, u) => sum + u.tables.length, 0)

  // A column is hidden once, however many files it appears in.
  const hidden = [...new Set(files.flatMap((t) => t.health.pii_columns.map((c) => columnLabel(catalog, t.name, c))))]

  return [
    {
      id: 'read',
      label: 'Read your files',
      detail: `${plural(files.length, 'file')}, ${rows.toLocaleString('en-IN')} rows`,
      glyph: 'table',
    },
    {
      id: 'clean',
      label: 'Cleaned them as they were read',
      detail: cleaned.length ? sentenceList(cleaned) : 'Nothing needed fixing',
      glyph: 'sparkles',
    },
    {
      id: 'links',
      label: 'Found the links between them',
      detail: links.length
        ? `${plural(links.length, 'link')}, so one question can cover more than one file`
        : 'No shared columns, so each file answers on its own',
      glyph: 'link',
    },
    {
      id: 'combined',
      label: 'Combined the files that match',
      detail: combinedFiles
        ? `${plural(combinedFiles, 'file')} stacked into ${plural(unions.length, 'view')} you can ask about at once`
        : 'None of your files held the same kind of rows',
      glyph: 'compare',
    },
    {
      id: 'hidden',
      label: 'Hid personal data from the AI',
      detail: hidden.length
        ? `${plural(hidden.length, 'column')} kept back: ${sentenceList(hidden)}`
        : 'No personal-data columns were found in these files',
      glyph: 'lock',
    },
  ]
}

/** The three best first questions for the "ready" card. Fewer if the catalog offered fewer. */
export const firstQuestions = (catalog: Catalog): string[] => catalog.suggested_questions.slice(0, 3)
