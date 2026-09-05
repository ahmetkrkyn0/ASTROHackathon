import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Where the operator has dragged the assistant, as an offset from where CSS
 * put it.
 *
 * An offset rather than a position, deliberately. The window's resting place
 * is `right: 16px; bottom: 56px` in assistant.css, and that has to keep
 * working: it is what clears the status strip, what the responsive rules
 * adjust, and what an operator who has never dragged anything gets. Storing
 * absolute coordinates would mean reading the CSS back at mount and owning a
 * value the stylesheet is still trying to set. A translate on top of it leaves
 * one source of truth for the resting place.
 */
export interface WindowOffset {
  x: number
  y: number
}

const ZERO: WindowOffset = { x: 0, y: 0 }

/** How much of the window must stay on screen, in px, on every edge. */
export const KEEP_VISIBLE = 64

/**
 * The offset, clamped so the window cannot be dragged out of reach.
 *
 * Pure, and exported, because this is the part with the arithmetic and the
 * part that is wrong in ways nothing would show until a window is already
 * lost. `base` is where CSS alone puts the window -- the rect with the current
 * transform subtracted out.
 *
 * Each edge answers a different question. minX/maxX keep KEEP_VISIBLE px of
 * the window inside the left and right edges. maxY does the same at the
 * bottom. minY is the exception: it clamps the TOP of the window to the top of
 * the viewport rather than letting it go KEEP_VISIBLE px past, because the
 * header is the drag handle -- push the header off the top and there is
 * nothing left to grab.
 */
export function clampOffset(
  next: WindowOffset,
  base: { left: number; top: number; width: number },
  viewport: { width: number; height: number },
): WindowOffset {
  const minX = KEEP_VISIBLE - base.left - base.width
  const maxX = viewport.width - KEEP_VISIBLE - base.left
  const minY = -base.top
  const maxY = viewport.height - KEEP_VISIBLE - base.top

  return {
    x: Math.min(Math.max(next.x, minX), maxX),
    y: Math.min(Math.max(next.y, minY), maxY),
  }
}

/**
 * How far the pointer must travel before a press becomes a drag.
 *
 * Only matters for a handle that is ALSO a button -- the launcher opens the
 * assistant on click and moves on drag, and without a threshold every click
 * would end with a one-pixel move and `isDragging` true, which suppresses the
 * click. 4px is under what a deliberate drag covers and over what a hand
 * shake does.
 */
const DRAG_THRESHOLD = 4

/**
 * Whether a press that landed on `target` should start a drag.
 *
 * Pure and exported because the version inlined in the handler had a bug that
 * no test could reach: it asked `closest('button, ...')` without excluding the
 * handle, and the launcher IS a button -- so every press on it matched, and
 * the one control that most needed dragging could not be dragged at all.
 *
 * The rule is "a control BELOW the handle takes its own click". The chat
 * header holds "Yeni sohbet" and minimize and must not swallow them; a handle
 * that is itself a control is still a handle.
 */
export function shouldStartDrag(target: Element | null, handle: Element): boolean {
  if (!target) return false
  const control = target.closest('button, a, input, textarea, select')
  return control === null || control === handle
}

export interface DraggableOptions {
  /**
   * Selector for the element that actually moves, when it is not the handle
   * itself. The chat window is dragged by its header; the launcher is its own
   * handle and passes nothing.
   */
  moves?: string
}

export interface DraggableWindow {
  offset: WindowOffset
  isDragging: boolean
  /**
   * True from the moment a press passes DRAG_THRESHOLD until the next click
   * has been suppressed. A handle that is also a button reads this to know
   * the release ends a drag rather than a click.
   */
  didDragRef: React.MutableRefObject<boolean>
  /** Spread onto the drag handle. */
  handleProps: {
    onPointerDown: (event: React.PointerEvent) => void
  }
  reset: () => void
}

/**
 * Pointer-drag for a fixed-position panel.
 *
 * Pointer events rather than mouse events: one code path covers mouse, pen and
 * touch, and setPointerCapture keeps the drag alive when the cursor outruns the
 * handle -- which it will, because a drag is faster than a repaint.
 *
 * The window is clamped so at least KEEP_VISIBLE px of it stays inside the
 * viewport on every edge. A panel dragged fully off screen is not recoverable
 * except by knowing the reset gesture exists, and a control that can be lost
 * is a control that will be.
 */
export function useDraggableWindow(
  enabled: boolean,
  options: DraggableOptions = {},
): DraggableWindow {
  const { moves } = options
  const [offset, setOffset] = useState<WindowOffset>(ZERO)
  const [isDragging, setIsDragging] = useState(false)

  // The drag's own bookkeeping. Refs, not state: these change on every
  // pointermove and none of them should cause a render on its own.
  const originRef = useRef({ pointerX: 0, pointerY: 0, offsetX: 0, offsetY: 0 })
  const elementRef = useRef<HTMLElement | null>(null)
  const didDragRef = useRef(false)

  const clamp = useCallback(
    (next: WindowOffset): WindowOffset => {
      const el = elementRef.current
      if (!el) return next

      // getBoundingClientRect already includes the current transform, so undo
      // it to get where CSS alone would put the window.
      const rect = el.getBoundingClientRect()
      return clampOffset(
        next,
        { left: rect.left - offset.x, top: rect.top - offset.y, width: rect.width },
        { width: window.innerWidth, height: window.innerHeight },
      )
    },
    [offset.x, offset.y],
  )

  const onPointerDown = useCallback(
    (event: React.PointerEvent) => {
      if (!enabled) return
      // Left button only, and never a drag that starts on a control: the
      // header carries "Yeni sohbet" and the minimize button, and a drag
      // beginning on either of those is a click the operator meant.
      if (event.button !== 0) return

      const handle = event.currentTarget as HTMLElement

      if (!shouldStartDrag(event.target as Element, handle)) return
      // The handle moves itself unless the caller named an ancestor.
      elementRef.current = moves ? handle.closest(moves) : handle
      if (!elementRef.current) return

      didDragRef.current = false

      originRef.current = {
        pointerX: event.clientX,
        pointerY: event.clientY,
        offsetX: offset.x,
        offsetY: offset.y,
      }
      handle.setPointerCapture(event.pointerId)
      setIsDragging(true)
    },
    [enabled, moves, offset.x, offset.y],
  )

  // Move and release are bound to the window rather than to the handle so a
  // pointer that leaves the handle mid-drag still reaches them. The listeners
  // exist only while a drag is in flight.
  useEffect(() => {
    if (!isDragging) return

    const onMove = (event: PointerEvent) => {
      const origin = originRef.current
      const dx = event.clientX - origin.pointerX
      const dy = event.clientY - origin.pointerY

      // Below the threshold this is still a click that has not been released.
      if (!didDragRef.current && Math.hypot(dx, dy) < DRAG_THRESHOLD) return
      didDragRef.current = true

      setOffset(clamp({ x: origin.offsetX + dx, y: origin.offsetY + dy }))
    }
    const onUp = () => setIsDragging(false)

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
  }, [clamp, isDragging])

  /**
   * Re-clamp when the viewport shrinks.
   *
   * A window dragged to the right edge of a wide window is off screen after
   * the browser is made narrow, and nothing else would bring it back.
   */
  useEffect(() => {
    const onResize = () => setOffset((current) => clamp(current))
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [clamp])

  const reset = useCallback(() => setOffset(ZERO), [])

  return { offset, isDragging, didDragRef, handleProps: { onPointerDown }, reset }
}
