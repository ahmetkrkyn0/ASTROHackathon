/**
 * Fetch one binary raster and keep it as a capability.
 *
 * The hook every analysis layer uses instead of its own effect, so that the
 * three things easy to get wrong are got right once: an absent cache reads as
 * `unavailable` rather than as an error, a superseded request does not report
 * a failure, and the Float32Array is never copied into React state where a
 * re-render would clone a megabyte.
 */

import { useEffect, useState } from 'react'

import { fetchBinaryLayer, fetchFieldByUrl, type BinaryField } from '../net/layers'
import { isDataUnavailable } from '../net/errors'
import {
  CAPABILITY_IDLE,
  CAPABILITY_LOADING,
  capabilityError,
  capabilityFromError,
  capabilityReady,
  type Capability,
} from './capability'

export type BinaryFieldCapability = Capability<BinaryField>

/**
 * A named layer from `/api/layers/{name}`.
 *
 * `enabled` is a parameter rather than a caller-side `if` because the rule of
 * hooks forbids the `if`, and because a toggled-off layer must not merely stop
 * drawing -- it must stop asking. These endpoints answer 404 when the cache is
 * missing, and a hidden layer polling for a 404 fills the console with
 * failures for a layer nobody asked to see.
 */
export function useBinaryLayer(
  name: string,
  options: { enabled: boolean; downsample?: number; roverId?: string },
): BinaryFieldCapability {
  const { enabled, downsample, roverId } = options
  const [capability, setCapability] = useState<BinaryFieldCapability>(CAPABILITY_IDLE)

  useEffect(() => {
    if (!enabled) {
      setCapability(CAPABILITY_IDLE)
      return
    }

    const controller = new AbortController()
    setCapability(CAPABILITY_LOADING)

    fetchBinaryLayer(name, { downsample, roverId }, controller.signal)
      .then((field) => {
        if (controller.signal.aborted) return
        setCapability(capabilityReady(field))
      })
      .catch((error: unknown) => {
        const next = capabilityFromError(error, {
          isDataUnavailable: isDataUnavailable(error),
          signal: controller.signal,
        })
        // null means the request was cancelled, which is not a state change:
        // leaving `loading` in place lets the replacement request resolve it.
        if (next) setCapability(next)
      })

    return () => controller.abort()
  }, [enabled, name, downsample, roverId])

  return capability
}

/**
 * A field addressed by a `binary_url` a manifest handed us --
 * `/api/safe-haven`, `/api/survival`, `/api/thermal-dwell`, the series
 * endpoints.
 *
 * `binaryUrl` being null is the ordinary case, not an error: those manifests
 * publish an empty `fields` object when the model is unavailable, so there is
 * no URL to fetch and the capability the caller derived from the model block
 * already says why.
 */
export function useBinaryFieldUrl(
  label: string,
  binaryUrl: string | null,
  options: { enabled: boolean } = { enabled: true },
): BinaryFieldCapability {
  const { enabled } = options
  const [capability, setCapability] = useState<BinaryFieldCapability>(CAPABILITY_IDLE)

  useEffect(() => {
    if (!enabled || !binaryUrl) {
      setCapability(CAPABILITY_IDLE)
      return
    }

    const controller = new AbortController()
    setCapability(CAPABILITY_LOADING)

    fetchFieldByUrl(label, binaryUrl, controller.signal)
      .then((field) => {
        if (controller.signal.aborted) return
        setCapability(capabilityReady(field))
      })
      .catch((error: unknown) => {
        const next = capabilityFromError(error, {
          isDataUnavailable: isDataUnavailable(error),
          signal: controller.signal,
        })
        if (next) setCapability(next)
      })

    return () => controller.abort()
  }, [enabled, label, binaryUrl])

  // A shape mismatch throws inside fieldFromResponse rather than resolving to
  // a field that would be drawn one cell out of place. It arrives here as a
  // plain Error, which capabilityFromError has already classified.
  return capability
}

/** Re-exported so a caller needs one import for the field and its states. */
export { capabilityError }
export type { BinaryField }
