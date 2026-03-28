const contourLines = [
  "M -8 22 C 10 12, 26 10, 40 17 S 70 34, 108 8",
  "M -6 45 C 16 34, 34 32, 48 38 S 78 56, 106 30",
  "M -4 68 C 18 58, 36 56, 53 62 S 80 80, 104 58",
  "M 0 88 C 18 78, 34 76, 52 81 S 82 95, 102 74",
];

const layerThemes = {
  elevation: {
    badgeClass: "bg-slate-100/90 text-slate-700",
    surfaceStyle: {
      backgroundImage:
        "linear-gradient(135deg, #f8fafc 0%, #e2e8f0 44%, #f8fafc 100%)",
    },
    zones: [
      { cx: 28, cy: 26, rx: 18, ry: 14, fill: "rgba(148, 163, 184, 0.18)" },
      { cx: 76, cy: 62, rx: 24, ry: 18, fill: "rgba(100, 116, 139, 0.14)" },
    ],
    metaLabel: "Topography emphasis",
  },
  slope: {
    badgeClass: "bg-amber-100/90 text-amber-800",
    surfaceStyle: {
      backgroundImage:
        "radial-gradient(circle at 18% 28%, rgba(245, 158, 11, 0.16), transparent 22%), radial-gradient(circle at 76% 60%, rgba(251, 191, 36, 0.14), transparent 24%), linear-gradient(135deg, #f8fafc 0%, #fff7ed 48%, #f8fafc 100%)",
    },
    zones: [
      { cx: 26, cy: 34, rx: 17, ry: 12, fill: "rgba(245, 158, 11, 0.18)" },
      { cx: 70, cy: 54, rx: 22, ry: 16, fill: "rgba(251, 191, 36, 0.12)" },
    ],
    metaLabel: "Gradient emphasis",
  },
  thermal_risk: {
    badgeClass: "bg-rose-100/90 text-rose-700",
    surfaceStyle: {
      backgroundImage:
        "radial-gradient(circle at 24% 30%, rgba(251, 113, 133, 0.22), transparent 24%), radial-gradient(circle at 70% 64%, rgba(251, 191, 36, 0.18), transparent 22%), radial-gradient(circle at 58% 20%, rgba(15, 23, 42, 0.07), transparent 18%), linear-gradient(135deg, #f8fafc 0%, #fff1f2 42%, #f8fafc 100%)",
    },
    zones: [
      { cx: 24, cy: 32, rx: 18, ry: 14, fill: "rgba(244, 63, 94, 0.18)" },
      { cx: 62, cy: 68, rx: 20, ry: 16, fill: "rgba(251, 191, 36, 0.14)" },
      { cx: 78, cy: 28, rx: 16, ry: 12, fill: "rgba(148, 163, 184, 0.12)" },
    ],
    metaLabel: "Thermal emphasis",
  },
  traversability: {
    badgeClass: "bg-cyan-100/90 text-cyan-800",
    surfaceStyle: {
      backgroundImage:
        "radial-gradient(circle at 22% 22%, rgba(34, 211, 238, 0.14), transparent 24%), radial-gradient(circle at 78% 72%, rgba(14, 165, 233, 0.16), transparent 26%), linear-gradient(135deg, #f8fafc 0%, #ecfeff 48%, #f8fafc 100%)",
    },
    zones: [
      { cx: 32, cy: 30, rx: 20, ry: 12, fill: "rgba(34, 211, 238, 0.16)" },
      { cx: 74, cy: 66, rx: 24, ry: 18, fill: "rgba(14, 165, 233, 0.12)" },
    ],
    metaLabel: "Traverse emphasis",
  },
  psr_mask: {
    badgeClass: "bg-slate-200/90 text-slate-700",
    surfaceStyle: {
      backgroundImage:
        "radial-gradient(circle at 30% 34%, rgba(15, 23, 42, 0.16), transparent 24%), radial-gradient(circle at 66% 64%, rgba(71, 85, 105, 0.14), transparent 26%), linear-gradient(135deg, #f8fafc 0%, #eef2f7 48%, #f8fafc 100%)",
    },
    zones: [
      { cx: 30, cy: 34, rx: 20, ry: 14, fill: "rgba(30, 41, 59, 0.16)" },
      { cx: 66, cy: 64, rx: 24, ry: 18, fill: "rgba(71, 85, 105, 0.12)" },
    ],
    metaLabel: "PSR emphasis",
  },
};

function toPoint([row, col], rows, columns) {
  return {
    x: ((col + 0.5) / columns) * 100,
    y: ((row + 0.5) / rows) * 100,
  };
}

function toPolyline(points, rows, columns) {
  return points
    .map((point) => {
      const normalized = toPoint(point, rows, columns);
      return `${normalized.x},${normalized.y}`;
    })
    .join(" ");
}

function Marker({ point, label, dotClass, labelClass }) {
  return (
    <div
      className="pointer-events-none absolute z-20 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2"
      style={{ left: `${point.x}%`, top: `${point.y}%` }}
    >
      <div className={`flex h-5 w-5 items-center justify-center rounded-full ring-4 ring-white shadow-lg ${dotClass}`}>
        <span className="h-2 w-2 rounded-full bg-white" />
      </div>
      <div className={`rounded-full px-2.5 py-1 text-[11px] font-semibold shadow-lg ${labelClass}`}>
        {label}
      </div>
    </div>
  );
}

function LegendItem({ toneClass, label }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`h-2.5 w-8 rounded-full ${toneClass}`} />
      <span>{label}</span>
    </div>
  );
}

export default function MapView({
  gridMetadata,
  selectedLayer,
  pathResult,
  comparisonResult,
  replanResult,
}) {
  const activeLayer = gridMetadata.layers.find((layer) => layer.id === selectedLayer) ?? gridMetadata.layers[0];
  const theme = layerThemes[selectedLayer] ?? layerThemes.thermal_risk;
  const [rows, columns] = gridMetadata.shape;

  const safePath = toPolyline(comparisonResult.safe_path.path_grid, rows, columns);
  const shortestPath = toPolyline(comparisonResult.shortest_path.path_grid, rows, columns);
  const oldSegmentPath = replanResult.old_segment.length
    ? toPolyline(replanResult.old_segment, rows, columns)
    : "";
  const newSegmentPath = replanResult.new_segment.length
    ? toPolyline(replanResult.new_segment, rows, columns)
    : "";
  const startPoint = toPoint(gridMetadata.start_grid, rows, columns);
  const goalPoint = toPoint(gridMetadata.goal_grid, rows, columns);
  const showReplan = Boolean(oldSegmentPath && newSegmentPath);

  return (
    <section className="mission-surface overflow-hidden px-5 py-5 sm:px-6 sm:py-6">
      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <p className="mission-label">MapView</p>
          <h2 className="text-[clamp(1.5rem,2vw,2rem)] font-semibold tracking-tight text-slate-950">
            {gridMetadata.region_name}
          </h2>
          <p className="max-w-2xl text-sm leading-6 text-slate-500">{activeLayer.description}</p>
        </div>

        <div className="flex flex-wrap gap-2 text-xs font-medium">
          <span className={`rounded-full px-3 py-1.5 ${theme.badgeClass}`}>{activeLayer.label}</span>
          <span className="rounded-full bg-white/80 px-3 py-1.5 text-slate-600 ring-1 ring-slate-200/80">
            {theme.metaLabel}
          </span>
          <span className="rounded-full bg-white/80 px-3 py-1.5 text-slate-600 ring-1 ring-slate-200/80">
            {pathResult.route_strategy}
          </span>
        </div>
      </div>

      <div
        className="relative min-h-[440px] overflow-hidden rounded-[32px] bg-slate-100 sm:min-h-[560px]"
        style={theme.surfaceStyle}
      >
        <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.35),transparent_52%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent,rgba(15,23,42,0.08))]" />

        <svg
          className="absolute inset-0 h-full w-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          <g opacity="0.42">
            {contourLines.map((path) => (
              <path
                key={path}
                d={path}
                fill="none"
                stroke="rgba(15, 23, 42, 0.12)"
                strokeWidth="0.4"
                strokeLinecap="round"
              />
            ))}
          </g>

          <g opacity="0.9">
            {theme.zones.map((zone) => (
              <ellipse
                key={`${zone.cx}-${zone.cy}`}
                cx={zone.cx}
                cy={zone.cy}
                rx={zone.rx}
                ry={zone.ry}
                fill={zone.fill}
              />
            ))}
          </g>

          <polyline
            points={shortestPath}
            fill="none"
            stroke="rgba(224, 86, 73, 0.92)"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="3.5 3"
          />
          <polyline
            points={safePath}
            fill="none"
            stroke="rgba(15, 118, 110, 0.2)"
            strokeWidth="3.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <polyline
            points={safePath}
            fill="none"
            stroke="rgba(15, 118, 110, 0.9)"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {showReplan ? (
            <>
              <polyline
                points={oldSegmentPath}
                fill="none"
                stroke="rgba(217, 119, 6, 0.9)"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray="2.5 2"
              />
              <polyline
                points={newSegmentPath}
                fill="none"
                stroke="rgba(3, 105, 161, 0.26)"
                strokeWidth="4.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <polyline
                points={newSegmentPath}
                fill="none"
                stroke="rgba(3, 105, 161, 0.92)"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </>
          ) : null}
        </svg>

        <Marker
          point={startPoint}
          label="Start"
          dotClass="bg-slate-950"
          labelClass="bg-white text-slate-900 ring-1 ring-slate-200/70"
        />
        <Marker
          point={goalPoint}
          label="Goal"
          dotClass="bg-sky-600"
          labelClass="bg-sky-600 text-white"
        />

        <div className="absolute left-4 top-4 flex flex-wrap gap-2 sm:left-5 sm:top-5">
          <span className="rounded-full bg-white/80 px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm ring-1 ring-white/90 backdrop-blur">
            {gridMetadata.resolution_m} m per cell
          </span>
          <span className="rounded-full bg-white/80 px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm ring-1 ring-white/90 backdrop-blur">
            {pathResult.route_label}
          </span>
        </div>

        <div className="absolute bottom-4 left-4 rounded-[22px] bg-white/76 px-4 py-3 text-[11px] font-medium text-slate-600 shadow-lg ring-1 ring-white/90 backdrop-blur sm:bottom-5 sm:left-5">
          <div className="flex flex-wrap gap-x-4 gap-y-2">
            <LegendItem toneClass="bg-emerald-600" label="Safe route" />
            <LegendItem toneClass="bg-rose-500" label="Shortest route" />
            {showReplan ? <LegendItem toneClass="bg-amber-500" label="Old segment" /> : null}
            {showReplan ? <LegendItem toneClass="bg-sky-600" label="New segment" /> : null}
          </div>
        </div>

        <div className="absolute bottom-4 right-4 max-w-[280px] rounded-[24px] bg-white/80 px-4 py-4 text-sm shadow-lg ring-1 ring-white/90 backdrop-blur sm:bottom-5 sm:right-5">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Active plan</p>
          <p className="mt-2 text-base font-semibold text-slate-950">{pathResult.route_strategy}</p>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            Distance {pathResult.total_distance_m} m, thermal {pathResult.total_thermal_exposure.toFixed(1)}
            , energy {pathResult.total_energy_cost.toFixed(1)}.
          </p>
          <p className="mt-3 text-xs leading-5 text-slate-400">{replanResult.reason}</p>
        </div>
      </div>
    </section>
  );
}
