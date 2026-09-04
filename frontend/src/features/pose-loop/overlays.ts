import { metresToPixel, type GridFrame } from '../../grid/geo'
import type { OverlayLayer } from '../../overlay/types'
import type { Corridor, PoseResponse } from '../../net/types'

/**
 * The pose, and the line from it to the corridor centreline.
 *
 * along_track_m locates the projection along the corridor; converting it to
 * a waypoint index needs the corridor's own spacing, so the nearest
 * waypoint is found by distance instead -- fewer assumptions, same picture.
 */
export function poseOverlays(
  pose: { x_m: number; y_m: number } | null,
  result: PoseResponse | null,
  corridor: Corridor | null,
  frame: GridFrame | null,
): OverlayLayer[] {
  if (!pose || !frame) return []

  const posePixel = metresToPixel(pose.x_m, pose.y_m, frame)
  const layers: OverlayLayer[] = [
    {
      kind: 'points',
      id: 'pose-current',
      points: [posePixel],
      style: {
        // Red when the pose broke the corridor, amber when localization is
        // too uncertain to trust it, white otherwise.
        color:
          result?.recommended_action === 'stop_and_localize'
            ? '#fbbf24'
            : result && result.fired_triggers.length > 0
              ? '#f87171'
              : '#f8fafc',
        radius: 5,
      },
    },
  ]

  if (corridor && result) {
    let nearest = corridor.waypoints[0]
    let best = Number.POSITIVE_INFINITY
    for (const [x, y] of corridor.waypoints) {
      const distance = Math.hypot(x - pose.x_m, y - pose.y_m)
      if (distance < best) {
        best = distance
        nearest = [x, y]
      }
    }
    layers.push({
      kind: 'polyline',
      id: 'pose-deviation',
      points: [posePixel, metresToPixel(nearest[0], nearest[1], frame)],
      style: { color: '#fbbf24', lineWidth: 1.5, dash: [4, 3], opacity: 0.9 },
    })
  }

  return layers
}
