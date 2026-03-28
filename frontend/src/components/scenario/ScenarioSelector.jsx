import PanelCard from "../layout/PanelCard";

export default function ScenarioSelector({ scenarios, activeScenarioId, onSelect }) {
  return (
    <PanelCard
      title="ScenarioSelector"
      description="Choose the mock mission setup used by the Mission Control panel."
      contentClassName="space-y-3"
    >
      {scenarios.map((scenario) => {
        const active = scenario.scenario_id === activeScenarioId;

        return (
          <button
            key={scenario.scenario_id}
            type="button"
            onClick={() => onSelect(scenario.scenario_id)}
            className={`w-full rounded-xl border px-4 py-3 text-left transition ${
              active
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300 hover:bg-white"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold">{scenario.name}</p>
              <span
                className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                  active ? "bg-white/15 text-white" : "bg-white text-slate-500"
                }`}
              >
                {scenario.status}
              </span>
            </div>
            <p className={`mt-2 text-sm ${active ? "text-slate-200" : "text-slate-500"}`}>
              {scenario.description}
            </p>
          </button>
        );
      })}
    </PanelCard>
  );
}
