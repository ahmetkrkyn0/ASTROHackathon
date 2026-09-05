import { useEffect, useRef, useState } from 'react'

/**
 * The chart's real rendered width, in CSS pixels.
 *
 * This exists because a stretched viewBox scales TEXT along with the drawing.
 * A 640-unit box in the full-width card renders at ~1120px, so a 9-unit tick
 * label lands near 16px -- larger than any label in the cockpit -- while the
 * same chart in a half-width card renders the same label near 7px. One chart,
 * two type sizes, a factor of two apart.
 *
 * Measuring instead lets the chart draw in pixel space, where a font-size of
 * 10 is 10px in every card and the type scale is the cockpit's, not an
 * accident of column width.
 */
export function useChartWidth(fallback = 640): [React.RefObject<HTMLDivElement>, number] {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(fallback)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    // ResizeObserver rather than a window resize listener: the rails collapse
    // and the details section expands without the window changing size at all,
    // and both change how wide these cards are.
    const observer = new ResizeObserver(([entry]) => {
      const next = entry.contentRect.width
      if (next > 0) setWidth(next)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return [ref, width]
}
