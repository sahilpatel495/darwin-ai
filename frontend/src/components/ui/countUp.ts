// The hero figure counts up when an answer arrives (§4). 400 ms, then it is simply the number.
//
// Everything that reaches a StatTile is already formatted for an Indian reader — "₹20.40 Cr",
// "12.4%", "1,28,400". Rather than re-implement that formatting, this finds the one run of
// digits in the display string and interpolates it in place, keeping the prefix, the suffix and
// the number of decimals exactly as the server wrote them. A string with no digits ("Not
// available") is returned untouched and nothing animates.
//
// No imports beyond React, so countUp.test.mjs can load the pure half directly in Node.

import { useEffect, useState } from 'react'

export interface NumericDisplay {
  prefix: string
  /** The digits as written, e.g. "20.40" or "1,28,400". */
  digits: string
  suffix: string
  value: number
  decimals: number
  /** Group separators are put back at the same distances from the decimal point. */
  groups: number[]
}

const NUMBER = /-?\d[\d,]*(?:\.\d+)?/

/** Split "₹20.40 Cr" into "₹" + 20.40 + " Cr". Returns null when there is no number to count. */
export function splitNumber(display: string): NumericDisplay | null {
  const match = NUMBER.exec(display)
  if (!match) return null
  const digits = match[0]
  const value = Number(digits.replace(/,/g, ''))
  if (!Number.isFinite(value)) return null
  const dot = digits.indexOf('.')
  const whole = dot < 0 ? digits : digits.slice(0, dot)
  // Distances from the right of the whole part, so 1,28,400 rebuilds as 1,28,400 and not 128,400.
  const groups: number[] = []
  for (let i = whole.length - 1, seen = 0; i >= 0; i--) {
    if (whole[i] === ',') groups.push(seen)
    else seen++
  }
  return {
    prefix: display.slice(0, match.index),
    digits,
    suffix: display.slice(match.index + digits.length),
    value,
    decimals: dot < 0 ? 0 : digits.length - dot - 1,
    groups,
  }
}

/** Write `value` back in the shape `spec` came in: same decimals, same separators. */
export function formatLike(spec: NumericDisplay, value: number): string {
  const fixed = value.toFixed(spec.decimals)
  const dot = fixed.indexOf('.')
  let whole = dot < 0 ? fixed : fixed.slice(0, dot)
  const rest = dot < 0 ? '' : fixed.slice(dot)
  const sign = whole.startsWith('-') ? '-' : ''
  if (sign) whole = whole.slice(1)
  // `groups` counts digits from the right and is ascending, so every separator already placed
  // sits to the right of the next one: subtract them from the cut, or 1,28,400 comes out 12,8,400.
  spec.groups.forEach((at, placed) => {
    const cut = whole.length - at - placed
    if (cut > 0) whole = `${whole.slice(0, cut)},${whole.slice(cut)}`
  })
  return `${spec.prefix}${sign}${whole}${rest}${spec.suffix}`
}

// Ease-out: fast at the start, so the figure is readable long before it settles.
const ease = (t: number) => 1 - (1 - t) ** 3

/**
 * The display string, counting up to itself over 400 ms. Off when `animate` is false, when the
 * reader asked for reduced motion, or when the string holds no number.
 */
export function useCountUp(display: string, animate: boolean, ms = 400): string {
  const [shown, setShown] = useState(display)

  useEffect(() => {
    const spec = animate ? splitNumber(display) : null
    if (!spec || matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setShown(display)
      return
    }
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      // The last frame prints the original string, so a rounding slip can never show a figure
      // one paisa off the one the database computed.
      setShown(t >= 1 ? display : formatLike(spec, spec.value * ease(t)))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [display, animate, ms])

  return shown
}
