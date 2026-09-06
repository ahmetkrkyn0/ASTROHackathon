/**
 * Number formatting shared by the charts and the panels.
 *
 * Its own module rather than an export from charts.tsx: a non-component export
 * there breaks Fast Refresh for the whole file, which this project's eslint
 * config treats as an error.
 *
 * The rules themselves live in i18n/reportCopy.ts, because a thousands
 * separator is a fact about the reader's language and not about this feature.
 * This module is the re-export the charts and the modal already import, kept
 * so the call sites did not all have to move.
 */
export { fmtNum as fmt, fmtPct } from '../../i18n/reportCopy'
export type { ReportLang } from '../../i18n/reportCopy'
