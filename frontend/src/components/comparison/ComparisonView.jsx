function SummaryCard({ label, pathResult, tone }) {
  return (
    <article className={`rounded-[24px] px-4 py-4 ${tone}`}>
      <p className="text-sm font-semibold">{label}</p>
      <p className="mt-2 text-base font-semibold">{pathResult.route_strategy}</p>
      <div className="mt-4 space-y-2 text-sm leading-6">
        <p>Distance: {pathResult.total_distance_m} m</p>
        <p>Thermal exposure: {pathResult.total_thermal_exposure.toFixed(1)}</p>
        <p>Energy cost: {pathResult.total_energy_cost.toFixed(1)}</p>
      </div>
    </article>
  );
}

export default function ComparisonView({ comparisonResult }) {
  const isSafePreferred = comparisonResult.delta.recommendation === "safe_path_preferred";

  return (
    <section className="space-y-5">
      <div className="space-y-2">
        <p className="mission-label">ComparisonView</p>
        <h2 className="mission-title">Route tradeoff</h2>
        <p className="text-sm leading-6 text-slate-500">
          Compact safe-vs-shortest summary for operator review.
        </p>
      </div>

      <div className="rounded-[26px] bg-slate-950 px-4 py-4 text-white shadow-[0_24px_60px_-34px_rgba(15,23,42,0.85)]">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
          Recommendation
        </p>
        <p className="mt-2 text-lg font-semibold">
          {isSafePreferred ? "Favor the safe route" : "Paths are currently equivalent"}
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          The safe route is {comparisonResult.delta.distance_overhead_pct.toFixed(1)}% longer, but it
          reduces thermal exposure by {comparisonResult.delta.thermal_reduction_pct.toFixed(1)}%.
        </p>
      </div>

      <div className="space-y-3">
        <SummaryCard
          label="Safe path"
          pathResult={comparisonResult.safe_path}
          tone="bg-emerald-50/90 text-emerald-900"
        />
        <SummaryCard
          label="Shortest path"
          pathResult={comparisonResult.shortest_path}
          tone="bg-rose-50/90 text-rose-900"
        />
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex items-center justify-between rounded-2xl bg-slate-100/80 px-3 py-2 text-slate-600">
          <span>Distance overhead</span>
          <span className="font-semibold text-slate-900">
            {comparisonResult.delta.distance_overhead_pct.toFixed(1)}%
          </span>
        </div>
        <div className="flex items-center justify-between rounded-2xl bg-slate-100/80 px-3 py-2 text-slate-600">
          <span>Thermal reduction</span>
          <span className="font-semibold text-slate-900">
            {comparisonResult.delta.thermal_reduction_pct.toFixed(1)}%
          </span>
        </div>
        <div className="flex items-center justify-between rounded-2xl bg-slate-100/80 px-3 py-2 text-slate-600">
          <span>Energy delta</span>
          <span className="font-semibold text-slate-900">
            {comparisonResult.delta.energy_delta_pct.toFixed(1)}%
          </span>
        </div>
      </div>
    </section>
  );
}
