// The composer (§8). Asking is the product, so this is the boldest thing on the screen — twice:
//
//  - `hero`: an empty workspace. A 32px box, three lines tall, lifted off the canvas, with a
//    placeholder that types real example questions out while nobody is using it.
//  - `docked`: a conversation. The same controls in a 24px bar floating over the blurred page.
//
// One component for both, because they are one control: the same textarea keeps its id, its
// draft and its focus when the first question turns the hero into the bar.

import { useEffect, useState, type KeyboardEvent, type ReactNode, type Ref } from 'react'
import { Button, Chip, Popover, Tooltip, cx } from '../ui'
import { Glyph } from '../graphics'
import { typedPlaceholder } from './prompts'

// §8: the three writing tips live behind the "?" — never as a paragraph under the box.
const WRITING_TIPS = [
  'Name the period: “in 2025”, “in FY25”.',
  'Name the measure: “gross pay”, not “pay”.',
  'Ask a follow-up: “now split that by location”.',
]

export interface ComposerProps {
  variant: 'hero' | 'docked'
  value: string
  onChange: (value: string) => void
  /** Sends the draft. The form's submit, so Enter and the Ask button are the same path. */
  onSubmit: () => void
  /** No question can be sent: the files are not loaded, or one is already running. */
  disabled: boolean
  /** The files are loaded and a question would be answered. Drives the status dot. */
  ready: boolean
  /** Shown while the box is empty and nobody is in it, typed out one at a time (§8). */
  examples: string[]
  /** The placeholder the rest of the time: while typing, and when asking is off. */
  idlePlaceholder: string
  /** Files loaded right now. Zero hides the chip rather than saying "Data: 0 files". */
  fileCount: number
  /** Opens the Data drawer, which the top bar owns (§6). Without it the chip states the fact. */
  onOpenData?: () => void
  /** One quiet line under the bar: "Enter to ask", and how much room is left near the limit. */
  hint?: ReactNode
  maxLength: number
  textareaRef?: Ref<HTMLTextAreaElement>
}

/** The model's own state, in one dot and one word. Green is "ask me something". */
function ModelStatus({ ready }: { ready: boolean }) {
  const tip = ready
    ? 'An AI model writes the query; your rows never reach it.'
    : 'Your files are no longer loaded, so questions are off.'
  return (
    <Tooltip label={tip}>
      {/* Not focusable: it is a state, not a control, and a tab stop between the question box and
          the Ask button would be one more press on the product's most-used path. The whole
          sentence is the element's own name, so a screen reader reads it where the eye reads
          "Ready"; the tooltip is the mouse's copy of the same words. */}
      <span
        role="img"
        aria-label={tip}
        className="inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-caption text-steel"
      >
        <span aria-hidden className={cx('size-2 shrink-0 rounded-full', ready ? 'bg-success' : 'bg-stone')} />
        {ready ? 'Ready' : 'Files not loaded'}
      </span>
    </Tooltip>
  )
}

export default function Composer({
  variant,
  value,
  onChange,
  onSubmit,
  disabled,
  ready,
  examples,
  idlePlaceholder,
  fileCount,
  onOpenData,
  hint,
  maxLength,
  textareaRef,
}: ComposerProps) {
  const hero = variant === 'hero'
  const [focused, setFocused] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  // Reduced motion keeps the example and drops the typing: the first question simply sits there.
  const [still] = useState(() => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches)

  // The typewriter runs only when there is nothing to read in the box and nobody is in it, so it
  // never eats a character of somebody's question or blinks under their cursor.
  const cycling = !disabled && value === '' && !focused && examples.length > 0
  useEffect(() => {
    if (!cycling || still) return
    const started = performance.now()
    const timer = setInterval(() => setElapsed(performance.now() - started), 60)
    return () => clearInterval(timer)
  }, [cycling, still])

  const placeholder = !cycling ? idlePlaceholder : still ? examples[0] : typedPlaceholder(examples, elapsed)

  function submit(event: { preventDefault(): void }) {
    event.preventDefault()
    onSubmit()
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // isComposing: Enter also confirms a word on Hindi and other IME keyboards; that is not a submit.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) submit(event)
  }

  return (
    <form onSubmit={submit}>
      <div
        className={cx(
          // The one surface that lifts off the canvas (§2 level 2). Focus grows the border into
          // the cobalt ring and lifts the whole box a hair (§4).
          // One background per variant, never both: two `bg-canvas*` utilities on one element are
          // decided by the order of the built stylesheet, not by the order written here.
          'flex flex-col border shadow-level-2 transition-[border-color,transform] duration-200',
          'focus-within:-translate-y-px focus-within:border-primary focus-within:ring-1 focus-within:ring-primary',
          hero ? 'rounded-xxxl border-hairline bg-canvas p-3' : 'rounded-xxl border-hairline-soft bg-canvas/85 p-2 backdrop-blur-md',
        )}
      >
        <label htmlFor="darwinlens-question" className="sr-only">
          Your question
        </label>
        <textarea
          // The id is the workspace's handle on this box: "Ask about this" on a tile types a
          // question into it, and the skip link jumps to it.
          id="darwinlens-question"
          ref={textareaRef}
          rows={hero ? 3 : 1}
          value={value}
          maxLength={maxLength}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          aria-describedby={hint ? 'darwinlens-question-hint' : undefined}
          // 16px on a phone, or the browser zooms the page when the box takes focus.
          className={cx(
            'w-full resize-none bg-transparent px-3 text-body-md text-ink [field-sizing:content]',
            'placeholder:text-steel disabled:text-stone',
            // The box around it is the focus indicator (its border turns cobalt and thickens into
            // a ring), so the textarea's own outline would draw a second rectangle inside it.
            // Important, because the global :focus-visible rule is unlayered and would win.
            'outline-none! focus-visible:outline-none!',
            // 88px: three 24px lines plus the padding, because `field-sizing` would otherwise
            // shrink the hero box to one line and the invitation with it.
            hero ? 'min-h-[5.5rem] py-2' : 'max-h-28 min-h-9 py-1.5',
          )}
        />

        <div className="flex flex-wrap items-center gap-1.5 px-1 pt-1">
          {/* Without a handler the count is still worth stating; it just is not a button. */}
          {fileCount > 0 && (
            <Chip
              static={onOpenData === undefined}
              leading={<Glyph name="table" size={16} />}
              onClick={onOpenData}
              className="px-3 py-1.5"
            >
              Data: {fileCount === 1 ? '1 file' : `${fileCount} files`}
            </Chip>
          )}
          <ModelStatus ready={ready} />
          {/* The writing tips, behind a question mark. Only in the hero: a panel opening downward
              from a bar docked to the bottom of the window would be cut off by it. */}
          {hero && (
            <Popover
              trigger="?"
              triggerLabel="How to word a question"
              title="Wording a question"
              className="press inline-flex size-7 items-center justify-center rounded-full border border-hairline-soft text-button-md text-charcoal hover:bg-surface-soft"
            >
              <ul className="list-disc space-y-1.5 pl-4">
                {WRITING_TIPS.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            </Popover>
          )}
          <Button type="submit" variant="action" size={hero ? 'md' : 'sm'} disabled={disabled || value.trim() === ''} className="ml-auto">
            Ask
            <span aria-hidden className="text-white/80">
              ↵
            </span>
          </Button>
        </div>
      </div>

      {hint && (
        <p id="darwinlens-question-hint" className="mt-2 px-4 text-caption text-steel">
          {hint}
        </p>
      )}
    </form>
  )
}
