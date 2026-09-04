import { useEffect, useMemo, useState } from 'react'
import { fetchCellTelemetry } from '../../api'
import { useFocusTelemetry, useMission } from '../../mission/MissionContext'
import type { CellTelemetryResponse } from '../../net/types'

export type CostKey = 'slope' | 'energy' | 'shadow' | 'thermal'

export interface CostRow {
  key: CostKey
  label: string
  /** null means an INFINITE contribution: this component closes the cell. */
  value: number | null
  /** Fraction of the finite total, 0-1. Zero when the cell is impassable. */
  share: number
  weight: number
}

const LABELS: Record<CostKey, string> = {
  slope: 'Slope',
  energy: 'Energy',
  // The cost component is named `shadow`; the grid layer behind it is named
  // `shadow_ratio`. Two namespaces, not one (spec T2).
  shadow: 'Shadow',
  thermal: 'Thermal',
}

const WEIGHT_KEY: Record<CostKey, 'w_slope' | 'w_energy' | 'w_shadow' | 'w_thermal'> = {
  slope: 'w_slope',
  energy: 'w_energy',
  shadow: 'w_shadow',
  thermal: 'w_thermal',
}

const KEYS: CostKey[] = ['slope', 'energy', 'shadow', 'thermal']

export function useCostExplain() {
  const { weights } = useMission()
  // The cell under the pointer, which is what this panel explains. The
  // canonical mission value publishes no hoverCell and no cellTelemetry, on
  // purpose: focus telemetry already follows hoverPoint ?? goal ?? start, and
  // a feature that wants one cell's numbers fetches that cell. selectedCell
  // is deliberately NOT used -- it is always null in this cockpit, and
  // binding to it would make the panel update on click instead of on hover,
  // which is a different feature.
  const focus = useFocusTelemetry()
  const [cellTelemetry, setCellTelemetry] = useState<CellTelemetryResponse | null>(null)

  // One request per cell, not per pointer event: the effect keys on the two
  // coordinates, and the in-flight request is aborted when they change, so
  // dragging across the grid leaves one live request rather than a queue of
  // answers arriving out of order.
  useEffect(() => {
    const controller = new AbortController()
    fetchCellTelemetry(focus.row, focus.col, controller.signal)
      .then(setCellTelemetry)
      .catch((cause: unknown) => {
        // An abort is this effect's own cleanup, not a failure to report.
        if ((cause as { name?: string }).name === 'AbortError') return
        setCellTelemetry(null)
      })
    return () => controller.abort()
  }, [focus.row, focus.col])

  const hoverCell: [number, number] = [focus.row, focus.col]

  return useMemo(() => {
    const breakdown = cellTelemetry?.cost_breakdown ?? null
    if (!breakdown) {
      return {
        rows: [],
        total: null,
        impassable: false,
        impassableBy: [],
        cell: hoverCell,
      }
    }

    const impassableBy = KEYS.filter((key) => breakdown[key] === null).map(
      (key) => LABELS[key],
    )

    // A null TOTAL is the authoritative verdict, and it has two causes.
    // costmap.explain() returns null when any component is infinite, and
    // ALSO when _invalid_mask closes the cell -- not traversable, or NaN in
    // slope / thermal / shadow_ratio / thermal_min (costmap.py:66-75,
    // 155-158). The second path leaves all four components finite, so
    // keying "impassable" off impassableBy alone would call such a cell
    // passable and print its total as "unknown". Live example on the
    // shipped grid: row 0, col 74 -- four finite contributions, null total.
    const total = breakdown.total
    const impassable = total === null

    // Shares are taken against the finite total only. When the cell is
    // impassable there is no meaningful denominator, so every bar reads 0
    // rather than inventing a proportion out of a partial sum. The value
    // column still shows each real number.
    const denominator = total !== null && total > 0 ? total : 0

    const rows: CostRow[] = KEYS.map((key) => ({
      key,
      label: LABELS[key],
      value: breakdown[key],
      share:
        denominator > 0 && breakdown[key] !== null
          ? (breakdown[key] as number) / denominator
          : 0,
      weight: weights[WEIGHT_KEY[key]],
    }))

    return { rows, total, impassable, impassableBy, cell: hoverCell }
    // hoverCell is rebuilt from focus.row/focus.col on every render, so the
    // two coordinates are the dependencies rather than the array they go in.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cellTelemetry, focus.row, focus.col, weights])
}
