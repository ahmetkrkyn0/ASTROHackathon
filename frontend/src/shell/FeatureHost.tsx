import { FEATURES, type FeatureSlot } from '../features/registry'

/**
 * Renders whichever features are registered for one slot.
 *
 * Emits a fragment and nothing else: an empty slot produces no element, no
 * wrapper, no margin and no height, so a slot the cockpit has not filled yet is
 * invisible to layout. That is what lets the five hosts sit in App.tsx
 * permanently without changing how the cockpit looks today.
 */
export function FeatureHost({ slot }: { slot: FeatureSlot }) {
  return (
    <>
      {FEATURES.filter((feature) => feature.slot === slot).map(({ id, Component }) => (
        <Component key={id} />
      ))}
    </>
  )
}
