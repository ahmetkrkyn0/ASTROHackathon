import { useCallback, useMemo } from 'react'
import { useMission } from '../../mission/MissionContext'
import { useAnalysisJob } from '../analysis-job'
import { runRiskSweep, type RiskSweepBody, type RiskSweepResponse } from '../../net/riskSweep'

/** The alphas the contract's own summary spans: nominal, mild, strong, extreme. */
const ALPHAS = [0.5, 0.9, 0.99]

export function useRiskSweep() {
  const { start, goal, roverId, weights, routeIdentity } = useMission()

  const body = useMemo<RiskSweepBody | null>(() => {
    if (!start || !goal) return null
    return {
      start: { row: start[0], col: start[1] },
      goal: { row: goal[0], col: goal[1] },
      rover_id: roverId,
      weights: weights as unknown as Record<string, number>,
      alphas: ALPHAS,
    }
  }, [goal, roverId, start, weights])

  const run = useCallback(
    (signal: AbortSignal): Promise<RiskSweepResponse> => {
      if (!body) return Promise.reject(new Error('Pick a start and a goal first.'))
      return runRiskSweep(body, signal)
    },
    [body],
  )

  const { job, start: begin, cancel } = useAnalysisJob<RiskSweepResponse>({
    run,
    identity: routeIdentity,
    endpoint: 'analysis',
  })

  return { job, start: begin, cancel, canRun: body !== null, alphas: ALPHAS }
}
