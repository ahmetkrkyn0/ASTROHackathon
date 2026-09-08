import { useCallback, useEffect, useState } from 'react'

/**
 * Safari (and older WebKit embeds) still ship the Fullscreen API only under
 * the webkit prefix, so every call site below has to try both spellings.
 * Typed here rather than cast at each use so the fallbacks stay visible.
 */
interface FullscreenElement extends HTMLElement {
  webkitRequestFullscreen?: () => Promise<void> | void
}

interface FullscreenDocument extends Document {
  webkitFullscreenElement?: Element | null
  webkitExitFullscreen?: () => Promise<void> | void
}

function currentFullscreenElement(): Element | null {
  const doc = document as FullscreenDocument
  return doc.fullscreenElement ?? doc.webkitFullscreenElement ?? null
}

/**
 * Drives one element in and out of browser fullscreen.
 *
 * `active` tracks the *browser's* state rather than our own intent, because
 * the user can leave fullscreen by means we never see a click for -- Escape,
 * F11, switching tabs on some platforms. Listening to fullscreenchange is the
 * only way the button's label and the stage's class stay honest when that
 * happens.
 *
 * Returns `supported: false` where the API is missing or blocked by policy
 * (iOS Safari on iPhone, some embedded webviews) so callers can hide the
 * affordance instead of offering a button that silently does nothing.
 */
export function useFullscreen(ref: React.RefObject<HTMLElement | null>) {
  const [active, setActive] = useState(false)

  const supported =
    typeof document !== 'undefined' &&
    Boolean(
      document.fullscreenEnabled ||
        (document as FullscreenDocument).webkitFullscreenElement !== undefined,
    )

  useEffect(() => {
    const sync = () => setActive(currentFullscreenElement() === ref.current)
    document.addEventListener('fullscreenchange', sync)
    document.addEventListener('webkitfullscreenchange', sync)
    // The element may already be fullscreen if this mounted during one.
    sync()
    return () => {
      document.removeEventListener('fullscreenchange', sync)
      document.removeEventListener('webkitfullscreenchange', sync)
    }
  }, [ref])

  const enter = useCallback(async () => {
    const element = ref.current as FullscreenElement | null
    if (!element) return
    try {
      if (element.requestFullscreen) await element.requestFullscreen()
      else if (element.webkitRequestFullscreen) await element.webkitRequestFullscreen()
    } catch {
      // Denied (no user gesture, or a permissions policy). The listener above
      // never fires, so `active` correctly stays false and the button keeps
      // reading "Fullscreen".
    }
  }, [ref])

  const exit = useCallback(async () => {
    const doc = document as FullscreenDocument
    if (!currentFullscreenElement()) return
    try {
      if (doc.exitFullscreen) await doc.exitFullscreen()
      else if (doc.webkitExitFullscreen) await doc.webkitExitFullscreen()
    } catch {
      /* Same reasoning as enter(). */
    }
  }, [])

  const toggle = useCallback(() => {
    if (active) void exit()
    else void enter()
  }, [active, enter, exit])

  return { active, supported, enter, exit, toggle }
}

export default useFullscreen
