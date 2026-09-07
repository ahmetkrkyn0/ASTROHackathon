/**
 * How far the planned-route ribbon floats above the surface it describes.
 *
 * The route is painted on the ground, so ideally it would sit exactly on the
 * mesh. It cannot: at orbit distance a coplanar ribbon z-fights the terrain
 * into a flickering dashed mess. The fix is to lift it -- but "just clear of
 * the ground" is a different number at each of the two scales this scene is
 * viewed at, and using one number for both is what put the route on the
 * ceiling.
 *
 *   orbit -- roughly 2.5 km out, terrain vertically exaggerated. Several
 *            metres is well under a pixel from there and comfortably beats
 *            depth-buffer precision.
 *   FPS   -- the eye sits at 1.6 m. The orbit offset put the ribbon 2.4 m
 *            ABOVE the driver's eyeline, so the route the rover is meant to
 *            be driving along became a glowing green ceiling across the
 *            windscreen. On the surface the lift only has to beat depth
 *            precision, which centimetres do.
 */
export function ribbonSurfaceOffsetM(cameraMode: 'fps' | 'orbit'): number {
  return cameraMode === 'fps' ? 0.15 : 4
}

/** Ribbon height in scene units for one waypoint. `verticalScale` is the
 *  terrain mesh's own exaggeration, so the ribbon rises and falls with the
 *  ground rather than drifting away from it when the scale changes. */
export function ribbonHeight({
  altitudeM,
  minM,
  verticalScale,
  cameraMode,
}: {
  altitudeM: number | null
  minM: number
  verticalScale: number
  cameraMode: 'fps' | 'orbit'
}): number {
  return ((altitudeM ?? minM) - minM) * verticalScale + ribbonSurfaceOffsetM(cameraMode)
}

/** Rover chassis width, from the box geometry TerrainCanvas3D builds it with. */
export const ROVER_CHASSIS_WIDTH_M = 1.45

/**
 * Half-width of the route ribbon, in metres.
 *
 * On the surface the ribbon has to stay narrower than the vehicle. A band
 * wider than the chassis swallows the rover whole -- the thing the route
 * exists to guide vanishes inside the guide -- so the route reads as a marked
 * lane the rover straddles and remains visible on top of.
 *
 * Orbit inverts the constraint: at 2.5 km a lane that narrow is sub-pixel and
 * the route disappears for the opposite reason, so it widens to something
 * that survives the distance without becoming the widest thing on the map.
 */
export function ribbonHalfWidthM(cameraMode: 'fps' | 'orbit'): number {
  return cameraMode === 'fps' ? 0.45 : 2.2
}
