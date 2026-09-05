/**
 * Number formatting shared by the charts and the panels.
 *
 * Its own module rather than an export from charts.tsx: a non-component export
 * there breaks Fast Refresh for the whole file, which this project's eslint
 * config treats as an error.
 */
export function fmt(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return '--'
  // Thousands get a separator and lose their decimals -- a node count of
  // 3,558.0 reads as a measurement it is not. en-GB, matching the interface
  // language, so the separator does not disagree with the decimal point the
  // toFixed branch produces.
  return Math.abs(value) >= 1000
    ? Math.round(value).toLocaleString('en-GB')
    : value.toFixed(digits)
}
