import { MissionValidationPanel } from './MissionValidationPanel'
import { useMissionValidation } from './useMissionValidation'

export function MissionValidation() {
  const state = useMissionValidation()
  return (
    <section className="rail-section">
      <p className="panel-kicker">Reality Check</p>
      <MissionValidationPanel {...state} />
    </section>
  )
}
