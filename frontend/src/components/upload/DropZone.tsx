// Drag-and-drop plus click-to-choose, used large where a project starts and compact everywhere
// else. The real control is a native <input type="file">: the button opens it, so keyboard and
// screen reader users get the browser's own file picker. The input sits outside the clickable area
// so its own click event cannot bubble back and re-open the picker. While an upload runs the
// caller renders UploadProgress in this component's place, so there is no disabled state to manage.

import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { Glyph } from '../graphics'
import { Button, cx } from '../ui'
import { ACCEPT_ATTRIBUTE } from './files'

interface DropZoneProps {
  onFiles: (files: File[]) => void
  /** One line instead of the full invitation: in a dialog, or beside a re-attach. */
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
          'cursor-pointer border-2 border-dashed text-center transition-colors duration-150',
          compact ? 'rounded-xl px-4 py-4' : 'rounded-xxl px-4 py-10 sm:px-6 sm:py-12',
          dragging ? 'border-primary bg-primary-soft' : 'border-hairline bg-surface-soft hover:border-primary',
          className,
        )}
      >
        {!compact && (
          <>
            <Glyph name="upload" size={48} className="mx-auto text-charcoal" />
            <p className="mt-4 text-heading-sm text-ink-deep">Drop your files here</p>
          </>
        )}
        {/* The keyboard control. No onClick of its own: the click bubbles to the frame above,
            which opens the picker once. */}
        <Button variant={compact ? 'ghost' : 'primary'} size={compact ? 'sm' : 'md'} className={compact ? '' : 'mt-5'}>
          {label ?? (compact ? 'Add more files' : 'Choose files')}
        </Button>
        <p className={cx('text-body-sm text-steel', compact ? 'mt-2' : 'mt-4')}>
          {compact ? 'or drop them here' : 'Several at once is fine: .csv, .tsv, .xlsx or .xlsm.'}
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
