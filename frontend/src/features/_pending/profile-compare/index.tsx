import { useEffect } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { ProfileComparePanel } from './ProfileComparePanel'
import { profileOverlays } from './overlays'
import { useProfileCompare } from './useProfileCompare'

const OVERLAY_ID = 'profile-compare'

export function ProfileCompare() {
  const { results, comparison, run, busy, error } = useProfileCompare()
  const { register, unregister } = useOverlays()

  useEffect(() => {
    register(OVERLAY_ID, profileOverlays(results))
    return () => unregister(OVERLAY_ID)
  }, [register, results, unregister])

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
