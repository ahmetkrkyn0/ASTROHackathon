import { postJson } from './client'
import type { PoseResponse } from './types'

/**
 * Which estimator produced the pose. Required, and not decorative: a
 * dead-reckoned pose and an absolute fix carry different trust, and
 * localization_budget uses this to decide whether a source resets
 * accumulated drift or merely slows it (pose.py:50-62).
 */
export type PoseSource =
  | 'dead_reckoning'
  | 'visual_odometry'
  | 'lidar_odometry'
  | 'skyline_fix'
  | 'sun_sensor'

/** skyline_fix and sun_sensor fix against an external absolute reference. */
export const ABSOLUTE_SOURCES: PoseSource[] = ['skyline_fix', 'sun_sensor']

export interface PoseEstimateBody {
  /** Projected CRS easting, metres -- the frame the corridor uses. */
  x_m: number
  /** Projected CRS northing, metres. */
  y_m: number
  /** Grid azimuth: 0 = grid north (decreasing row), 90 = grid east, clockwise. */
  heading_deg: number
  /** 1-sigma horizontal position uncertainty, metres. */
  covariance_m: number
  /** 1-sigma heading uncertainty, degrees. */
  heading_covariance_deg: number
  timestamp_utc: string
  source: PoseSource
  /**
   * Distance the estimator CLAIMS to have covered, measured from the start
   * of the ACTIVE corridor -- reset it whenever a new plan is issued. The
   * gap between this and actual advance along the corridor is slip.
   */
  distance_travelled_m: number
}

export interface PoseBody {
  pose: PoseEstimateBody
  /** Telemetry the pose cannot supply -- same shape as ReplanRequest.state. */
  state?: Record<string, number>
  /** Echo corridor_fix.along_track_m from the previous response. */
  previous_along_track_m?: number
  /** Echo the corridor_id from the /api/plan that produced this route. */
  corridor_id?: string
}

export async function submitPose(
  body: PoseBody,
  signal?: AbortSignal,
): Promise<PoseResponse> {
  return postJson<PoseResponse>('/pose', body, signal)
}
