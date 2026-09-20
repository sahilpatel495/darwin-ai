// Coming back to a project whose files the server has forgotten (§6.6). The thread above is still
// readable; this is how the analyst gets back to asking. The promise and the inconvenience are the
// same sentence on purpose: we never keep your files, so you have to hand them over again.

import type { ProjectRecord } from '../../lib/projects'
import { Banner, Button, Chip } from '../ui'
import DropZone from '../upload/DropZone'
import UploadProgress from '../upload/UploadProgress'
import type { Busy } from '../upload/UploadProgress'

interface ReattachProps {
  project: ProjectRecord
  busy: Busy | null
  onFiles: (files: File[]) => void
  onSample: () => void
}

export default function Reattach({ project, busy, onFiles, onSample }: ReattachProps) {
  return (
    <div className="space-y-3">
      <Banner tone="warn" nextStep="Re-attach them to ask new questions. Everything you have already asked stays here.">
        Your files are no longer loaded. We never keep them on our server.
      </Banner>

      {busy ? (
        <UploadProgress busy={busy} />
      ) : project.isSample ? (
        <Button variant="primary" onClick={onSample}>
          Reload sample data
        </Button>
      ) : (
        <div>
          <p className="type-small text-ink-2">This project was built from these files:</p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {project.fileNames.map((name) => (
              <li key={name}>
                <Chip static>{name}</Chip>
              </li>
            ))}
          </ul>
          <DropZone compact label="Re-attach files" onFiles={onFiles} className="mt-3" />
        </div>
      )}
    </div>
  )
}
