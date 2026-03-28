const metricItems = [
  {
    key: "total_distance_m",
    label: "Distance",
    unit: "m",
  },
  {
    key: "total_thermal_exposure",
    label: "Thermal Exposure",
    unit: "",
  },
  {
    key: "total_energy_cost",
    label: "Energy Cost",
    unit: "",
  },
  {
    key: "max_slope_deg",
    label: "Max Slope",
    unit: "deg",
  },
];

function formatValue(value, unit) {
  const base = Number.isInteger(value) ? value : value.toFixed(1);
  return unit ? `${base} ${unit}` : base;
}

export default function MetricsPanel({ pathResult, comparisonResult }) {
  return (
    <section className="space-y-5">
      <div className="space-y-2">
        <p className="mission-label">MetricsPanel</p>
        <h2 className="mission-title">Mission summary</h2>
        <p className="text-sm leading-6 text-slate-500">
          Compact operational readout for the active mock plan.
        </p>
      </div>

      <dl className="space-y-3">
        {metricItems.map((item) => (
          <div
            key={item.key}
            className="flex items-end justify-between gap-4 border-b border-slate-200/70 pb-3 last:border-b-0 last:pb-0"
          >
            <div>
              <dt className="text-sm text-slate-500">{item.label}</dt>
              <dd className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
                {formatValue(pathResult[item.key], item.unit)}
              </dd>
            </div>
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-300">
              Live
            </span>
          </div>
        ))}
      </dl>

      <div className="rounded-[24px] bg-slate-950 px-4 py-4 text-slate-50">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Risk mix</p>
        <div className="mt-3 space-y-2 text-sm">
          <div className="flex items-center justify-between rounded-2xl bg-white/6 px-3 py-2">
            <span>Safe cells</span>
            <span className="font-semibold">{pathResult.risk_breakdown.safe_cells}</span>
          </div>
          <div className="flex items-center justify-between rounded-2xl bg-white/6 px-3 py-2">
            <span>Caution cells</span>
            <span className="font-semibold">{pathResult.risk_breakdown.caution_cells}</span>
          </div>
          <div className="flex items-center justify-between rounded-2xl bg-white/6 px-3 py-2">
            <span>Danger cells</span>
            <span className="font-semibold">{pathResult.risk_breakdown.danger_cells}</span>
          </div>
        </div>
      </div>

      <div className="rounded-2xl bg-slate-100/80 px-4 py-3 text-sm leading-6 text-slate-600">
        Current comparison delta indicates{" "}
        <span className="font-semibold text-slate-900">
          {comparisonResult.delta.thermal_reduction_pct.toFixed(1)}% lower thermal exposure
        </span>{" "}
        for the safer route with a{" "}
        <span className="font-semibold text-slate-900">
          {comparisonResult.delta.distance_overhead_pct.toFixed(1)}% distance premium
        </span>
        .
      </div>
    </section>
  );
}
