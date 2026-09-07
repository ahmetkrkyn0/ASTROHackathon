import { useMission } from '../../mission/MissionContext'
import { DemUncertaintyCard } from './DemUncertaintyCard'
import { LayerProvenancePanel } from './LayerProvenancePanel'
import { UncertaintySeriesCard } from './UncertaintySeriesCard'
import { LAYER_FOR_VIEW, useLayerProvenance } from './useLayerProvenance'

export function LayerProvenance() {
  const { activeViewMode } = useMission()
  const { manifest, loading, error } = useLayerProvenance()

  const layerName = LAYER_FOR_VIEW[activeViewMode]
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
      {/*
        Present only where the DEM clone cache exists -- which is the same
        condition under which the four uncertainty layers appear in the overlay
        list. No cache, no card, and nothing claiming an ensemble that is not
        there.
      */}
      {manifest?.dem_uncertainty && (
        <>
          <DemUncertaintyCard pedigree={manifest.dem_uncertainty} />
          {/* The same ensemble in time rather than in space. It renders
              nothing until it has been asked and answered, so a deployment
              with no clone horizons adds no empty card. */}
          <UncertaintySeriesCard />
        </>
      )}
    </section>
  )
}
