export default function ScenarioSelector({ scenarios, activeScenarioId, onSelect }) {
  return (
    <section className="space-y-4">
      <div className="space-y-2">
        <p className="mission-label">ScenarioSelector</p>
        <div className="flex items-end justify-between gap-3">
          <h2 className="mission-title">Mission setup</h2>
          <span className="text-xs font-medium text-slate-400">{scenarios.length} presets</span>
        </div>
        <p className="text-sm leading-6 text-slate-500">
          Select the mock scenario that drives the current route-planning session.
        </p>
      </div>

      <div className="space-y-2.5">
        {scenarios.map((scenario) => {
          const active = scenario.scenario_id === activeScenarioId;

          return (
            <button
              key={scenario.scenario_id}
              type="button"
              onClick={() => onSelect(scenario.scenario_id)}
              className={`w-full rounded-2xl px-4 py-3 text-left transition ${
                active
                  ? "bg-slate-900 text-white shadow-[0_20px_40px_-28px_rgba(15,23,42,0.85)]"
                  : "bg-white/70 text-slate-700 ring-1 ring-slate-200/70 hover:bg-white"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold">{scenario.name}</p>
                <span
                  className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                    active ? "bg-white/15 text-white" : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {scenario.status}
                </span>
              </div>
              <p className={`mt-2 text-sm leading-6 ${active ? "text-slate-200" : "text-slate-500"}`}>
                {scenario.description}
              </p>
            </button>
          );
        })}
      </div>
    </section>
  );
}
