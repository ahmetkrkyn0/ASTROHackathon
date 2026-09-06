/**
 * An alternative LunaPath mark: the product's own output.
 *
 * The patch this competes with is a highway running to a horizon, which is the
 * stock picture for "a journey" -- it would serve a logistics firm or a tyre
 * brand equally well. This one tries to be a mark only this product could have.
 *
 * Three decisions carry it:
 *
 * TOP-DOWN, not a horizon. LunaPath does not show anyone a landscape from
 * standing height. It shows a 500x500 grid of the south pole from above, which
 * is the view the planning actually happens in, so that is the view the mark
 * takes. Craters read as rings rather than as ellipses for the same reason.
 *
 * A POLYLINE, not a road. A* returns a sequence of cells, and the route drawn
 * on the map is a chain of straight segments between waypoints -- it turns,
 * it doubles back around a slope, it is visibly computed. A smooth curve would
 * be a picture of a road; the kinks are the picture of a solver.
 *
 * THE APP'S OWN COLOURS, in the app's own meanings. Mint is where a rover
 * starts and coral is where it is going, on every screen in the product. The
 * mark uses them for exactly that, so it teaches the legend before the operator
 * has seen a map. Nothing here is decorative colour.
 *
 * The route deliberately does not run straight between its endpoints: it bends
 * around the large crater rather than through it, which is the one thing the
 * planner is for.
 */

interface LunaPathRouteMarkProps {
  size?: number
  className?: string
}

export default function LunaPathRouteMark({ size = 132, className }: LunaPathRouteMarkProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 200 200"
      fill="none"
      role="img"
      aria-label="LunaPath"
    >
      {/* The disc: the mapped sector, edge on. */}
      <circle cx="100" cy="100" r="88" stroke="var(--coral)" strokeWidth="4.5" />

      {/* Terrain. Rings, not discs -- a crater seen from directly above is a
          rim, and filling them would turn the pole into a domino. */}
      <g stroke="var(--text)" strokeOpacity="0.34" strokeWidth="2.6">
        <circle cx="126" cy="86" r="26" />
        <circle cx="62" cy="72" r="13" />
        <circle cx="54" cy="132" r="17" />
        <circle cx="138" cy="146" r="10" />
        <circle cx="95" cy="46" r="7.5" />
      </g>

      {/* The route. Straight segments with real corners, bending around the
          crater instead of through it. */}
      <path
        d="M 52,148 L 78,138 L 88,116 L 112,124 L 138,110 L 146,78"
        stroke="var(--lavender)"
        strokeWidth="5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Waypoints: the solver's own vertices, not decoration. */}
      <g fill="var(--void)" stroke="var(--lavender)" strokeWidth="2.6">
        <circle cx="78" cy="138" r="4" />
        <circle cx="88" cy="116" r="4" />
        <circle cx="112" cy="124" r="4" />
        <circle cx="138" cy="110" r="4" />
      </g>

      {/* Start: filled, because the rover is there. */}
      <circle cx="52" cy="148" r="9.5" fill="var(--mint)" />

      {/* Goal: open, because it is not there yet. The same pair of marks the
          map draws on the terrain. */}
      <circle cx="146" cy="78" r="8" fill="var(--void)" stroke="var(--coral)" strokeWidth="5" />
    </svg>
  )
}
