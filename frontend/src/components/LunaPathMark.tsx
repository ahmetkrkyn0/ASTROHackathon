/**
 * The LunaPath emblem.
 *
 * Redrawn from the mission-patch the team made, in the console's palette. The
 * original is royal blue behind a coral ring, with a white lunar horizon, a
 * road running to the vanishing point and an arrow leaving it. Royal blue is
 * not a colour this product owns anywhere; the coral ring already is
 * (`--coral`), so the ring keeps its colour and the blue becomes the ground the
 * rest of the console is built on.
 *
 * The two-tone construction survives the translation intact: everything that
 * was blue-inside-white -- the craters, the road surface either side of the
 * centre line -- is a hole rather than a painted shape, cut with a mask. That
 * is why the mark reads on the boot screen's void and would read just as well
 * on a light surface: the holes take whatever is behind them, exactly as the
 * blue did.
 *
 * The wordmark is deliberately not here. The original curves LUNAPATH along
 * the bottom of the disc in custom lettering; tracing that would be a worse
 * copy of it, and every surface that shows this mark already sets the name in
 * Archivo directly underneath. Drawing it twice is the duplication, not the
 * omission.
 */

interface LunaPathMarkProps {
  /** Rendered square at this many pixels. */
  size?: number
  className?: string
}

export default function LunaPathMark({ size = 132, className }: LunaPathMarkProps) {
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
      <defs>
        {/* White where the emblem paints, black where the ground shows. */}
        <mask id="lunapath-surface" maskUnits="userSpaceOnUse">
          {/* The lunar surface: the lower part of the disc, closed along a
              horizon that bulges up toward the ring. */}
          <path
            d="M 12.8,112 A 88,88 0 0 0 187.2,112 A 116,116 0 0 0 12.8,112 Z"
            fill="#fff"
          />

          {/* The road, in perspective. Both lanes are triangles converging on
              one vanishing point at (100, 82), which is where the horizon sits
              -- that is what makes it read as distance rather than as two
              tapering wedges. They run past the bottom of the disc (y=200)
              rather than stopping inside it: a road that ends in mid-surface
              leaves a notch, and the surface is what clips them.

              Cut out, so they carry the ground colour the way the blue did.
              What is left between them is the centre line, and it runs on
              through the horizon into the arrow. */}
          <path d="M 57,200 L 93,200 L 100,82 Z" fill="#000" />
          <path d="M 107,200 L 143,200 L 100,82 Z" fill="#000" />

          {/* Craters, kept clear of the road at every depth -- the lanes are
              widest at the bottom, so the low ones sit furthest out. */}
          <ellipse cx="52" cy="124" rx="16" ry="9.5" fill="#000" />
          <ellipse cx="150" cy="130" rx="13" ry="8" fill="#000" />
          <ellipse cx="68" cy="100" rx="8" ry="5" fill="#000" />
          <ellipse cx="136" cy="104" rx="9" ry="5.5" fill="#000" />
          <ellipse cx="163" cy="112" rx="6.5" ry="4" fill="#000" />
          <ellipse cx="38" cy="104" rx="6" ry="4" fill="#000" />
          <ellipse cx="50" cy="156" rx="8" ry="4.5" fill="#000" />
          <ellipse cx="150" cy="160" rx="6.5" ry="4" fill="#000" />
        </mask>
      </defs>

      {/* The outer ring, and the inner arc the arrow rises through. Both keep
          the coral they had. */}
      <circle cx="100" cy="100" r="91" stroke="var(--coral)" strokeWidth="5" />
      {/* Only the half above the horizon. Drawn as a full circle it showed
          through the road's cut-outs, which read as a mistake rather than as
          an arc behind the moon. */}
      <path d="M 43.8,82 A 59,59 0 0 1 156.2,82" stroke="var(--coral)" strokeWidth="2.4" />

      <g mask="url(#lunapath-surface)">
        <rect x="0" y="0" width="200" height="200" fill="var(--text)" />
      </g>

      {/* Leaving the surface. The one part of the mark that is not the moon, so
          it is the one part that takes the console's accent rather than its
          regolith white. */}
      <path
        d="M 100,34 L 113,60 L 104.5,60 L 102.6,86 L 97.4,86 L 95.5,60 L 87,60 Z"
        fill="var(--lavender)"
      />
    </svg>
  )
}
