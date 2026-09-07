import { Icon } from '../../components/Fleet/SpecIcons'
import { Meter } from '../../components/Instrument'
import {
  MOONPLANBENCH_CLAIM,
  MOONPLANBENCH_SOURCE,
  MOONPLANBENCH_VARIANTS,
} from './moonPlanBench'
import './benchmark.css'

/**
 * MoonPlanBench (D2), in the systems drawer.
 *
 * Offline evidence, not a runtime feature: there is no endpoint and the plan
 * forbids inventing one. It renders the same figures whatever the mission is,
 * which is what an external validation result is.
 *
 * The two success rates are drawn as one bar with two marks rather than as two
 * numbers, because the whole point is the gap between them and what causes it.
 * LunaPath's row is never shown without the benchmark-model row beside it.
 */
export function Benchmark() {
  return (
    <section className="rail-section">
      <p className="panel-kicker">External Benchmark</p>

      <div className="lp-bm">
        <p className="lp-bm-lede">
          Independent slope-thresholded occupancy benchmark, {MOONPLANBENCH_SOURCE.maps} maps.
        </p>

        <ul className="lp-bm-list">
          {MOONPLANBENCH_VARIANTS.map((variant) => (
            <li key={variant.label} className="lp-bm-row">
              <div className="lp-bm-head">
                <span className="lp-bm-label">{variant.label.replace('MoonPlanBench-', '')}°</span>
                <span className="lp-bm-rate">
                  <b>{(variant.lunapathSuccess * 100).toFixed(1)}%</b>
                  <span className="lp-bm-vs">
                    vs {(variant.benchmarkModelSuccess * 100).toFixed(0)}%
                  </span>
                </span>
              </div>

              {/* One track, two marks: the gap IS the finding, and two
                  separate numbers would let either be quoted alone. The bar is
                  LunaPath under its own safety rule; the marker is the same
                  benchmark under the model that allows corner-cutting. */}
              <Meter
                fraction={variant.lunapathSuccess}
                tone={variant.lunapathSuccess >= variant.benchmarkModelSuccess ? 'ok' : 'data'}
                ticks={4}
                marker={variant.benchmarkModelSuccess}
              />

              <p className="lp-bm-why">
                {variant.cornerCutOnlyMaps > 0
                  ? `${variant.cornerCutOnlyMaps} of ${variant.totalMaps} maps are connected only by cutting a corner between two blocked cells.`
                  : 'No map depends on cutting a corner; the two models agree.'}
              </p>
            </li>
          ))}
        </ul>

        {/* The strongest honest claim available, and it is about agreement
            rather than about winning. */}
        <p className="lp-bm-match">
          <Icon name="check" />
          <span>
            Under the benchmark’s own motion model, LunaPath reproduces the paper’s
            shortest-path lengths exactly ({MOONPLANBENCH_VARIANTS
              .map((v) => v.benchmarkModelLength.toFixed(2))
              .join(' · ')}).
          </span>
        </p>

        <p className="lp-bm-claim">{MOONPLANBENCH_CLAIM}</p>

        <p className="lp-bm-source">
          <Icon name="evidence" />
          {MOONPLANBENCH_SOURCE.report} · {MOONPLANBENCH_SOURCE.paper} (quoted)
        </p>
      </div>
    </section>
  )
}
