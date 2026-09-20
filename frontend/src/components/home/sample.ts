// What "See what's inside" needs before it can list the sample files (§15), kept pure so
// sample.test.mjs can run it in Node.
//
// The reply is read defensively on purpose: this listing is the one call the app makes that
// api.ts does not own yet, and the endpoint may be missing entirely on an older server. Anything
// that is not a list of named files is treated as "not available", which the dialog says in a
// sentence rather than showing an empty list or a dead download link.

export interface SampleFile {
  name: string
  /** Bytes, or null when the server did not say. */
  size: number | null
  /** One line about what is in it. Empty when the server did not say. */
  description: string
}

export const SAMPLE_FILES_URL = '/api/sample/files'
export const SAMPLE_ZIP_URL = '/api/sample/download'
export const sampleFileUrl = (name: string) => `${SAMPLE_FILES_URL}/${encodeURIComponent(name)}`

const text = (value: unknown): string => (typeof value === 'string' ? value : '')
const bytes = (value: unknown): number | null => (typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null)

/** A bare array or `{ files: [...] }`, either way: both are obvious shapes for this endpoint. */
export function parseSampleFiles(body: unknown): SampleFile[] {
  const list = Array.isArray(body) ? body : Array.isArray((body as { files?: unknown })?.files) ? (body as { files: unknown[] }).files : []
  return list
    .map((item) => item as Record<string, unknown>)
    .filter((item) => item && text(item.name) !== '')
    .map((item) => ({ name: text(item.name), size: bytes(item.size_bytes ?? item.size ?? item.bytes), description: text(item.description ?? item.about) }))
}

/** "36 KB", "1.2 MB" — the size a person reads, in the units a file browser uses. */
export function fileSize(size: number | null): string {
  if (size === null) return ''
  if (size < 1024) return `${size} bytes`
  const kb = size / 1024
  if (kb < 1000) return `${Math.round(kb)} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}
