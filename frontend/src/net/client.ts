const BASE = '/api'

/** An HTTP failure the backend described in its `detail` field. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Every FastAPI failure in this backend arrives as `{"detail": "..."}`
 * (HTTPException). Reading it here means no caller has to, and a caller
 * that only prints `error.message` still shows the real reason instead of
 * a bare status code.
 */
async function failure(response: Response): Promise<ApiError> {
  let detail = response.statusText
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') {
      detail = body.detail
    }
  } catch {
    // Body was not JSON. statusText is the best we have.
  }
  return new ApiError(response.status, detail)
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { signal })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}

export async function postJson<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}

/**
 * The binary path. Headers come back with the array because the backend's
 * self-description (rows, cols, validity, value range) travels in
 * `X-Layer-*` / `X-Series-*` headers, not in the payload.
 */
export async function getFloat32(
  path: string,
  signal?: AbortSignal,
): Promise<{ data: Float32Array; headers: Headers }> {
  const response = await fetch(`${BASE}${path}`, { signal })
  if (!response.ok) throw await failure(response)
  return {
    data: new Float32Array(await response.arrayBuffer()),
    headers: response.headers,
  }
}
