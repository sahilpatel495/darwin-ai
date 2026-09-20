// The search pill's real self (§6): ⌘K anywhere, then type. It goes to a page or a project, asks
// a question you have asked before, or starts an analysis — all without the mouse.
//
// Built on the native <dialog> rather than on <Dialog>, for the one reason a palette is different
// from every other overlay: the first thing in it is the field, not a heading, and the list under
// it is a listbox the field drives. <dialog> still gives us the focus trap, Esc and the scrim.

import { useEffect, useMemo, useRef, useState } from 'react'
import { analysesPath, boardPath, go, HOW, overviewPath, PROJECTS, projectPath, SETTINGS, TRUST } from '../../lib/route'
import type { ProjectRecord } from '../../lib/projects'
import { Glyph } from '../graphics'
import type { GlyphName } from '../graphics/Glyph'
import { cx, Kbd, SearchIcon } from '../ui'

export interface CommandPaletteProps {
  open: boolean
  onClose: () => void
  /** Newest first. Every one of them is one Enter away. */
  projects: ProjectRecord[]
  /** The project that is open, if any: its sections and its questions come first. */
  project: ProjectRecord | null
  /** Asks a question again, in the project it was asked in. */
  onAsk: (projectId: string, question: string) => void
}

interface Command {
  id: string
  /** What happens, in the analyst's words. */
  label: string
  /** The group it sits under: "Go to", "Projects", "Ask again". */
  group: string
  glyph: GlyphName
  run: () => void
}

/** How many past questions are worth offering. Beyond this it is a transcript, not a shortcut. */
const RECENT_QUESTIONS = 8

const matches = (command: Command, typed: string) => command.label.toLowerCase().includes(typed) || command.group.toLowerCase().includes(typed)

export default function CommandPalette({ open, onClose, projects, project, onAsk }: CommandPaletteProps) {
  const dialog = useRef<HTMLDialogElement>(null)
  const field = useRef<HTMLInputElement>(null)
  const [typed, setTyped] = useState('')
  const [at, setAt] = useState(0)

  const commands = useMemo<Command[]>(() => {
    const list: Command[] = []
    const goTo = (id: string, label: string, href: string, glyph: GlyphName) => list.push({ id, label, group: 'Go to', glyph, run: () => go(href) })

    if (project) {
      goTo('ask', 'Ask a question', projectPath(project.id), 'sparkles')
      goTo('overview', 'Overview of this project', overviewPath(project.id), 'bars')
      goTo('analyses', 'Start an analysis', analysesPath(project.id), 'compare')
      goTo('board', 'Saved report', boardPath(project.id), 'receipt')
    }
    goTo('home', 'Your projects', PROJECTS, 'table')
    goTo('settings', 'Profile and usage', SETTINGS, 'people')
    goTo('how', 'How DarwinLens works', HOW, 'lock')
    goTo('trust', 'Trust report', TRUST, 'shield')

    for (const other of projects) {
      if (other.id === project?.id) continue
      list.push({ id: `p-${other.id}`, label: other.name, group: 'Projects', glyph: 'table', run: () => go(projectPath(other.id)) })
    }

    // Newest question first: the one you want again is usually the one you just had.
    if (project) {
      const { id } = project
      for (const turn of [...project.turns].reverse().slice(0, RECENT_QUESTIONS)) {
        list.push({ id: `q-${turn.id}`, label: turn.question, group: 'Ask again', glyph: 'sparkles', run: () => onAsk(id, turn.question) })
      }
    }
    return list
  }, [project, projects, onAsk])

  const shown = useMemo(() => {
    const needle = typed.trim().toLowerCase()
    return needle ? commands.filter((command) => matches(command, needle)) : commands
  }, [commands, typed])

  useEffect(() => {
    const el = dialog.current
    if (!el) return
    if (open && !el.open) {
      el.showModal()
      setTyped('')
      setAt(0)
      field.current?.focus()
    }
    if (!open && el.open) el.close()
  }, [open])

  // A list that has shrunk under the cursor must not leave the cursor past its end.
  useEffect(() => setAt((current) => Math.min(current, Math.max(0, shown.length - 1))), [shown.length])

  const choose = (command: Command | undefined) => {
    if (!command) return
    onClose()
    command.run()
  }

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'ArrowDown') setAt((current) => (current + 1) % Math.max(1, shown.length))
    else if (event.key === 'ArrowUp') setAt((current) => (current - 1 + Math.max(1, shown.length)) % Math.max(1, shown.length))
    else if (event.key === 'Home') setAt(0)
    else if (event.key === 'End') setAt(Math.max(0, shown.length - 1))
    else if (event.key === 'Enter') choose(shown[at])
    else return
    event.preventDefault()
  }

  let lastGroup = ''

  return (
    <dialog
      ref={dialog}
      aria-label="Search DarwinLens"
      onClose={onClose}
      onClick={(event) => event.target === dialog.current && onClose()}
      className="w-[36rem] max-w-[calc(100vw-2rem)] rounded-xxl p-0 sm:mt-[12vh] sm:mb-auto"
    >
      <div className="flex max-h-[70dvh] flex-col" onKeyDown={onKeyDown}>
        <div className="flex shrink-0 items-center gap-3 border-b border-hairline-soft px-5 py-4">
          <span aria-hidden className="text-stone">
            <SearchIcon size={20} />
          </span>
          <input
            ref={field}
            value={typed}
            onChange={(event) => {
              setTyped(event.target.value)
              setAt(0)
            }}
            role="combobox"
            aria-expanded
            aria-haspopup="listbox"
            aria-autocomplete="list"
            aria-controls="palette-list"
            aria-activedescendant={shown[at] ? `palette-${shown[at].id}` : undefined}
            aria-label="Search pages, projects and questions"
            placeholder="Search or ask…"
            autoComplete="off"
            // No ring of its own. Focus never leaves this box — the arrow keys move a highlight
            // through the list below via aria-activedescendant — so the highlighted row is the
            // focus indicator, and a second rectangle drawn around the text is just a box inside
            // a box. Important, because the global :focus-visible rule in index.css is unlayered.
            className="min-w-0 flex-1 bg-transparent text-subtitle-md text-ink-deep outline-none! placeholder:text-stone focus-visible:outline-none!"
          />
          <Kbd>Esc</Kbd>
        </div>

        {/* A listbox owns its options directly, so the grouping headers are presentational and
            each result is the option itself — no wrapper in between to confuse a screen reader. */}
        <div id="palette-list" role="listbox" aria-label="Results" className="min-h-0 flex-1 overflow-y-auto p-2">
          {shown.length === 0 && <p className="px-3 py-6 text-center text-body-md text-slate">Nothing here by that name. Try a project or a question you have asked.</p>}
          {shown.map((command, index) => {
            const header = command.group !== lastGroup ? command.group : null
            lastGroup = command.group
            return (
              <div key={command.id} role="presentation">
                {header && <p className="px-3 pt-3 pb-1 text-caption font-bold text-steel">{header}</p>}
                <button
                  type="button"
                  id={`palette-${command.id}`}
                  role="option"
                  aria-selected={index === at}
                  onMouseMove={() => setAt(index)}
                  onClick={() => choose(command)}
                  className={cx(
                    'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-body-md',
                    index === at ? 'bg-surface-soft text-ink-deep' : 'text-ink',
                  )}
                >
                  <span aria-hidden className="shrink-0 text-charcoal">
                    <Glyph name={command.glyph} size={22} />
                  </span>
                  <span className="min-w-0 flex-1 truncate">{command.label}</span>
                  {index === at && <Kbd>↵</Kbd>}
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </dialog>
  )
}
