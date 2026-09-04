import type { LayerManifestEntry, Validity } from '../../net/types'
import './layer-provenance.css'

const LABEL: Record<Validity, string> = {
  MEASURED: 'Measured',
  MODEL: 'Modelled',
  DERIVED: 'Derived',
  SYNTHETIC: 'Synthetic',
}

const EXPLANATION: Record<Validity, string> = {
  MEASURED: 'Instrument data. This layer is observation, not inference.',
  MODEL: 'Produced by a physical model fitted to this site.',
  DERIVED: 'Computed from a measured layer. Inherits its errors.',
  SYNTHETIC: 'Stand-in values. Not tied to this site’s real conditions.',
}

function formatRange(entry: LayerManifestEntry): string {
  // min and max are null when the layer holds no finite value
  // (terrain.py:262-266). An empty range is reported as unknown, never 0.
  if (entry.min === null || entry.max === null) return 'unknown'
  const units = entry.units ? ` ${entry.units}` : ''
  return `${entry.min.toFixed(2)} – ${entry.max.toFixed(2)}${units}`
}

export function LayerProvenancePanel({
  layerName,
  entry,
  loading,
  error,
}: {
  layerName: string
  entry: LayerManifestEntry | null
  loading: boolean
  error: string | null
}) {
  if (loading) {
    return <p className="lp-provenance-note">Reading layer provenance…</p>
  }
  if (error) {
    return <p className="lp-provenance-note lp-provenance-warn">{error}</p>
  }
  if (!entry) {
    return (
      <p className="lp-provenance-note">
        No manifest entry for <code>{layerName}</code>.
      </p>
    )
  }

  // validity is null when the grid metadata carried no label. Saying
  // "unknown" is the honest answer; assuming MEASURED would be a claim.
  const validity = entry.validity
  const tone = validity ? validity.toLowerCase() : 'unknown'

  return (
    <div className="lp-provenance-card">
      <div className="lp-provenance-head">
        <code className="lp-provenance-name">{layerName}</code>
        <span className={`lp-provenance-badge lp-provenance-${tone}`}>
          {validity ? LABEL[validity] : 'Unknown'}
        </span>
      </div>

      <p className="lp-provenance-why">
        {validity ? EXPLANATION[validity] : 'This layer carries no provenance label.'}
      </p>

      {entry.description ? (
        <p className="lp-provenance-desc">{entry.description}</p>
      ) : null}

      <dl className="lp-provenance-facts">
        <div>
          <dt>Range</dt>
          <dd>{formatRange(entry)}</dd>
        </div>
        <div>
          <dt>No-data cells</dt>
          <dd>{entry.nodata.toLocaleString()}</dd>
        </div>
      </dl>
    </div>
  )
}
