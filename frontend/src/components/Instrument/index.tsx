import type { ReactNode } from 'react'
import './instrument.css'

/**
 * The console's instrument vocabulary.
 *
 * The panels added across F1-F3 each invented their own way of showing a
 * figure, a bar and a section rule, and the result read as a settings page:
 * every number the same size, every rule the same weight, nothing to look at
 * first. A mission console does not look like that because it has a hierarchy
 * -- one figure per block is the reading, the rest is context for it.
 *
 * Three pieces, used by every panel here, so they read as one instrument
 * rather than seven arrangements of the same tokens:
 *
 *   Readout   the figure a block exists to show, at display size in mono
 *   Meter     a bar with a real axis: ticks, a baseline, and labelled ends
 *   Field     the small label/value pair everything else is made of
 *
 * Tone is semantic and is spent only where it means something. `ok`, `warn`
 * and `bad` carry safety meaning; `data` is the neutral instrument colour for
 * a measurement that is not a verdict.
 */

export type Tone = 'data' | 'ok' | 'warn' | 'bad' | 'muted'

/** The figure a block exists to show. One per block, or it is not a headline. */
export function Readout({
  label,
  value,
  unit,
  sub,
  tone = 'data',
}: {
  label: string
  value: ReactNode
  unit?: string
  /** One line under the figure, for what qualifies it. */
  sub?: ReactNode
  tone?: Tone
}) {
  return (
    <div className={`lp-io-readout is-${tone}`}>
      <span className="lp-io-label">{label}</span>
      <span className="lp-io-value">
        {value}
        {unit ? <i className="lp-io-unit">{unit}</i> : null}
      </span>
      {sub ? <span className="lp-io-sub">{sub}</span> : null}
    </div>
  )
}

/**
 * A bar with an axis rather than a bar on its own.
 *
 * `origin` places zero: 0 draws a left-anchored bar, 0.5 a diverging one. The
 * ticks are what make it readable as a measurement -- a coloured rectangle
 * with no scale is a decoration, and the panels had several.
 */
export function Meter({
  fraction,
  origin = 0,
  tone = 'data',
  ticks = 4,
  low,
  high,
  marker,
  clamped,
}: {
  /** Signed, -1..1. Negative only means anything when origin is 0.5. */
  fraction: number
  origin?: 0 | 0.5
  tone?: Tone
  ticks?: number
  low?: string
  high?: string
  /** A second value on the same scale, 0..1 across the track. */
  marker?: number
  clamped?: boolean
}) {
  const magnitude = Math.min(Math.abs(fraction), 1)
  const width = origin === 0.5 ? magnitude * 50 : magnitude * 100
  const negative = fraction < 0

  return (
    <div className="lp-io-meter">
      <div className={`lp-io-track is-${tone}`}>
        <span className="lp-io-ticks" aria-hidden="true">
          {Array.from({ length: ticks - 1 }, (_, i) => (
            <i key={i} style={{ left: `${((i + 1) / ticks) * 100}%` }} />
          ))}
        </span>
        {origin === 0.5 ? <span className="lp-io-origin" aria-hidden="true" /> : null}
        <span
          className={`lp-io-fill ${negative ? 'is-negative' : ''} ${clamped ? 'is-clamped' : ''}`}
          style={
            origin === 0.5
              ? negative
                ? { right: '50%', width: `${width}%` }
                : { left: '50%', width: `${width}%` }
              : { left: 0, width: `${width}%` }
          }
        />
        {marker !== undefined ? (
          <span className="lp-io-marker" style={{ left: `${marker * 100}%` }} aria-hidden="true" />
        ) : null}
      </div>
      {low || high ? (
        <div className="lp-io-scale">
          <span>{low}</span>
          <span>{high}</span>
        </div>
      ) : null}
    </div>
  )
}

/** The label/value pair everything that is not a headline is made of. */
export function Field({
  label,
  value,
  hint,
  tone = 'data',
}: {
  label: string
  value: ReactNode
  hint?: string
  tone?: Tone
}) {
  return (
    <div className={`lp-io-field is-${tone}`}>
      <dt>{label}</dt>
      <dd>{value}</dd>
      {hint ? <span className="lp-io-hint">{hint}</span> : null}
    </div>
  )
}

/** A row of Fields on one baseline. */
export function FieldRow({ children }: { children: ReactNode }) {
  return <dl className="lp-io-fields">{children}</dl>
}

/** A labelled rule, the way a schematic separates two things. */
export function Divide({ label }: { label: string }) {
  return (
    <div className="lp-io-divide">
      <span>{label}</span>
    </div>
  )
}
