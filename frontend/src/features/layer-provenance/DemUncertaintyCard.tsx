import type { DemUncertaintyPedigree } from '../../net/types'

/**
 * Where the four uncertainty layers came from, and what they do not cover.
 *
 * Sits under the layer-provenance card because it answers the same question
 * one level up: that card says what a layer is, this says what the ensemble
 * behind four of them was.
 *
 * The three `*_held_fixed` flags are the reason this is worth screen space.
 * NASA's clones vary the terrain; our pipeline did not re-derive the thermal
 * field, the far-field horizon or Earth visibility for each one. So an
 * uncertainty band read off these layers is a band over **terrain alone**, and
 * an operator who reads it as total mission uncertainty is reading it wrong.
 * That limit is invisible in the layers themselves.
 */
export function DemUncertaintyCard({ pedigree }: { pedigree: DemUncertaintyPedigree }) {
  const heldFixed = [
    pedigree.thermal_field_held_fixed ? 'thermal field' : null,
    pedigree.far_field_held_fixed ? 'far-field horizon' : null,
    pedigree.earth_visibility_cloned ? null : 'Earth visibility',
  ].filter((entry): entry is string => entry !== null)

  return (
    <div className="lp-provenance-card lp-dem-card">
      <div className="lp-provenance-head">
        <code className="lp-provenance-name">DEM uncertainty</code>
        {/*
          `synthetic` is a real state and it is called out, not smoothed over:
          a stand-in ensemble carries none of NASA's authority and the layers
          drawn from it would otherwise look identical.
        */}
        <span
          className={`lp-provenance-badge ${
            pedigree.model === 'nasa_pgda_clones'
              ? 'lp-provenance-model'
              : 'lp-provenance-synthetic'
          }`}
        >
          {pedigree.model === 'nasa_pgda_clones' ? 'NASA clones' : pedigree.model}
        </span>
      </div>

      <dl className="lp-provenance-facts lp-dem-facts">
        <div>
          <dt>Clones</dt>
          <dd>{pedigree.n_clones}</dd>
        </div>
        <div>
          <dt>Site</dt>
          <dd>{pedigree.site}</dd>
        </div>
        <div>
          <dt>Near-field fill</dt>
          <dd>{pedigree.near_range_m.toLocaleString()} m</dd>
        </div>
        {typeof pedigree.slope_max_deg === 'number' && (
          <div>
            <dt>Slope limit used</dt>
            <dd>{pedigree.slope_max_deg}°</dd>
          </div>
        )}
      </dl>

      {/* What the ensemble did not vary. The layers cannot say this. */}
      {heldFixed.length > 0 && (
        <p className="lp-provenance-why">
          Held fixed across every clone: {heldFixed.join(', ')}. A band read off these
          layers is uncertainty in the terrain, not in the mission.
        </p>
      )}

      <p className="lp-provenance-desc">
        {pedigree.reference}{' '}
        <a href={pedigree.product_url} target="_blank" rel="noreferrer">
          PGDA product
        </a>
      </p>
    </div>
  )
}
