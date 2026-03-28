export default function MissionControlPage() {
  return (
    <div className="bg-slate-50 text-slate-900 overflow-hidden select-none" style={{ height: '100vh', width: '100vw' }}>

      {/* Top Navigation Bar */}
      <header className="fixed top-0 left-0 right-0 h-16 bg-white/80 backdrop-blur-md border-b border-slate-200 z-50 px-6 flex items-center justify-between">
        <div className="flex items-center gap-10">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-slate-900 rounded-lg flex items-center justify-center">
              <span className="material-symbols-outlined text-white text-xl">navigation</span>
            </div>
            <h1 className="text-sm font-bold tracking-tight uppercase">
              LunaPath <span className="font-normal opacity-50">Mission Control</span>
            </h1>
          </div>
          <nav className="hidden lg:flex gap-1 items-center">
            <a className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-900 transition-colors" href="#">Telemetry</a>
            <a className="px-4 py-2 text-xs font-bold text-slate-900 bg-slate-100 rounded-full" href="#">Route Planner</a>
            <a className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-900 transition-colors" href="#">Surface Ops</a>
            <a className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-900 transition-colors" href="#">Archive</a>
          </nav>
        </div>
        <div className="flex items-center gap-6">
          <div className="h-10 flex flex-col justify-center items-end border-r border-slate-200 pr-6">
            <span className="text-[0.6rem] font-bold uppercase tracking-widest text-slate-400">Active Scenario</span>
            <span className="text-xs font-bold">Shackleton Crater - South Rim</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 text-emerald-700 text-[0.65rem] font-bold rounded-md border border-emerald-100">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              REPLANNING: ACTIVE
            </div>
            <button className="p-2 hover:bg-slate-100 rounded-lg text-slate-500 transition-colors">
              <span className="material-symbols-outlined text-lg">settings</span>
            </button>
            <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 overflow-hidden">
              <img
                alt="Commander"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuC9g198cssrJ-P3H6YFAjzymWu8m0OldNqRnKPx1A-6vAKL38-9NkQkMOH3N5Qwtuid-VP1OUan4esLfR4HGsHMsAfyB8zS-gT6LeN-ryJbBfWDk6aFDjJCouDa7uj9J86WrFxyvA60DTfYgeov8lwCh-rKBGAp0RdI2op6RbfOiG8jEKcSbGLf_u_er2CZG8__umXx_GC18xq0LaHmxADKuANWdEirBC5uz-fZB0qjpVEWHo-nqxFNL991cajZLhrZDB07hHXSZOAc"
              />
            </div>
          </div>
        </div>
      </header>

      {/* GIS Map Canvas */}
      <main className="relative w-screen h-screen pt-16 bg-slate-100 overflow-hidden cursor-crosshair">

        {/* Top-Down Analytical Map */}
        <div className="absolute inset-0 map-background">
          <div className="absolute inset-0 topo-shading"></div>

          {/* GIS SVG Layer */}
          <svg
            className="absolute inset-0 w-full h-full"
            preserveAspectRatio="xMidYMid slice"
            viewBox="0 0 1000 1000"
          >
            <defs>
              <radialGradient id="thermalGradient">
                <stop offset="0%" stopColor="#ef4444" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Grid Lines */}
            <path d="M 0 200 L 1000 200 M 0 400 L 1000 400 M 0 600 L 1000 600 M 0 800 L 1000 800" stroke="rgba(0,0,0,0.05)" strokeWidth="1" />
            <path d="M 200 0 L 200 1000 M 400 0 L 400 1000 M 600 0 L 600 1000 M 800 0 L 800 1000" stroke="rgba(0,0,0,0.05)" strokeWidth="1" />

            {/* PSR Regions (Shadow Danger) */}
            <path className="psr-region" d="M 100 100 Q 150 80 200 150 T 300 100 L 280 250 Q 200 280 120 230 Z" />
            <path className="psr-region" d="M 750 600 Q 850 550 900 650 T 800 800 Q 700 750 750 600" />

            {/* Thermal Hazard Map */}
            <circle className="thermal-hazard" cx="450" cy="500" r="150" />
            <circle className="thermal-hazard" cx="550" cy="450" r="100" />

            {/* Shortest / High Risk Route */}
            <path d="M 250 850 L 550 450 L 750 250" fill="none" opacity="0.6" stroke="#ef4444" strokeDasharray="6,4" strokeWidth="1.5" />

            {/* Safe Route */}
            <path d="M 250 850 Q 300 900 400 850 T 500 750" fill="none" stroke="#10b981" strokeWidth="3" />

            {/* Dynamic Replanned Segment */}
            <path d="M 500 750 C 550 650 650 350 750 250" fill="none" stroke="#f59e0b" strokeLinecap="round" strokeWidth="3" />

            {/* Markers */}
            <circle cx="250" cy="850" fill="#1e293b" r="8" stroke="white" strokeWidth="2" /> {/* Start */}
            <circle cx="750" cy="250" fill="#10b981" r="10" stroke="white" strokeWidth="3" /> {/* Goal */}
            <circle cx="500" cy="750" fill="#ef4444" r="5" /> {/* Hazard Point */}
          </svg>

          {/* Map Legend */}
          <div className="absolute bottom-36 left-8 glass-panel p-4 rounded-xl border border-slate-200 text-[0.65rem] font-bold space-y-3">
            <h4 className="uppercase tracking-widest text-slate-400 mb-2">Map Legend</h4>
            <div className="flex items-center gap-2">
              <span className="w-3 h-0.5 bg-emerald-500"></span>
              <span>SAFE PATH</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-0.5 bg-amber-500"></span>
              <span>REPLANNED SEGMENT</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-0.5 bg-red-400 border-dashed border-red-400"></span>
              <span className="text-slate-400">HIGH RISK (ESTIMATED)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-slate-300 opacity-50 border border-slate-400 border-dashed"></span>
              <span>PSR REGION</span>
            </div>
          </div>

          {/* Node Tooltip */}
          <div className="absolute top-[48%] left-[52%] glass-panel px-4 py-3 rounded-xl shadow-xl z-10 min-w-[180px]">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
              <span className="text-[0.65rem] font-black uppercase tracking-widest">Node Analysis: 4-B</span>
            </div>
            <div className="space-y-1.5 text-[0.7rem]">
              <div className="flex justify-between text-slate-500">
                <span>Temp Delta</span>
                <span className="font-bold text-slate-900">+42.4 K</span>
              </div>
              <div className="flex justify-between text-slate-500">
                <span>Elevation</span>
                <span className="font-bold text-slate-900">-4,102 m</span>
              </div>
              <div className="pt-1.5 mt-1.5 border-t border-slate-100 flex justify-between">
                <span className="font-bold text-red-600">RISK FACTOR</span>
                <span className="font-black text-red-600 uppercase">Critical</span>
              </div>
            </div>
          </div>
        </div>

        {/* System Intelligence Module (Left) */}
        <div className="absolute top-8 left-8 w-80 z-20">
          <div className="glass-panel p-6 rounded-2xl shadow-2xl border border-slate-200/50">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center">
                  <span className="material-symbols-outlined text-white text-base">psychology</span>
                </div>
                <div>
                  <h3 className="text-[0.65rem] font-black uppercase tracking-widest text-slate-900">System Intelligence</h3>
                  <p className="text-[0.6rem] text-slate-400">AI AGENT: LUNA-42</p>
                </div>
              </div>
              <span className="px-2 py-0.5 bg-slate-100 rounded text-[0.6rem] font-bold text-slate-500">T+04:22:12</span>
            </div>
            <div className="space-y-4">
              <div className="p-3 bg-red-50 border border-red-100 rounded-xl">
                <p className="text-xs leading-relaxed text-slate-700 font-medium">
                  <span className="text-red-600 font-bold uppercase text-[0.65rem]">Alert:</span>{' '}
                  Thermal spike detected in{' '}
                  <span className="text-slate-900 font-bold underline decoration-red-200">sector 4-B</span>.
                  {' '}Route recomputed to reduce exposure by{' '}
                  <span className="text-emerald-600 font-bold">42%</span>.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-[0.6rem] font-bold text-slate-400 uppercase mb-1">Trigger Type</div>
                  <div className="text-[0.7rem] font-bold text-slate-700">THERMAL_EXT</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <div className="text-[0.6rem] font-bold text-slate-400 uppercase mb-1">Confidence</div>
                  <div className="text-[0.7rem] font-bold text-emerald-600">99.2%</div>
                </div>
              </div>
            </div>
            <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between">
              <span className="text-[0.65rem] font-bold text-slate-400 uppercase tracking-tighter">Status</span>
              <span className="flex items-center gap-1.5 text-[0.65rem] font-black text-emerald-600">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                OPTIMIZED
              </span>
            </div>
          </div>
        </div>

        {/* Precision Control Rail (Right) */}
        <aside className="fixed right-6 top-24 bottom-24 w-20 glass-panel rounded-3xl shadow-2xl flex flex-col items-center py-8 z-40">
          <div className="flex flex-col items-center gap-1 mb-8">
            <div className="w-10 h-10 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center mb-1">
              <span className="material-symbols-outlined text-slate-600">precision_manufacturing</span>
            </div>
            <span className="text-[0.55rem] font-black uppercase text-slate-400">ALPHA-1</span>
          </div>
          <div className="flex flex-col gap-5 flex-1 w-full px-4">
            <button className="flex flex-col items-center gap-1.5 group">
              <div className="w-12 h-12 bg-white border border-slate-200 rounded-2xl flex items-center justify-center text-slate-400 group-hover:bg-slate-50 group-hover:text-slate-900 transition-all shadow-sm">
                <span className="material-symbols-outlined">thermostat</span>
              </div>
              <span className="text-[0.55rem] font-bold text-slate-400 uppercase tracking-tighter">Thermal</span>
            </button>
            <button className="flex flex-col items-center gap-1.5 group">
              <div className="w-12 h-12 bg-white border border-slate-200 rounded-2xl flex items-center justify-center text-slate-400 group-hover:bg-slate-50 transition-all">
                <span className="material-symbols-outlined">terrain</span>
              </div>
              <span className="text-[0.55rem] font-bold text-slate-400 uppercase tracking-tighter">Slope</span>
            </button>
            <button className="flex flex-col items-center gap-1.5 group">
              <div className="w-12 h-12 bg-white border border-slate-200 rounded-2xl flex items-center justify-center text-slate-400 group-hover:bg-slate-50 transition-all">
                <span className="material-symbols-outlined">bolt</span>
              </div>
              <span className="text-[0.55rem] font-bold text-slate-400 uppercase tracking-tighter">Energy</span>
            </button>
            <button className="flex flex-col items-center gap-1.5 group">
              <div className="w-12 h-12 bg-white border border-slate-200 rounded-2xl flex items-center justify-center text-slate-400 group-hover:bg-slate-50 transition-all">
                <span className="material-symbols-outlined">layers</span>
              </div>
              <span className="text-[0.55rem] font-bold text-slate-400 uppercase tracking-tighter">Layers</span>
            </button>
          </div>
          <button className="w-12 h-12 bg-red-500 text-white rounded-2xl shadow-lg shadow-red-200 hover:bg-red-600 transition-all flex flex-col items-center justify-center gap-0.5 active:scale-95">
            <span className="material-symbols-outlined text-lg">bolt</span>
            <span className="text-[0.4rem] font-black">TRIGGER</span>
          </button>
        </aside>

        {/* Weighting Parameters Panel (Right Float) */}
        <div className="absolute right-32 top-1/2 -translate-y-1/2 w-64 z-20">
          <div className="glass-panel p-5 rounded-2xl shadow-xl border border-slate-200/50">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-[0.65rem] font-black uppercase tracking-widest">Weighting Parameters</h3>
              <span className="material-symbols-outlined text-slate-300 text-base">tune</span>
            </div>
            <div className="space-y-6">
              {/* Thermal */}
              <div className="space-y-3">
                <div className="flex justify-between items-center text-[0.6rem] font-bold">
                  <span className="text-slate-400">THERMAL WEIGHT</span>
                  <span className="tabular-nums text-slate-900">85%</span>
                </div>
                <div className="h-1 w-full bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-slate-900 w-[85%]"></div>
                </div>
              </div>
              {/* Slope */}
              <div className="space-y-3">
                <div className="flex justify-between items-center text-[0.6rem] font-bold">
                  <span className="text-slate-400">SLOPE WEIGHT</span>
                  <span className="tabular-nums text-slate-900">42%</span>
                </div>
                <div className="h-1 w-full bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-slate-400 w-[42%]"></div>
                </div>
              </div>
              {/* Energy */}
              <div className="space-y-3">
                <div className="flex justify-between items-center text-[0.6rem] font-bold">
                  <span className="text-slate-400">ENERGY WEIGHT</span>
                  <span className="tabular-nums text-slate-900">68%</span>
                </div>
                <div className="h-1 w-full bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-slate-400 w-[68%]"></div>
                </div>
              </div>
            </div>
            <button className="mt-8 w-full py-2.5 bg-slate-100 hover:bg-slate-200 rounded-xl text-[0.65rem] font-bold text-slate-900 transition-colors uppercase tracking-widest">
              Replan Mission
            </button>
          </div>
        </div>

        {/* Bottom Metrics Bar */}
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 w-[90%] max-w-5xl z-40">
          <div className="glass-panel px-10 py-6 rounded-3xl shadow-2xl border border-slate-200/50 flex items-center justify-between gap-8">
            <div className="flex items-center gap-12">
              <div className="flex flex-col">
                <span className="text-[0.6rem] font-bold uppercase tracking-widest text-slate-400 mb-1">Distance</span>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-extrabold tabular-nums tracking-tight">14.2</span>
                  <span className="text-xs font-bold text-slate-400">km</span>
                </div>
              </div>
              <div className="flex flex-col">
                <span className="text-[0.6rem] font-bold uppercase tracking-widest text-slate-400 mb-1">Thermal Exposure</span>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-extrabold tabular-nums tracking-tight">12</span>
                  <span className="text-xs font-bold text-slate-400">%</span>
                </div>
              </div>
              <div className="flex flex-col">
                <span className="text-[0.6rem] font-bold uppercase tracking-widest text-slate-400 mb-1">Energy Cost</span>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-extrabold tabular-nums tracking-tight">4.8</span>
                  <span className="text-xs font-bold text-slate-400">kWh</span>
                </div>
              </div>
              <div className="flex flex-col">
                <span className="text-[0.6rem] font-bold uppercase tracking-widest text-slate-400 mb-1">Max Slope</span>
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-extrabold tabular-nums tracking-tight">8.2</span>
                  <span className="text-xs font-bold text-slate-400">°</span>
                </div>
              </div>
              <div className="flex flex-col">
                <span className="text-[0.6rem] font-bold uppercase tracking-widest text-slate-400 mb-1">Compute Time</span>
                <div className="flex items-baseline gap-1 text-emerald-600">
                  <span className="text-2xl font-extrabold tabular-nums tracking-tight">142</span>
                  <span className="text-xs font-bold uppercase">ms</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-4 pl-8 border-l border-slate-100">
              <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 text-emerald-600 rounded-full border border-emerald-100">
                <span className="material-symbols-outlined text-sm font-bold">verified</span>
                <span className="text-[0.7rem] font-bold tracking-tight uppercase">Safe Path Preferred</span>
              </div>
              <button className="bg-slate-900 text-white px-8 py-3 rounded-2xl text-[0.7rem] font-bold uppercase tracking-widest hover:bg-slate-800 transition-all shadow-lg active:scale-95">
                Execute Route
              </button>
            </div>
          </div>
        </div>

      </main>
    </div>
  );
}
