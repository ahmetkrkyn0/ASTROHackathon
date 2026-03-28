import PanelCard from "../layout/PanelCard";

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
    <PanelCard
      title="MetricsPanel"
      description="Core mission metrics for the currently selected mock plan."
      contentClassName="space-y-4"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {metricItems.map((item) => (
          <div key={item.key} className="rounded-xl bg-slate-50 p-4">
            <p className="text-sm text-slate-500">{item.label}</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">
              {formatValue(pathResult[item.key], item.unit)}
            </p>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <p className="text-sm font-medium text-slate-900">Risk breakdown</p>
        <div className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-3">
          <div className="rounded-lg bg-emerald-50 px-3 py-2">
            Safe cells: {pathResult.risk_breakdown.safe_cells}
          </div>
          <div className="rounded-lg bg-amber-50 px-3 py-2">
            Caution cells: {pathResult.risk_breakdown.caution_cells}
          </div>
          <div className="rounded-lg bg-rose-50 px-3 py-2">
            Danger cells: {pathResult.risk_breakdown.danger_cells}
          </div>
        </div>
      </div>

      <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
        Comparison delta: safe route thermal reduction is{" "}
        <span className="font-semibold text-slate-900">
          {comparisonResult.delta.thermal_reduction_pct.toFixed(1)}%
        </span>{" "}
        with a distance overhead of{" "}
        <span className="font-semibold text-slate-900">
          {comparisonResult.delta.distance_overhead_pct.toFixed(1)}%
        </span>
        .
      </div>
    </PanelCard>
  );
}
