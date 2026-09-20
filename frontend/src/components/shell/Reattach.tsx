// Coming back to a project whose files the server has forgotten (§6). Everything already asked is
// still readable; this is how the analyst gets back to asking. The promise and the inconvenience
// are the same sentence on purpose: we never keep your files, so you have to hand them over again.
//
// The sample project is one press, because that is the project an evaluator will come back to.

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
    <div className="space-y-4">
      <Banner
        tone="warn"
        nextStep="Everything you have already asked stays here."
        action={project.isSample && !busy ? <Button variant="action" onClick={onSample}>Reload the sample company</Button> : undefined}
      >
        Your files are no longer loaded. DarwinLens never keeps them on its server.
      </Banner>

      {busy ? (
        <UploadProgress busy={busy} />
      ) : (
        !project.isSample && (
          <div className="rounded-xxl border border-hairline-soft p-5 sm:p-6">
            <p className="text-body-sm text-slate">This project was built from these files:</p>
            <ul className="mt-3 flex flex-wrap gap-2">
              {project.fileNames.map((name) => (
                <li key={name}>
                  <Chip static>{name}</Chip>
                </li>
              ))}
            </ul>
            <DropZone compact label="Re-attach files" onFiles={onFiles} className="mt-4" />
          </div>
        )
      )}
    </div>
  )
}
