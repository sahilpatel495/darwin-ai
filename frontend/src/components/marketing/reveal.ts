// "Light these up one at a time, the first time they are scrolled to."
//
// Two diagrams need exactly this — the landing's flow card and the How page's what-the-AI-sees
// panel — and both want it once rather than on a loop: a sequence that replays every time it
// scrolls past is decoration, and the second viewing teaches nothing the first did not.
//
// Reduced motion lights everything immediately, because the sequence is a reading aid, never the
// information itself.

import { useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

/**
 * Attach the ref to the block, render the first `lit` items as revealed.
 * `stepMs` is how far apart they land; 300ms or so reads as a sequence without being a wait.
 */
export function useSequence(length: number, stepMs = 320): [RefObject<HTMLDivElement | null>, number] {
  const block = useRef<HTMLDivElement>(null)
  const timer = useRef(0)
  const [lit, setLit] = useState(0)

  useEffect(() => {
    const element = block.current
    if (!element) return
    // Reduced motion, and any browser without the observer, get everything at once: content that
    // stays invisible because a watcher never fired is worse than content that never animated.
    if (typeof IntersectionObserver === 'undefined' || matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return setLit(length)
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return
        observer.disconnect() // one-shot: scrolling back up does not replay it
        let step = 0
        timer.current = setInterval(() => {
          step += 1
          setLit(step)
          if (step >= length) clearInterval(timer.current)
        }, stepMs)
      },
      { threshold: 0.3 },
    )
    observer.observe(element)
    return () => {
      observer.disconnect()
      clearInterval(timer.current)
    }
  }, [length, stepMs])

  return [block, lit]
}
