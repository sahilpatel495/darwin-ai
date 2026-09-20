// Everything Verity knows about the uploaded data: files with their receipts, how the files
// connect, and the metric definitions. A fixed column from 768px up; below that it is a drawer
// opened from the bar under the header. While the drawer is closed it is `invisible`, which also takes its
// controls out of the tab order, so keyboard users never tab into something they cannot see.

import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import type { Catalog, Metric } from '../../types'
import DropZone from '../upload/DropZone'
import UploadProgress from '../upload/UploadProgress'
import type { Busy } from '../upload/UploadProgress'
import FileCard from './FileCard'
import Glossary from './Glossary'
import Links from './Links'

interface SidebarProps {
  catalog: Catalog
  busy: Busy | null
  /** Drawer state; ignored from 768px up, where the sidebar is always visible. */
  open: boolean
  onClose: () => void
  onFiles: (files: File[]) => void
  onSetLink: (linkId: string, status: 'active' | 'rejected') => Promise<void>
  onSaveGlossary: (glossary: Metric[]) => Promise<boolean>
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {children}
    </section>
  )
}

export default function Sidebar({ catalog, busy, open, onClose, onFiles, onSetLink, onSaveGlossary }: SidebarProps) {
  const closeButton = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (!open) return
    closeButton.current?.focus() // keyboard users land inside the drawer they just opened
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // Union views are listed under "How your files connect", not as files: nobody uploaded them.
  const files = catalog.tables.filter((table) => !table.is_view)

  return (
    <>
      {open && <div onClick={onClose} aria-hidden className="fixed inset-0 z-30 bg-ink/40 md:hidden" />}
      <aside
        aria-label="Your data"
        className={`z-40 w-[min(22rem,88vw)] shrink-0 space-y-6 overflow-y-auto border-r border-line bg-canvas p-4 transition-transform max-md:fixed max-md:inset-y-0 max-md:left-0 md:w-80 ${
          open ? '' : 'max-md:invisible max-md:-translate-x-full'
        }`}
      >
        <button ref={closeButton} type="button" onClick={onClose} className="ml-auto block rounded-md border border-line px-2.5 py-1 text-sm font-medium text-ink md:hidden">
          Close
        </button>

        <Section title="Your files">
          <ul className="space-y-2">
            {files.map((table) => (
              <FileCard key={table.name} table={table} />
            ))}
          </ul>
          {busy ? <UploadProgress busy={busy} /> : <DropZone compact onFiles={onFiles} />}
        </Section>

        <Section title="How your files connect">
          <Links catalog={catalog} onSetLink={onSetLink} />
        </Section>

        <Section title="Metric definitions">
          <Glossary glossary={catalog.glossary} onSave={onSaveGlossary} />
        </Section>
      </aside>
    </>
  )
}
