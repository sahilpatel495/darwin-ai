// Drag-and-drop plus click-to-choose, used large on the landing page and compact in the sidebar.
// The real control is a native <input type="file">: the button opens it, so keyboard and screen
// reader users get the browser's own file picker. The input sits outside the clickable area so its
// own click event cannot bubble back and re-open the picker. While an upload runs the shell
// renders UploadProgress in this component's place, so there is no disabled state to manage.

import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { UploadIcon } from '../shell/icons'
import { ACCEPT_ATTRIBUTE } from './files'

interface DropZoneProps {
  onFiles: (files: File[]) => void
  /** Sidebar variant: one line, labelled "Add more files". */
  compact?: boolean
}

export default function DropZone({ onFiles, compact = false }: DropZoneProps) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length) onFiles([...e.dataTransfer.files])
  }

  const frame = dragging ? 'border-accent bg-accent-soft' : 'border-line bg-surface hover:border-accent'
  return (
    <>
      <div
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`cursor-pointer rounded-card border-2 border-dashed text-center transition-colors ${frame} ${compact ? 'p-3' : 'px-4 py-6 sm:px-6 sm:py-10'}`}
      >
        {!compact && (
          <div className="mb-3 flex justify-center text-accent">
            <UploadIcon />
          </div>
        )}
        {!compact && <p className="text-base font-medium text-ink">Drop your CSV or Excel files here</p>}
        {/* No onClick of its own: the click bubbles to the frame above, which opens the picker once. */}
        <button
          type="button"
          className={compact ? 'text-sm font-medium text-accent' : 'mt-4 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-ink'}
        >
          {compact ? 'Add more files' : 'Choose files'}
        </button>
        <p className={`text-ink-soft ${compact ? 'text-xs' : 'mt-3 text-sm'}`}>
          {compact ? 'or drop them here' : 'Several files at once is fine: .csv, .tsv, .xlsx or .xlsm.'}
        </p>
      </div>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPT_ATTRIBUTE}
        tabIndex={-1}
        aria-hidden
        className="sr-only"
        onChange={(e) => {
          if (e.target.files?.length) onFiles([...e.target.files])
          e.target.value = '' // so choosing the same file again still fires onChange
        }}
      />
    </>
  )
}
