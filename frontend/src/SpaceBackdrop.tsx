import { useEffect, useRef, useState } from 'react'

/**
 * The lunar clip that runs underneath the whole app, plus its vignette.
 *
 * Mounted once, for the life of the session, and never remounted between
 * phases -- swapping it in and out would restart playback and re-buffer on
 * every transition, which is exactly the seam the landing -> cinematic ->
 * deck sequence is trying to hide. Phases change `stage` and `frozen`; the
 * element itself stays put.
 *
 * Decoration only: `aria-hidden`, and transparent to the pointer so the
 * console above owns every interaction.
 *
 * The clip is optional and gitignored. A missing file is not a failure
 * state -- the poster is `starimg.jpeg`, so a fresh clone still looks
 * deliberate. Same for `prefers-reduced-motion`: the video is never mounted
 * and the poster stands in.
 */

const CLIP_SRC = '/videos/moon-backdrop-1080.mp4'

/** How much of the clip each phase lets through. */
const STAGE_OPACITY = {
  /** Behind the landing page, which has its own moon to stay legible over. */
  ambient: 0.4,
  /** The transition beat: the clip IS the screen. */
  feature: 1,
  /** Behind the console, where panels and terrain are the subject. */
  deck: 0.55,
} as const

export type BackdropStage = keyof typeof STAGE_OPACITY

interface Props {
  stage: BackdropStage
  /** Hold the current frame -- set once route planning starts. */
  frozen?: boolean
}

export default function SpaceBackdrop({ stage, frozen = false }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [motionOk, setMotionOk] = useState(true)

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const apply = () => setMotionOk(!query.matches)
    apply()
    query.addEventListener('change', apply)
    return () => query.removeEventListener('change', apply)
  }, [])

  useEffect(() => {
    const video = videoRef.current
    if (!video || !motionOk) return

    if (frozen) {
      // Pause, not unmount: the frame stays on screen as a still.
      video.pause()
      return
    }
    // Autoplay can still be refused (a background tab, a policy that
    // muted-inline does not satisfy). The poster is already behind the
    // element, so a rejection needs catching but not handling.
    video.play().catch(() => {})
  }, [frozen, motionOk])

  return (
    <div
      className={`space-backdrop space-backdrop--${stage}`}
      style={{ '--backdrop-opacity': STAGE_OPACITY[stage] } as React.CSSProperties}
      aria-hidden="true"
    >
      {motionOk ? (
        <video
          ref={videoRef}
          className="space-backdrop-media"
          src={CLIP_SRC}
          poster="/starimg.jpeg"
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
        />
      ) : (
        <img className="space-backdrop-media" src="/starimg.jpeg" alt="" />
      )}

      {/* Vertical vignette: keeps the topbar and status strip legible without
          hiding the middle of the frame, where the terrain sits. Lifts during
          the transition beat, when the clip is meant to be the subject. */}
      <div className="space-backdrop-vignette bg-gradient-to-t from-black/80 via-black/40 to-black/80" />

      {/* Sun grazing the horizon. At this latitude it never gets far above
          it, which is the whole reason the shadow and thermal layers exist. */}
      <div className="space-backdrop-terminator" />
    </div>
  )
}
