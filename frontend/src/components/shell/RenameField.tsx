// Renaming happens where the name is (§8): the name becomes a field, Enter saves, Esc puts it
// back. No dialog — renaming is not a decision, and a dialog would make it feel like one.

import { useState } from 'react'
import { Button, Input, cx } from '../ui'

interface RenameFieldProps {
  name: string
  /** Called with the trimmed name. An empty field is a cancel, not a nameless project. */
  onSave: (name: string) => void
  onCancel: () => void
  className?: string
}

const MAX_NAME = 80

export default function RenameField({ name, onSave, onCancel, className }: RenameFieldProps) {
  const [draft, setDraft] = useState(name)

  return (
    <form
      className={cx('flex min-w-0 flex-wrap items-end gap-2', className)}
      onSubmit={(event) => {
        event.preventDefault()
        const next = draft.trim()
        if (next) onSave(next)
        else onCancel()
      }}
    >
      <Input
        label="Project name"
        labelHidden
        autoFocus
        value={draft}
        maxLength={MAX_NAME}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => event.key === 'Escape' && onCancel()}
        className="min-w-40 flex-1"
      />
      <Button type="submit" variant="primary" size="sm">
        Save name
      </Button>
      <Button variant="ghost" size="sm" onClick={onCancel}>
        Cancel
      </Button>
    </form>
  )
}
