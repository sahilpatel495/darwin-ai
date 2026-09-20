// The signature background (§4): three radial gradients in cobalt, purple and ice drifting slowly
// over white, under a fine grain that stops the blend from banding on a cheap panel.
//
// Cheap on purpose. Three absolutely-positioned divs animating `transform` and nothing else, so
// the compositor does the whole thing on the GPU and there is no paint per frame — a CSS filter:
// blur() over a full-screen element is what makes this kind of background cost 30% of a laptop's
// battery, so the softness comes from the gradient's own falloff instead.
//
// Under `prefers-reduced-motion` the blobs simply stop where they are: the colour is the point,
// the drift is the flourish.

import type { CSSProperties } from 'react'
import { cx } from '../ui/cx'

export interface AuroraBackdropProps {
  /** `hero` a wash you can read a 64px headline over · `panel` half the alpha, for auth art. */
  intensity?: 'hero' | 'panel'
  className?: string
}

// 1px of noise tiled by the browser. An inline SVG data URI, not a file: the strict CSP is
// `default-src 'self'`, and this stays self-hosted without a round trip.
const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)' opacity='.5'/%3E%3C/svg%3E\")"

interface Blob {
  color: string
  style: CSSProperties
}

/** Three blobs, three periods that do not divide into each other, so the loop never reads. */
const BLOBS: Blob[] = [
  {
    color: 'var(--color-primary)',
    style: { top: '-24%', left: '-12%', width: '72%', height: '96%', animation: 'drift-a 26s var(--ease-in-out) infinite' },
  },
  {
    color: 'var(--color-purple)',
    style: { top: '-18%', right: '-14%', width: '66%', height: '88%', animation: 'drift-b 34s var(--ease-in-out) infinite' },
  },
  {
    // Ice: the cold pale blue that keeps the other two from reading as a single violet smear.
    color: '#7FD4F5',
    style: { bottom: '-34%', left: '18%', width: '78%', height: '82%', animation: 'drift-c 41s var(--ease-in-out) infinite' },
  },
]

export default function AuroraBackdrop({ intensity = 'hero', className }: AuroraBackdropProps) {
  const alpha = intensity === 'hero' ? 0.34 : 0.18

  return (
    <div aria-hidden className={cx('pointer-events-none absolute inset-0 overflow-hidden bg-canvas', className)}>
      {BLOBS.map((blob, i) => (
        <div
          key={i}
          className="absolute"
          style={{
            ...blob.style,
            background: `radial-gradient(closest-side, color-mix(in srgb, ${blob.color} ${Math.round(alpha * 100)}%, transparent), transparent 100%)`,
          }}
        />
      ))}
      {/* The grain sits over the colour, not under it: it is there to break the gradient's
          banding, and under the blobs it would be invisible. */}
      <div className="absolute inset-0 opacity-[.035] mix-blend-multiply" style={{ backgroundImage: GRAIN, backgroundSize: '160px 160px' }} />
    </div>
  )
}
