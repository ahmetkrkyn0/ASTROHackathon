import type { ProfileResult } from '../../net/types'
import type { OverlayCommand } from '../../overlay/types'

/** One polyline per profile, in the colour the backend assigned it. */
export function profileOverlays(results: ProfileResult[]): OverlayCommand[] {
  return results
    .filter((result) => !result.error && result.path_pixels.length > 1)
    .map((result) => ({
      kind: 'polyline' as const,
      id: `profile-${result.profile_id}`,
      points: result.path_pixels.map(([row, col]) => ({ row, col })),
      style: { color: result.color, widthPx: 2, opacity: 0.85 },
    }))
}
