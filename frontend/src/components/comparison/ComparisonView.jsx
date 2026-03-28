import PanelCard from "../layout/PanelCard";

function SummaryCard({ label, pathResult, tone }) {
  return (
    <div className={`rounded-xl p-4 ${tone}`}>
      <p className="text-sm font-medium">{label}</p>
      <p className="mt-2 text-lg font-semibold">{pathResult.route_strategy}</p>
      <div className="mt-4 space-y-2 text-sm">
        <p>Distance: {pathResult.total_distance_m} m</p>
        <p>Thermal exposure: {pathResult.total_thermal_exposure.toFixed(1)}</p>
        <p>Energy cost: {pathResult.total_energy_cost.toFixed(1)}</p>
      </div>
    </div>
  );
}

export default function ComparisonView({ comparisonResult }) {
  const isSafePreferred = comparisonResult.delta.recommendation === "safe_path_preferred";

  return (
    <PanelCard
      title="ComparisonView"
      description="Side-by-side summary of the safe path versus the shortest path."
      contentClassName="space-y-4"
    >
      <div className="grid gap-3 lg:grid-cols-2">
        <SummaryCard
          label="Safe path"
          pathResult={comparisonResult.safe_path}
          tone="bg-emerald-50 text-emerald-900"
        />
        <SummaryCard
          label="Shortest path"
          pathResult={comparisonResult.shortest_path}
          tone="bg-rose-50 text-rose-900"
        />
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
        <p className="font-medium text-slate-900">
          Recommendation: {isSafePreferred ? "Safe path preferred" : "Paths are currently equivalent"}
        </p>
        <p className="mt-2">
          The safe route is {comparisonResult.delta.distance_overhead_pct.toFixed(1)}% longer, reduces
          thermal exposure by {comparisonResult.delta.thermal_reduction_pct.toFixed(1)}%, and changes the
          energy profile by {comparisonResult.delta.energy_delta_pct.toFixed(1)}%.
        </p>
      </div>
    </PanelCard>
  );
}
