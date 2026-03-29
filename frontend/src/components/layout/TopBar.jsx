export default function TopBar({ title, subtitle, scenarioName }) {
  return (
    <header className="relative border-b border-slate-200/70 bg-white/70 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 px-4 py-5 sm:px-6 lg:flex-row lg:items-end lg:justify-between lg:px-8 xl:py-6">
        <div className="space-y-3">
          <p className="mission-label">LunaPath</p>
          <div>
            <h1 className="text-[clamp(2rem,3vw,2.7rem)] font-semibold tracking-tight text-slate-950">
              {title}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">{subtitle}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3.5 py-2 text-sm text-slate-600 shadow-sm ring-1 ring-slate-200/80">
            <span className="h-2 w-2 rounded-full bg-sky-500" />
            <span>Scenario</span>
            <span className="font-medium text-slate-900">{scenarioName}</span>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50/90 px-3.5 py-2 text-sm font-medium text-emerald-700 ring-1 ring-emerald-200/80">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <span>Mock Data Mode</span>
          </div>
        </div>
      </div>
    </header>
  );
}
