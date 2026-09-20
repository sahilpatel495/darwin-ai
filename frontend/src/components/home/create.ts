// Files (or the sample company) become a project. One function, because it happens from three
// places — Home, the landing's "Try the live demo", and the drop zone on an empty Home — and all
// three must produce exactly the same thing: a fresh session, a catalog read from it, and a record
// named after the files.

import { ensureSession, loadSample, resetSession, uploadFiles } from '../../api'
import { createProject, fileNamesFrom, projectName } from '../../lib/projects'
import type { ProjectRecord } from '../../lib/projects'
import type { Catalog } from '../../types'

export interface Created {
  project: ProjectRecord
  catalog: Catalog
}

/** Thrown when the files arrived but nothing readable came back. The caller says it in a sentence. */
export class NothingRead extends Error {}

async function create(load: (sessionId: string) => Promise<Catalog>, isSample: boolean): Promise<Created> {
  // ponytail: this tab holds one live session at a time (api.ts keeps a single id), so a new
  // project starts a fresh one and any other project's files are dropped with it.
  resetSession()
  const sessionId = await ensureSession()
  const catalog = await load(sessionId)
  if (!catalog?.tables?.length) throw new NothingRead()
  const fileNames = fileNamesFrom(catalog)
  return { project: createProject({ name: projectName(fileNames, isSample), isSample, fileNames, sessionId }), catalog }
}

export const createFromFiles = (files: File[], onProgress: (fraction: number) => void): Promise<Created> =>
  create((id) => uploadFiles(id, files, onProgress), false)

export const createFromSample = (): Promise<Created> => create(loadSample, true)
