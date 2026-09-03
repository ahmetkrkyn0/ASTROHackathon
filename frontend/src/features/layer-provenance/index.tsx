import { useMission } from '../../mission/MissionContext'
import { LayerProvenancePanel } from './LayerProvenancePanel'
import { LAYER_FOR_VIEW, useLayerProvenance } from './useLayerProvenance'

export function LayerProvenance() {
  const { activeLayer } = useMission()
  const { manifest, loading, error } = useLayerProvenance()

  const layerName = LAYER_FOR_VIEW[activeLayer]
  const entry = manifest?.layers[layerName] ?? null

  return (
    <section className="rail-section">
      <p className="panel-kicker">Layer Provenance</p>
      <LayerProvenancePanel
        layerName={layerName}
        entry={entry}
        loading={loading}
        error={error}
      />
    </section>
  )
}
