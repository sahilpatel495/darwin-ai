// Checks picked files before any byte is uploaded, so the analyst hears about a wrong file
// immediately and in plain words. This is a courtesy, not a security control: the server checks
// every upload again and is the authority. Pure and import-free so files.test.mjs runs in Node.

const ACCEPTED_EXTENSIONS = ['.csv', '.tsv', '.xlsx', '.xlsm']

/** Value for <input accept>, so the file picker greys out everything else. */
export const ACCEPT_ATTRIBUTE = ACCEPTED_EXTENSIONS.join(',')

// ponytail: mirrors the largest server cap (25 MB locally; the hosted demo allows 10 MB and the
// server says so itself). If the cap becomes configurable, serve it from the API instead.
export const MAX_FILE_BYTES = 25 * 1024 * 1024

// ponytail: mirrors MAX_FILES_PER_UPLOAD in backend/app/main.py. The server only refuses after
// every byte has arrived, so without this the analyst waits for an upload that was never going to
// be accepted. If the two drift, the server's own sentence still explains the refusal.
export const MAX_FILES_PER_UPLOAD = 10

/** Skipped files named one by one; any beyond this are counted in a single closing sentence. */
const MAX_SENTENCES = 5

export interface FileCheck<T> {
  accepted: T[]
  /** Plain sentences about the files that were not added: what happened, then what to do. */
  problems: string[]
}

/** Only the last extension counts, so "payroll.csv.exe" is judged as ".exe". */
function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot < 0 ? '' : name.slice(dot).toLowerCase()
}

function problemWith(file: { name: string; size: number }): string | null {
  const extension = extensionOf(file.name)
  if (extension === '.xls') return `${file.name} is in the old Excel format. Open it in Excel, save it as .xlsx, and add it again.`
  if (!ACCEPTED_EXTENSIONS.includes(extension)) return `${file.name} was skipped. Verity reads .csv, .tsv, .xlsx and .xlsm files.`
  if (file.size === 0) return `${file.name} is empty. Export it again and check it has rows.`
  if (file.size > MAX_FILE_BYTES) return `${file.name} is larger than 25 MB. Remove the sheets or columns you do not need and add it again.`
  return null
}

/** Splits a selection into files worth uploading and sentences about the rest. */
export function checkFiles<T extends { name: string; size: number }>(files: readonly T[]): FileCheck<T> {
  const result: FileCheck<T> = { accepted: [], problems: [] }
  for (const file of files) {
    const problem = problemWith(file)
    if (problem) result.problems.push(problem)
    else result.accepted.push(file)
  }
  // A dropped folder of scans must not become thirty identical lines that fill a phone screen.
  if (result.problems.length > MAX_SENTENCES) {
    const more = result.problems.splice(MAX_SENTENCES).length
    result.problems.push(`${more} more ${more === 1 ? 'file was' : 'files were'} skipped too. Verity reads .csv, .tsv, .xlsx and .xlsm files of up to 25 MB.`)
  }
  const leftOut = result.accepted.splice(MAX_FILES_PER_UPLOAD).length
  if (leftOut > 0) {
    const these = leftOut === 1 ? 'the last 1 was left out. Add it' : `the last ${leftOut} were left out. Add them`
    result.problems.push(`Only ${MAX_FILES_PER_UPLOAD} files can be added at a time, so ${these} once these have loaded.`)
  }
  return result
}

/**
 * True when an upload changed nothing. The server skips a file whose name and bytes it already
 * holds and answers with the catalog as it was, version included. Without this check, adding the
 * same file twice ends in silence and the analyst cannot tell whether the upload worked.
 */
export function nothingAdded(before: { version: number } | null, after: { version: number }): boolean {
  return before !== null && before.version === after.version
}
