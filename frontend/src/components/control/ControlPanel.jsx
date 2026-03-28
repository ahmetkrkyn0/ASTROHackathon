const weightFields = [
  { key: "w_dist", label: "Distance" },
  { key: "w_slope", label: "Slope" },
  { key: "w_thermal", label: "Thermal" },
  { key: "w_energy", label: "Energy" },
];

function WeightSlider({ label, value, onChange }) {
  return (
    <label className="block">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
          {value.toFixed(1)}
        </span>
      </div>
      <input
        type="range"
        min="0"
        max="2"
        step="0.1"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-slate-900"
      />
    </label>
  );
}

export default function ControlPanel({
  weights,
  selectedLayer,
  layerOptions,
  onWeightChange,
  onLayerChange,
  onApplyWeights,
  onPreviewReplan,
}) {
  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <p className="mission-label">ControlPanel</p>
        <h2 className="mission-title">Route priorities</h2>
        <p className="text-sm leading-6 text-slate-500">
          Tune the weighted planning bias, then refresh the mock route or preview a replan event.
        </p>
      </div>

      <div className="space-y-4">
        {weightFields.map((field) => (
          <WeightSlider
            key={field.key}
            label={field.label}
            value={weights[field.key]}
            onChange={(nextValue) => onWeightChange(field.key, nextValue)}
          />
        ))}
      </div>

      <label className="block space-y-2">
        <span className="mb-2 block text-sm font-medium text-slate-700">Active layer</span>
        <select
          value={selectedLayer}
          onChange={(event) => onLayerChange(event.target.value)}
          className="w-full rounded-2xl bg-white/80 px-3.5 py-3 text-sm text-slate-700 outline-none ring-1 ring-slate-200/80 transition focus:ring-2 focus:ring-slate-300"
        >
          {layerOptions.map((layer) => (
            <option key={layer.id} value={layer.id}>
              {layer.label}
            </option>
          ))}
        </select>
      </label>

      <div className="grid gap-3">
        <button
          type="button"
          onClick={onApplyWeights}
          className="rounded-2xl bg-slate-900 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
        >
          Refresh Mock Plan
        </button>
        <button
          type="button"
          onClick={onPreviewReplan}
          className="rounded-2xl bg-white/70 px-4 py-3 text-sm font-medium text-slate-700 ring-1 ring-slate-200/80 transition hover:bg-white"
        >
          Preview Replan
        </button>
      </div>

      <p className="text-xs leading-5 text-slate-400">
        This phase is mock-data driven. Controls reshape the local prototype state only.
      </p>
    </section>
  );
}
