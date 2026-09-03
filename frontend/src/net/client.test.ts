import { describe, expect, it } from 'vitest'
import { ApiError } from './client'

describe('ApiError', () => {
  it('carries the status alongside the message', () => {
    const error = new ApiError(422, 'start (9, 9) is outside the 5x5 grid.')
    expect(error.status).toBe(422)
    expect(error.message).toBe('start (9, 9) is outside the 5x5 grid.')
    expect(error).toBeInstanceOf(Error)
  })
})
