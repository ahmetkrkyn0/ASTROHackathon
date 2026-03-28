import PanelCard from "../layout/PanelCard";

const toneClasses = {
  info: "bg-slate-100 text-slate-700",
  warning: "bg-amber-100 text-amber-800",
  success: "bg-emerald-100 text-emerald-800",
};

export default function EventLog({ events = [] }) {
  return (
    <PanelCard
      title="EventLog"
      description="Manual trigger history and replanning notes for the prototype session."
      contentClassName="space-y-3"
    >
      {events.map((eventItem) => (
        <article key={eventItem.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium text-slate-900">{eventItem.title}</p>
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${toneClasses[eventItem.level] ?? toneClasses.info}`}
            >
              {eventItem.timestamp}
            </span>
          </div>
          <p className="mt-2 text-sm text-slate-600">{eventItem.detail}</p>
        </article>
      ))}
    </PanelCard>
  );
}
