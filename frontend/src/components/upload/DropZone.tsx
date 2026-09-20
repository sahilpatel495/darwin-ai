// Drag-and-drop plus click-to-choose, used large on the first screen and compact everywhere else.
// The real control is a native <input type="file">: the button opens it, so keyboard and screen
// reader users get the browser's own file picker. The input sits outside the clickable area so its
// own click event cannot bubble back and re-open the picker. While an upload runs the caller
// renders UploadProgress in this component's place, so there is no disabled state to manage.

import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { Button, cx } from '../ui'
import { ACCEPT_ATTRIBUTE } from './files'

interface DropZoneProps {
  onFiles: (files: File[]) => void
  /** One line instead of the full invitation: in a sidebar, or above the composer. */
  compact?: boolean
  /** The button's words, when "Choose files" is not what happens next. */
  label?: string
  className?: string
}

export default function DropZone({ onFiles, compact = false, label, className }: DropZoneProps) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length) onFiles([...e.dataTransfer.files])
  }

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
        className={cx(
          'cursor-pointer rounded-card border-2 border-dashed text-center transition-colors duration-100',
          dragging ? 'border-blue bg-blue-soft' : 'border-line bg-surface-2 hover:border-blue hover:bg-blue-soft/40',
          compact ? 'px-3 py-3' : 'px-4 py-8 sm:px-6',
          className,
        )}
      >
        {!compact && <p className="type-card text-ink">Drop your CSV or Excel files here</p>}
        {/* The keyboard control. No onClick of its own: the click bubbles to the frame above,
            which opens the picker once. */}
        <Button variant={compact ? 'ghost' : 'primary'} size={compact ? 'sm' : 'md'} className={compact ? '' : 'mt-4'}>
          {label ?? (compact ? 'Add more files' : 'Choose files')}
        </Button>
        <p className={cx('type-small text-ink-2', !compact && 'mt-3')}>
          {compact ? 'or drop them here' : 'Several files at once is fine: .csv, .tsv, .xlsx or .xlsm.'}
        </p>
      </div>
      {/* Hidden from the tab order and from screen readers: the button above is the control people
          reach, and it opens this picker. Two stops for one action would only confuse. */}
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
