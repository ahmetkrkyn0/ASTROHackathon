import { useEffect, useMemo } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { ProfileComparePanel } from './ProfileComparePanel'
import { profileOverlays } from './overlays'
import { useProfileCompare } from './useProfileCompare'

const OVERLAY_ID = 'profile-compare'

export function ProfileCompare() {
  const { results, comparison, run, busy, error } = useProfileCompare()
  const overlays = useOverlays()

  // MEMOISED: register keys off the array's identity, so a list rebuilt on
  // every render would re-run the effect forever.
  const commands = useMemo(() => profileOverlays(results), [results])

  useEffect(() => overlays.register(OVERLAY_ID, commands), [overlays, commands])

  return (
    <section className="rail-section">
      <p className="panel-kicker">Profile Comparison</p>
      <ProfileComparePanel
        results={results}
        comparison={comparison}
        run={run}
        busy={busy}
        error={error}
      />
    </section>
  )
}
