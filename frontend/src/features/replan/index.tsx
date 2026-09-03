import { ReplanPanel } from './ReplanPanel'
import { useReplan } from './useReplan'

export function Replan() {
  const state = useReplan()
  return (
    <section className="rail-section">
      <p className="panel-kicker">Replan Triggers</p>
      <ReplanPanel {...state} />
    </section>
  )
}
