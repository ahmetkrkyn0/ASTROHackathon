import { StressTestPanel } from './StressTestPanel'
import { useStressTest } from './useStressTest'

/** SHERPA Monte Carlo stress test (B5), in the systems drawer. */
export function StressTest() {
  const { job, start, cancel, canRun, runs } = useStressTest()

  return (
    <section className="rail-section">
      <p className="panel-kicker">Monte Carlo Stress Test</p>
      <StressTestPanel job={job} start={start} cancel={cancel} canRun={canRun} runs={runs} />
    </section>
  )
}
