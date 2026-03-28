import PanelCard from "../layout/PanelCard";

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
    <PanelCard
      title="ControlPanel"
      description="Adjust the weighted A* priorities and switch the layer preview."
      contentClassName="space-y-5"
    >
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

      <label className="block">
        <span className="mb-2 block text-sm font-medium text-slate-700">Active layer</span>
        <select
          value={selectedLayer}
          onChange={(event) => onLayerChange(event.target.value)}
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-slate-400"
        >
          {layerOptions.map((layer) => (
            <option key={layer.id} value={layer.id}>
              {layer.label}
            </option>
          ))}
        </select>
      </label>

      <div className="grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={onApplyWeights}
          className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
        >
          Refresh Mock Plan
        </button>
        <button
          type="button"
          onClick={onPreviewReplan}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
        >
          Preview Replan
        </button>
      </div>
    </PanelCard>
  );
}
