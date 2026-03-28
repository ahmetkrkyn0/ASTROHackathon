import PanelCard from "../layout/PanelCard";

function cellKey([row, col]) {
  return `${row}-${col}`;
}

function buildLookup(points = []) {
  return new Set(points.map(cellKey));
}

function getCellTone({ row, col, start, goal, safePath, shortPath, oldSegment, newSegment }) {
  const key = `${row}-${col}`;

  if (row === start[0] && col === start[1]) {
    return "bg-slate-900 text-white";
  }

  if (row === goal[0] && col === goal[1]) {
    return "bg-sky-600 text-white";
  }

  if (newSegment.has(key)) {
    return "bg-sky-100 ring-1 ring-inset ring-sky-300";
  }

  if (oldSegment.has(key)) {
    return "bg-amber-100 ring-1 ring-inset ring-amber-300";
  }

  if (safePath.has(key)) {
    return "bg-emerald-100 ring-1 ring-inset ring-emerald-200";
  }

  if (shortPath.has(key)) {
    return "bg-rose-100 ring-1 ring-inset ring-rose-200";
  }

  return "bg-slate-50";
}

export default function MapView({
  gridMetadata,
  selectedLayer,
  pathResult,
  comparisonResult,
  replanResult,
}) {
  const activeLayer = gridMetadata.layers.find((layer) => layer.id === selectedLayer) ?? gridMetadata.layers[0];
  const [rows, columns] = gridMetadata.shape;

  const safePath = buildLookup(comparisonResult.safe_path.path_grid);
  const shortPath = buildLookup(comparisonResult.shortest_path.path_grid);
  const oldSegment = buildLookup(replanResult.old_segment);
  const newSegment = buildLookup(replanResult.new_segment);

  return (
    <PanelCard
      title="MapView"
      description="Placeholder grid preview for route overlays and environmental layer context."
      actions={
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          Layer: {activeLayer.label}
        </span>
      }
      contentClassName="space-y-4"
    >
      <div
        className="grid gap-1 rounded-2xl border border-slate-200 bg-slate-100 p-3"
        style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
      >
        {Array.from({ length: rows * columns }, (_, index) => {
          const row = Math.floor(index / columns);
          const col = index % columns;
          const tone = getCellTone({
            row,
            col,
            start: gridMetadata.start_grid,
            goal: gridMetadata.goal_grid,
            safePath,
            shortPath,
            oldSegment,
            newSegment,
          });

          return (
            <div
              key={`${row}-${col}`}
              className={`flex aspect-square items-center justify-center rounded-md text-[10px] font-medium text-slate-500 ${tone}`}
            >
              {row === gridMetadata.start_grid[0] && col === gridMetadata.start_grid[1] ? "S" : null}
              {row === gridMetadata.goal_grid[0] && col === gridMetadata.goal_grid[1] ? "G" : null}
            </div>
          );
        })}
      </div>

      <div className="grid gap-3 text-sm text-slate-600 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl bg-slate-50 p-3">
          <p className="font-medium text-slate-900">Current route</p>
          <p className="mt-1">{pathResult.route_strategy}</p>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <p className="font-medium text-slate-900">Grid region</p>
          <p className="mt-1">{gridMetadata.region_name}</p>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <p className="font-medium text-slate-900">Resolution</p>
          <p className="mt-1">{gridMetadata.resolution_m} m / cell</p>
        </div>
        <div className="rounded-xl bg-slate-50 p-3">
          <p className="font-medium text-slate-900">Layer note</p>
          <p className="mt-1">{activeLayer.description}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-slate-600">
        <span className="rounded-full bg-emerald-100 px-3 py-1">Safe route</span>
        <span className="rounded-full bg-rose-100 px-3 py-1">Shortest route</span>
        <span className="rounded-full bg-amber-100 px-3 py-1">Old segment</span>
        <span className="rounded-full bg-sky-100 px-3 py-1">New segment</span>
      </div>
    </PanelCard>
  );
}
