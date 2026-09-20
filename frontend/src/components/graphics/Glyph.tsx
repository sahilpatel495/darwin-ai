// Duotone line illustrations, 24–64px (§4). They stand in for the stock photography a marketing
// site would use: feature tiles, empty states, the analysis gallery, suggestion cards.
//
// Two inks and no more: the line is `currentColor`, so a glyph takes the colour of whatever it
// sits in, and one accent shape underneath it (cobalt by default, purple as the second accent)
// gives the drawing a subject without a second stroke weight to reconcile.
//
// Drawn on a 32-unit grid with a 3-unit margin and 1.6 strokes, so a shield and a donut still look
// like the same hand at 24px in a chip and at 64px in a hero tile.

import type { SVGProps } from 'react'

export type GlyphName =
  | 'bars' | 'trend' | 'donut' | 'table' | 'shield' | 'link' | 'sparkles'
  | 'upload' | 'lock' | 'receipt' | 'people' | 'rupee' | 'calendar' | 'compare'

export interface GlyphProps extends Omit<SVGProps<SVGSVGElement>, 'name'> {
  name: GlyphName
  /** Side in pixels. 24 in a chip, 32 in a suggestion card, 48–64 in a feature tile. */
  size?: number
  /** The second ink. Cobalt by default; `var(--color-purple)` for the alternating tile. */
  accent?: string
}

/** The accent shape: a solid wash you can see through, so the line drawing stays the subject. */
const Wash = ({ children, accent }: { children: React.ReactNode; accent: string }) => (
  <g fill={accent} opacity={0.16}>
    {children}
  </g>
)

/** The one solid accent mark per glyph: the detail the eye lands on first. */
const Mark = ({ children, accent }: { children: React.ReactNode; accent: string }) => <g fill={accent}>{children}</g>

function shapes(name: GlyphName, accent: string) {
  switch (name) {
    case 'bars':
      return (
        <>
          <Wash accent={accent}>
            <rect x="5" y="17" width="5" height="10" rx="2" />
            <rect x="21" y="9" width="5" height="18" rx="2" />
          </Wash>
          <path d="M7.5 27v-9M16 27V13M24.5 27v-7" />
          <path d="M4 27h24" />
          <Mark accent={accent}>
            <rect x="13.5" y="12" width="5" height="15" rx="2" />
          </Mark>
        </>
      )
    case 'trend':
      return (
        <>
          <Wash accent={accent}>
            <path d="M4 21.5 12 15l6 4.5L28 9v16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" />
          </Wash>
          <path d="M4 21.5 12 15l6 4.5L28 9" />
          <path d="M22.5 8.5H28V14" />
          <path d="M4 27h24" />
          <Mark accent={accent}>
            <circle cx="12" cy="15" r="2.2" />
          </Mark>
        </>
      )
    case 'donut':
      return (
        <>
          <Wash accent={accent}>
            <path d="M16 4a12 12 0 0 1 12 12h-6a6 6 0 0 0-6-6Z" />
          </Wash>
          <circle cx="16" cy="16" r="12" />
          <circle cx="16" cy="16" r="5.5" />
          <path d="M16 4v6M28 16h-6" />
          <Mark accent={accent}>
            <path d="M16 4a12 12 0 0 1 9.6 4.8l-4.8 3.6A6 6 0 0 0 16 10Z" />
          </Mark>
        </>
      )
    case 'table':
      return (
        <>
          <Wash accent={accent}>
            <rect x="4" y="5" width="24" height="6" rx="2" />
          </Wash>
          <rect x="4" y="5" width="24" height="22" rx="3" />
          <path d="M4 11.5h24M4 19h24M13 11.5V27" />
          <Mark accent={accent}>
            <rect x="16" y="14.5" width="8" height="2.2" rx="1.1" />
            <rect x="16" y="22" width="5" height="2.2" rx="1.1" />
          </Mark>
        </>
      )
    case 'shield':
      return (
        <>
          <Wash accent={accent}>
            <path d="M16 3.5 27 7v9c0 6.4-4.4 11-11 13.5C9 27 4.5 22.4 4.5 16V7Z" />
          </Wash>
          <path d="M16 3.5 27 7v9c0 6.4-4.4 11-11 13.5C9 27 4.5 22.4 4.5 16V7Z" />
          <path d="m11 16 3.5 3.5L21.5 13" />
          <Mark accent={accent}>
            <circle cx="16" cy="7.2" r="1.6" />
          </Mark>
        </>
      )
    case 'link':
      // A link in DarwinLens is a column two *files* share, so the drawing is two files joined —
      // not a chain, which says "URL" to everyone who has used a browser.
      return (
        <>
          <Wash accent={accent}>
            <rect x="3" y="9" width="10" height="14" rx="3" />
          </Wash>
          <rect x="3" y="9" width="10" height="14" rx="3" />
          <rect x="19" y="9" width="10" height="14" rx="3" />
          <path d="M13 16h6" />
          <Mark accent={accent}>
            <circle cx="13" cy="16" r="1.8" />
            <circle cx="19" cy="16" r="1.8" />
          </Mark>
        </>
      )
    case 'sparkles':
      return (
        <>
          <Wash accent={accent}>
            <path d="M13 4c.9 5.3 2.8 7.2 8 8.1-5.2.9-7.1 2.8-8 8.1-.9-5.3-2.8-7.2-8-8.1 5.2-.9 7.1-2.8 8-8.1Z" />
          </Wash>
          <path d="M13 4c.9 5.3 2.8 7.2 8 8.1-5.2.9-7.1 2.8-8 8.1-.9-5.3-2.8-7.2-8-8.1 5.2-.9 7.1-2.8 8-8.1Z" />
          <path d="M23 18c.5 3 1.5 4 4.5 4.5-3 .5-4 1.5-4.5 4.5-.5-3-1.5-4-4.5-4.5 3-.5 4-1.5 4.5-4.5Z" />
          <Mark accent={accent}>
            <circle cx="23" cy="22.5" r="1.6" />
          </Mark>
        </>
      )
    case 'upload':
      return (
        <>
          <Wash accent={accent}>
            <path d="M4 19h24v6a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3Z" />
          </Wash>
          <path d="M4 19v6a3 3 0 0 0 3 3h18a3 3 0 0 0 3-3v-6" />
          <path d="M16 21V4M16 4l-6 6M16 4l6 6" />
          <Mark accent={accent}>
            <circle cx="16" cy="4.4" r="1.8" />
          </Mark>
        </>
      )
    case 'lock':
      return (
        <>
          <Wash accent={accent}>
            <rect x="5.5" y="14" width="21" height="14" rx="4" />
          </Wash>
          <rect x="5.5" y="14" width="21" height="14" rx="4" />
          <path d="M10.5 14v-4a5.5 5.5 0 0 1 11 0v4" />
          <Mark accent={accent}>
            <circle cx="16" cy="20.2" r="2.2" />
            <rect x="14.9" y="20.2" width="2.2" height="4" rx="1.1" />
          </Mark>
        </>
      )
    case 'receipt':
      return (
        <>
          <Wash accent={accent}>
            <path d="M6 4h20v24l-3.3-2.2L19.3 28 16 25.8 12.7 28l-3.4-2.2L6 28Z" />
          </Wash>
          <path d="M6 4h20v24l-3.3-2.2L19.3 28 16 25.8 12.7 28l-3.4-2.2L6 28Z" />
          <path d="M11 11h10M11 16.5h10" />
          <Mark accent={accent}>
            <rect x="11" y="20.8" width="6" height="2.2" rx="1.1" />
          </Mark>
        </>
      )
    case 'people':
      return (
        <>
          <Wash accent={accent}>
            <path d="M3.5 27.5c0-4.7 3.8-7.5 8.5-7.5s8.5 2.8 8.5 7.5Z" />
          </Wash>
          <circle cx="12" cy="11" r="5" />
          <path d="M3.5 27.5c0-4.7 3.8-7.5 8.5-7.5s8.5 2.8 8.5 7.5" />
          <path d="M21.5 7.4a5 5 0 0 1 0 9.2M23 20.6c3.4.7 5.5 3.3 5.5 6.9" />
          <Mark accent={accent}>
            <circle cx="12" cy="11" r="2" />
          </Mark>
        </>
      )
    case 'rupee':
      return (
        <>
          <Wash accent={accent}>
            <circle cx="16" cy="16" r="12.5" />
          </Wash>
          <circle cx="16" cy="16" r="12.5" />
          {/* The ₹ drawn rather than typed: a glyph must not depend on a font having loaded.
              Its top bar is the accent mark, so the two inks land on the letter itself. */}
          <path d="M11.5 13.5h9M18.5 9.5c0 3.7-2.5 4-7 4l8 9" />
          <Mark accent={accent}>
            <rect x="11" y="8.4" width="10" height="2.2" rx="1.1" />
          </Mark>
        </>
      )
    case 'calendar':
      return (
        <>
          <Wash accent={accent}>
            <rect x="4" y="6" width="24" height="6" rx="3" />
          </Wash>
          <rect x="4" y="6" width="24" height="22" rx="3.5" />
          <path d="M4 12.5h24M10.5 3.5V8M21.5 3.5V8" />
          <Mark accent={accent}>
            <rect x="9" y="16.5" width="5" height="5" rx="1.6" />
          </Mark>
        </>
      )
    case 'compare':
      return (
        <>
          <Wash accent={accent}>
            <rect x="4" y="9" width="10" height="18" rx="3" />
          </Wash>
          <rect x="4" y="9" width="10" height="18" rx="3" />
          <rect x="18" y="4" width="10" height="23" rx="3" />
          <Mark accent={accent}>
            <rect x="20.4" y="12" width="5.2" height="2.2" rx="1.1" />
          </Mark>
        </>
      )
  }
}

/**
 * One glyph. Decorative by default — every place it appears puts words beside it — so it is
 * hidden from screen readers unless you give it a `title`.
 */
export default function Glyph({ name, size = 32, accent = 'var(--color-primary)', ...rest }: GlyphProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...rest}
    >
      {shapes(name, accent)}
    </svg>
  )
}
