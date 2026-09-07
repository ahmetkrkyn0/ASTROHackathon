import type { AnalysisLayersState } from './useAnalysisLayers'
import { capabilityMessage, capabilityValue } from '../../mission/capability'

/**
 * The overlay toggle list, in the map dock beside the layer picker.
 *
 * Deliberately not a permanent rail card. This cockpit has been shrinking its
 * dashboard rather than growing it, and the theme rule for this integration is
 * that a new feature does not open a card by default. So: a dock control that
 * is one line until opened, and evidence panels live in the systems drawer.
 *
 * Every state is stated, none is hidden. A layer whose cache is missing stays
 * in the list, disabled, with the backend's own sentence and the command that
 * would produce it -- an absent capability that silently disappears from the
 * UI is indistinguishable from a capability that never existed.
 */
export function AnalysisLayersPanel({ entries, toggle }: AnalysisLayersState) {
  return (
    <div className="lp-analysis-layers">
      <div className="lp-analysis-header">
        <span className="lp-layer-label-hint">Analysis overlays</span>
      </div>

      <div className="lp-analysis-items">
        {entries.map(({ spec, enabled, capability }) => {
          const message = capabilityMessage(capability)
          const isUnavailable =
            capability.status === 'unavailable' || capability.status === 'unsupported'
          const isError = capability.status === 'error'
          const isLoading = capability.status === 'loading'
          const remedy = capability.status === 'unavailable' ? capability.remedy : null
          // The layer's own provenance, from X-Layer-Validity on the payload we
          // actually received -- not from the table above. Two layers here mean
          // the same physical quantity and carry different labels
          // (`slope_sigma` DERIVED, `slope_sigma_nasa` MODEL), which is the
          // whole reason they are separate entries; reading the label off the
          // response is what keeps that honest.
          const validity = capabilityValue(capability)?.validity ?? null

          return (
            <div
              key={spec.id}
              className={`lp-analysis-item ${enabled ? 'is-on' : ''} ${
                isUnavailable ? 'is-unavailable' : ''
              } ${isError ? 'is-error' : ''}`}
            >
              <button
                type="button"
                className="lp-analysis-toggle"
                onClick={() => toggle(spec.id)}
                aria-pressed={enabled}
              >
                <span className="lp-analysis-check" aria-hidden="true">
                  {enabled ? '◼' : '◻'}
                </span>
                <span className="lp-analysis-text">
                  <span className="lp-analysis-name">
                    {spec.label}
                    {validity && (
                      <span
                        className={`lp-analysis-validity lp-validity-${validity.toLowerCase()}`}
                      >
                        {validity}
                      </span>
                    )}
                    {isLoading && <span className="lp-analysis-status"> loading…</span>}
                  </span>
                  <span className="lp-analysis-blurb">{spec.blurb}</span>
                </span>
              </button>

              {/* The claim boundary, on screen rather than in a tooltip. */}
              <p className="lp-analysis-limit">{spec.limit}</p>

              {/*
                A missing cache is not a failure, and it does not read like one:
                no error styling, the backend's own sentence, and the command
                that fixes it. An error is styled as an error because something
                is genuinely wrong.
              */}
              {message && (
                <p className={`lp-analysis-note ${isError ? 'is-error' : ''}`}>
                  {isUnavailable ? 'Not available on this deployment. ' : ''}
                  {message}
                </p>
              )}
              {remedy && <code className="lp-analysis-remedy">{remedy}</code>}
            </div>
          )
        })}
      </div>
    </div>
  )
}
