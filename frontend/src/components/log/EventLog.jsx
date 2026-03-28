const toneClasses = {
  info: {
    dot: "bg-slate-400",
    chip: "bg-slate-100 text-slate-700",
  },
  warning: {
    dot: "bg-amber-500",
    chip: "bg-amber-100 text-amber-800",
  },
  success: {
    dot: "bg-emerald-500",
    chip: "bg-emerald-100 text-emerald-800",
  },
};

export default function EventLog({ events = [] }) {
  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="mission-label">EventLog</p>
          <h2 className="mission-title">Operational events</h2>
        </div>
        <p className="text-sm text-slate-400">Latest {events.length} mission-control records</p>
      </div>

      <div className="-mx-1 flex gap-3 overflow-x-auto px-1 pb-1">
        {events.map((eventItem) => {
          const tone = toneClasses[eventItem.level] ?? toneClasses.info;

          return (
            <article
              key={eventItem.id}
              className="min-w-[250px] flex-1 rounded-2xl bg-white/75 px-4 py-3 ring-1 ring-slate-200/70"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className={`h-2.5 w-2.5 rounded-full ${tone.dot}`} />
                  <p className="text-sm font-semibold text-slate-900">{eventItem.title}</p>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${tone.chip}`}>
                  {eventItem.timestamp}
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-500">{eventItem.detail}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
