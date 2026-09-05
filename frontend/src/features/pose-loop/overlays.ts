import { metresToPixel, type GridFrame } from '../../grid/geo'
import type { OverlayCommand } from '../../overlay/types'
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
): OverlayCommand[] {
  if (!pose || !frame) return []

  // Already a fine-grid cell: metresToPixel answers in row/col, which is the
  // only space the overlay contract carries.
  const poseCell = metresToPixel(pose.x_m, pose.y_m, frame)
  const commands: OverlayCommand[] = [
    {
      kind: 'points',
      id: 'pose-current',
      points: [poseCell],
      style: {
        // Red when the pose broke the corridor, amber when localization is
        // too uncertain to trust it, white otherwise.
        color:
          result?.recommended_action === 'stop_and_localize'
            ? '#e3d548'
            : result && result.fired_triggers.length > 0
              ? '#ed4b3d'
              : '#e7eaf1',
        radiusPx: 5,
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
    commands.push({
      kind: 'polyline',
      id: 'pose-deviation',
      points: [poseCell, metresToPixel(nearest[0], nearest[1], frame)],
      // Deviation from the corridor is a caution reading, so it takes the
      // ramp's MEDIUM rather than a copy of the value that used to be there.
      style: { color: '#e3d548', widthPx: 1.5, dash: [4, 3], opacity: 0.9 },
    })
  }

  return commands
}
