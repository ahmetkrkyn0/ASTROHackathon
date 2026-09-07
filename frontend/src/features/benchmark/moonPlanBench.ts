/**
 * MoonPlanBench (D2): LunaPath measured against an external benchmark.
 *
 * NOT A RUNTIME FEATURE. There is no endpoint for this and the plan forbids
 * inventing one -- it is an offline validation artifact, produced by
 * `scripts/moonplanbench_runner.py` and written up in
 * `docs/research/moonplanbench_report.md`. The figures below are transcribed
 * from that report's own tables and change only when the benchmark is re-run.
 *
 * THE HEADLINE IS NOT "100%", and it is not allowed to become one. LunaPath
 * scores 33.3% on the 10-degree variant where the paper's planners score 100,
 * and the reason is measured rather than guessed: the benchmark's reference
 * planners allow a diagonal move between two occupied cells, and LunaPath
 * refuses it. On the 10-degree maps, eight of twelve are connected ONLY by
 * such a move. Under the benchmark's own motion model LunaPath reproduces the
 * paper's shortest-path lengths exactly -- 651.81, 636.16, 620.24 against the
 * paper's 651.81, 636.16, 620.24 -- so the gap is the safety rule, not the
 * planner.
 *
 * Presenting the corner-cutting number as ours would be the single most
 * misleading thing this product could say about itself, which is why both
 * rows are always shown together and neither is ever shown alone.
 */

export interface BenchmarkVariant {
  /** Slope threshold that defines the occupancy grid. */
  label: string
  /** LunaPath A*, multi-criteria, with its corner-cutting ban. */
  lunapathSuccess: number
  /** Pure-distance Dijkstra under the BENCHMARK's motion model. */
  benchmarkModelSuccess: number
  /** Shortest path LunaPath found, in cells. */
  lunapathLength: number
  /** The same figure under the benchmark's model -- and the paper's own. */
  benchmarkModelLength: number
  /** Quoted from the paper, not measured here. */
  paperLength: number
  /** Maps reachable only by cutting a corner, out of twelve. */
  cornerCutOnlyMaps: number
  totalMaps: number
}

export const MOONPLANBENCH_VARIANTS: readonly BenchmarkVariant[] = [
  {
    label: 'MoonPlanBench-10',
    lunapathSuccess: 0.333,
    benchmarkModelSuccess: 1.0,
    lunapathLength: 720.3,
    benchmarkModelLength: 651.81,
    paperLength: 651.81,
    cornerCutOnlyMaps: 8,
    totalMaps: 12,
  },
  {
    label: 'MoonPlanBench-15',
    lunapathSuccess: 0.917,
    benchmarkModelSuccess: 1.0,
    lunapathLength: 658.34,
    benchmarkModelLength: 636.16,
    paperLength: 636.16,
    cornerCutOnlyMaps: 1,
    totalMaps: 12,
  },
  {
    label: 'MoonPlanBench-20',
    lunapathSuccess: 1.0,
    benchmarkModelSuccess: 1.0,
    lunapathLength: 631.88,
    benchmarkModelLength: 620.24,
    paperLength: 620.24,
    cornerCutOnlyMaps: 0,
    totalMaps: 12,
  },
]

/**
 * The claim boundary, transcribed from the report's machine-readable form
 * (`app.benchmark.CLAIM`). Shown wherever the figures are.
 */
export const MOONPLANBENCH_CLAIM =
  'MoonPlanBench maps are slope/roughness-thresholded occupancy grids only — no shadow, ' +
  'thermal, slip, roughness or Earth-visibility layer, and no DEM released — at 320 m to ' +
  '7,680 m per cell. LunaPath’s multi-criteria cost is a single value on them and its ' +
  'planner reduces to a shortest-path search with its own safety rules. Success here ' +
  'measures connectivity under a motion model, not rover route planning. The benchmark’s ' +
  'reference planners allow diagonal moves between two occupied cells; LunaPath refuses ' +
  'them. Every paper figure is a quotation from arXiv 2512.21438v1, not our measurement.'

export const MOONPLANBENCH_SOURCE = {
  report: 'docs/research/moonplanbench_report.md',
  runner: 'scripts/moonplanbench_runner.py',
  paper: 'arXiv 2512.21438v1',
  maps: 36,
}
