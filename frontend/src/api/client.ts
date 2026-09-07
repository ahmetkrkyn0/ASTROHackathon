/**
 * The shared transport primitives every API family uses.
 *
 * Small on purpose. It exists so that a new endpoint family -- api/corridor.ts,
 * api/replan.ts, api/profileCompare.ts -- can be written without importing the
 * legacy monolith, which would make "do not add to api.ts" a rule nobody could
 * actually follow. There is exactly one fetch implementation in this codebase
 * and this file does not add a second: callers still call fetch, they just
 * agree on the base path and on how a failure is reported.
 */

export const BASE = '/api'

/**
 * A failed HTTP call, with the status kept.
 *
 * The status is what lets a caller tell a transport/configuration failure from
 * a semantic one without reading the message: the AI endpoint answers a refused
 * question with 200 and an errorCode, and reserves 503 for "the server cannot
 * serve this at all". The detail string is carried for logs, never for display
 * -- a 503 from the assistant route can name a server environment variable.
 */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}
