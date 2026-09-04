import { FEATURES, selectFeatures, type FeatureSlot } from '../features/registry'
import { useMission } from '../mission/MissionContext'

/**
 * Renders whichever features are registered for one slot in the current mode.
 *
 * Emits a fragment and nothing else: an empty slot produces no element, no
 * wrapper, no margin and no height, so a slot the cockpit has not filled yet is
 * invisible to layout. That is what lets the five hosts sit in App.tsx
 * permanently without changing how the cockpit looks today.
 *
 * The mode comes from mission context rather than a prop, so a slot stays a
 * name and nothing more -- App.tsx writes `<LeftRailSlot />` and never has to
 * know that visibility depends on the stage.
 */
export function FeatureHost({ slot }: { slot: FeatureSlot }) {
  const { missionMode } = useMission()
  return (
    <>
      {selectFeatures(FEATURES, slot, missionMode).map(({ id, Component }) => (
        <Component key={id} />
      ))}
    </>
  )
}
