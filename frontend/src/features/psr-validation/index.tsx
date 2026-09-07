import { useEffect, useState } from 'react'

import { fetchPsrValidation, type PsrValidation } from '../../net/analysis'
import { isDataUnavailable } from '../../net/errors'
import {
  CAPABILITY_LOADING,
  capabilityFromError,
  capabilityReady,
  type Capability,
} from '../../mission/capability'
import './psr-validation.css'

/**
 * How far our shadow model and NASA's measured PSR mask actually agree.
 *
 * A validation card, in the Systems & Evidence drawer rather than the rails.
 * It is not part of placing or reading a route, and the theme rule for this
 * integration is that a new feature does not open a permanent card.
 *
 * The point of the panel is the number it could fail. Jaccard on this window
 * is 0.61: our `shadow_ratio >= 0.99` cells and NASA's mask agree on about
 * three fifths of their union. Publishing that is what makes the roughness and
 * PSR overlays evidence rather than decoration -- a validation panel that can
 * only ever show agreement is not validating anything.
 */
export function PsrValidationPanel() {
  const [state, setState] = useState<Capability<PsrValidation>>(CAPABILITY_LOADING)

  useEffect(() => {
    const controller = new AbortController()
    fetchPsrValidation(0.99, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return
        setState(capabilityReady(response))
      })
      .catch((error: unknown) => {
        const next = capabilityFromError(error, {
          isDataUnavailable: isDataUnavailable(error),
          signal: controller.signal,
        })
        if (next) setState(next)
      })
    return () => controller.abort()
  }, [])

  if (state.status === 'loading') {
    return (
      <section className="rail-section">
        <p className="panel-kicker">PSR validation</p>
        <p className="psr-note">Loading…</p>
      </section>
    )
  }

  // A missing cache is not a failure. The backend names the script; showing it
  // is more useful than any wording of our own, and hiding the panel entirely
  // would make an absent capability look like one that never existed.
  if (state.status === 'unavailable' || state.status === 'unsupported') {
    return (
      <section className="rail-section">
        <p className="panel-kicker">PSR validation</p>
        <p className="psr-note">{state.reason}</p>
        {state.status === 'unavailable' && state.remedy && (
          <code className="psr-remedy">{state.remedy}</code>
        )}
      </section>
    )
  }

  if (state.status === 'error') {
    return (
      <section className="rail-section">
        <p className="panel-kicker">PSR validation</p>
        <p className="psr-note is-error">{state.error.message}</p>
      </section>
    )
  }

  if (state.status === 'idle') return null

  const data = state.value
  const pct = (value: number) => `${(value * 100).toFixed(1)}%`

  return (
    <section className="rail-section">
      <p className="panel-kicker">PSR validation</p>

      <p className="psr-headline">
        Our shadow model against{' '}
        <a href={data.product_url} target="_blank" rel="noreferrer">
          {data.product}
        </a>
        , at <span className="psr-mono">shadow_ratio ≥ {data.threshold}</span>.
      </p>

      <dl className="psr-facts">
        <div>
          <dt>Jaccard</dt>
          <dd className="psr-mono">{data.jaccard.toFixed(3)}</dd>
        </div>
        <div>
          <dt>PSR recall</dt>
          <dd className="psr-mono">{pct(data.psr_recall)}</dd>
        </div>
        <div>
          <dt>Dark precision</dt>
          <dd className="psr-mono">{pct(data.dark_precision)}</dd>
        </div>
        <div>
          <dt>PSR cells</dt>
          <dd className="psr-mono">
            {data.n_psr.toLocaleString()} of {data.n_cells.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt>Median coldest, inside</dt>
          <dd className="psr-mono">{data.thermal_min_median_inside_psr.toFixed(1)} °C</dd>
        </div>
        <div>
          <dt>Median coldest, outside</dt>
          <dd className="psr-mono">{data.thermal_min_median_outside_psr.toFixed(1)} °C</dd>
        </div>
      </dl>

      {/* Both quoted, not paraphrased. The backend owns the claim it is making
          about its own product, and a reworded claim is a different claim. */}
      <p className="psr-note">{data.reading}</p>
      <p className="psr-note psr-claim">{data.claim}</p>

      <p className="psr-provenance">
        {Object.entries(data.validity).map(([layer, validity]) => (
          <span key={layer} className="psr-provenance-item">
            <span className="psr-mono">{layer}</span> {validity}
          </span>
        ))}
      </p>
    </section>
  )
}

export default PsrValidationPanel
