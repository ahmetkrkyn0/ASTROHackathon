import { MissionSnapshotPanel } from './MissionSnapshotPanel'

/**
 * The registry's only view of this feature.
 *
 * A one-line entrypoint on purpose: the registry imports this and nothing
 * else, so the panel's internals stay free to move without touching the file
 * every other feature also edits.
 */
export function MissionSnapshot() {
  return <MissionSnapshotPanel />
}
