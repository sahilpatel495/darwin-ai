// One glyph per kind of analysis (§14). Each draws the shape of its own result — descending
// bars for a breakdown, a rising line for a trend, a lone dot away from the cluster for unusual
// values — so the gallery can be read before any of the words are.
//
// Same grid as components/ui/icons.tsx (20px box, 1.7px strokes, currentColor) so they sit with
// the rest of the product's glyphs. They live here rather than there because they are analysis
// kinds, which arrive from the server and may grow: an unknown key falls back to a plain chart.

import type { ReactNode, SVGProps } from 'react'

const PATHS: Record<string, ReactNode> = {
  // Split one number by a group: bars of different lengths.
  breakdown: <path d="M3.5 5.5h11M3.5 10h7M3.5 14.5h4" />,
  // Month by month: a line that climbs.
  trend: (
    <>
      <path d="M3 13.5 7 9.5l3 2.5 6-6" />
      <path d="M16.5 5.5h-3M16.5 5.5V9" />
    </>
  ),
  // The highest and the lowest: one arrow each way.
  top_n: (
    <>
      <path d="M6 12.5V4M6 4 3.6 6.4M6 4l2.4 2.4" />
      <path d="M14 7.5V16M14 16l2.4-2.4M14 16l-2.4-2.4" />
    </>
  ),
  // How values are spread: a histogram with the mass in the middle.
  distribution: (
    <>
      <path d="M2.5 16.5h15" />
      <path d="M4.5 16.5V14M7.5 16.5v-6M10.5 16.5V7M13.5 16.5v-6M16.5 16.5V14" />
    </>
  ),
  // Part of the whole: a ring with one slice marked off.
  share: (
    <>
      <circle cx="10" cy="10" r="6.75" />
      <path d="M10 3.25A6.75 6.75 0 0 1 16.75 10H10Z" />
    </>
  ),
  // One group crossed with another: a table.
  pivot: (
    <>
      <rect x="3" y="3.5" width="14" height="13" rx="1.6" />
      <path d="M3 8h14M8.5 8v8.5" />
    </>
  ),
  // Do two numbers move together: points around a line.
  correlation: (
    <>
      <path d="M3.5 16.5 16.5 4.5" />
      <circle cx="6.5" cy="12" r="1.15" fill="currentColor" stroke="none" />
      <circle cx="10" cy="10.5" r="1.15" fill="currentColor" stroke="none" />
      <circle cx="13.5" cy="6.5" r="1.15" fill="currentColor" stroke="none" />
    </>
  ),
  // This period against the one before: a short bar, a tall bar, the step between them.
  change: (
    <>
      <path d="M5.5 16.5v-5M14.5 16.5V6" />
      <path d="m8.8 11.4 3.4-3.4M12.2 8h-2.5M12.2 8v2.5" />
    </>
  ),
  // Far outside the usual range: a cluster, and one on its own.
  outliers: (
    <>
      <circle cx="6" cy="13.2" r="1.15" fill="currentColor" stroke="none" />
      <circle cx="9.2" cy="14.6" r="1.15" fill="currentColor" stroke="none" />
      <circle cx="8.2" cy="11" r="1.15" fill="currentColor" stroke="none" />
      <circle cx="14.8" cy="5.8" r="1.15" fill="currentColor" stroke="none" />
      <circle cx="14.8" cy="5.8" r="3.4" />
    </>
  ),
}

const FALLBACK = <path d="M3 16.5h14M5.5 13.5v-3M9 13.5V6M12.5 13.5v-5M16 13.5V9" />

/** The glyph for one analysis kind. Decorative: the card beside it carries the name. */
export default function KindIcon({ kind, size = 20, ...rest }: SVGProps<SVGSVGElement> & { kind: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...rest}
    >
      {PATHS[kind] ?? FALLBACK}
    </svg>
  )
}
