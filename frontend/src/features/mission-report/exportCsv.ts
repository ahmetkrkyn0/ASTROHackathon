import type { PlanResponse, Waypoint } from '../../api'

/**
 * The route as a spreadsheet.
 *
 * The report answers "was this route sound"; the CSV answers questions the
 * report does not anticipate. It carries every waypoint, not a summary,
 * because the point of exporting is to ask something the interface did not
 * think of.
 */

/** One column per field the simulation actually produced. */
const COLUMNS: ReadonlyArray<{ header: string; value: (w: Waypoint) => string | number | boolean }> =
  [
    { header: 'step', value: (w) => w.step },
    { header: 'row', value: (w) => w.row },
    { header: 'col', value: (w) => w.col },
    { header: 'longitude_deg', value: (w) => w.lon },
    { header: 'latitude_deg', value: (w) => w.lat },
    { header: 'distance_m', value: (w) => w.distance_m },
    { header: 'elapsed_hours', value: (w) => w.elapsed_hours },
    { header: 'altitude_m', value: (w) => w.altitude_m ?? '' },
    { header: 'slope_deg', value: (w) => w.slope_deg },
    { header: 'surface_temp_c', value: (w) => w.surface_temp_c },
    { header: 'shadow_ratio', value: (w) => w.shadow_ratio },
    { header: 'battery_pct', value: (w) => w.battery_pct },
    { header: 'step_energy_wh', value: (w) => w.step_energy_wh },
    { header: 'node_cost', value: (w) => w.node_cost },
    { header: 'risk_level', value: (w) => w.risk_level },
    { header: 'recharged_this_step', value: (w) => w.recharged_this_step },
  ]

/**
 * RFC 4180 quoting.
 *
 * Only strings can carry a comma, a quote or a newline, but the rover name
 * reaches this file through the filename rather than a cell, so in practice
 * nothing here needs quoting today. It is done anyway: a field that starts
 * needing it later would otherwise corrupt every row after it, silently.
 */
function escapeCell(value: string | number | boolean): string {
  const text = String(value)
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`
  }
  return text
}

/** The whole route as RFC 4180 text, header row included. */
export function waypointsToCsv(waypoints: readonly Waypoint[]): string {
  const header = COLUMNS.map((c) => c.header).join(',')
  const rows = waypoints.map((w) => COLUMNS.map((c) => escapeCell(c.value(w))).join(','))
  // CRLF, which RFC 4180 specifies and Excel is happiest with.
  return [header, ...rows].join('\r\n')
}

/** A filename that says which route this is without being opened. */
export function csvFilename(plan: PlanResponse, now: Date = new Date()): string {
  const rover = (plan.rover?.id ?? 'rover').replace(/[^a-z0-9_-]/gi, '')
  const stamp = now.toISOString().slice(0, 16).replace(/[:T]/g, '-')
  return `lunapath-${rover}-${stamp}.csv`
}

/**
 * Hands the file to the browser.
 *
 * The BOM is not decoration: Excel reads a UTF-8 CSV as the local codepage
 * without it, so any non-ASCII in a future column arrives mangled. Every
 * other reader ignores it.
 */
export function downloadCsv(plan: PlanResponse, now: Date = new Date()): void {
  const blob = new Blob(['﻿', waypointsToCsv(plan.waypoints)], {
    type: 'text/csv;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = csvFilename(plan, now)
  document.body.appendChild(link)
  link.click()
  link.remove()
  // Revoking immediately can cancel the download in some browsers; one frame
  // is enough for the click to have been taken.
  requestAnimationFrame(() => URL.revokeObjectURL(url))
}
