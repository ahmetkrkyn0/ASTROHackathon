import { useState, useRef, useEffect, useCallback } from "react";

// ─── Demo rota verisi (Mock — backend bağlandığında burası API'den gelecek) ──────
const SAFE_PATH = "M 250 850 Q 300 900 400 850 T 500 750 C 550 650 650 350 750 250";
const SAFE_PATH_COORDS = [
  [250, 850],[300, 900],[400, 850],[450, 800],[500, 750],
  [550, 680],[600, 580],[660, 440],[710, 340],[750, 250],
];
const SHORT_PATH_COORDS = [
  [250, 850],[350, 720],[450, 580],[550, 450],[650, 340],[750, 250],
];
const INITIAL_METRICS = {
  distance: 14.2, thermal: 12, energy: 4.8, slope: 8.2, compute: 142,
};
const REPLANNED_METRICS = {
  distance: 15.8, thermal: 7, energy: 5.4, slope: 7.1, compute: 218,
};

// ─── Koordinatları viewBox SVG path'ine çevirir ─────────────────────────────
function coordsToPath(coords) {
  return coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c[0]} ${c[1]}`).join(" ");
}

export default function MissionControlPage() {
  // Slider state'leri
  const [weights, setWeights] = useState({ thermal: 85, slope: 42, energy: 68 });

  // Harita pan/zoom state
  const svgRef = useRef(null);
  const isPanning = useRef(false);
  const lastPos = useRef({ x: 0, y: 0 });
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: 1000, h: 1000 });

  // Replan state
  const [replanning, setReplanning] = useState(false);
  const [replanned, setReplanned] = useState(false);
  const [metrics, setMetrics] = useState(INITIAL_METRICS);
  const [replanStatus, setReplanStatus] = useState("OPTIMIZED");

  // ─── Pan handlers ────────────────────────────────────────────────────────
  const onMouseDown = useCallback((e) => {
    // Panel veya buton tıklamasında harita hareketi engellenir
    if (e.target.closest(".map-panel") || e.target.closest("button") || e.target.closest("input")) return;
    isPanning.current = true;
    lastPos.current = { x: e.clientX, y: e.clientY };
    e.currentTarget.style.cursor = "grabbing";
  }, []);

  const onMouseMove = useCallback((e) => {
    if (!isPanning.current) return;
    const dx = e.clientX - lastPos.current.x;
    const dy = e.clientY - lastPos.current.y;
    lastPos.current = { x: e.clientX, y: e.clientY };
    setViewBox((vb) => {
      const scale = vb.w / (svgRef.current?.clientWidth || 1000);
      return { ...vb, x: vb.x - dx * scale, y: vb.y - dy * scale };
    });
  }, []);

  const onMouseUp = useCallback((e) => {
    isPanning.current = false;
    e.currentTarget.style.cursor = "grab";
  }, []);

  // ─── Zoom handler (wheel) ────────────────────────────────────────────────
  const onWheel = useCallback((e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY > 0 ? 1.12 : 0.88;
    setViewBox((vb) => {
      const svgEl = svgRef.current;
      if (!svgEl) return vb;
      const rect = svgEl.getBoundingClientRect();
      // Mouse pozisyonunu SVG koordinatına çevir
      const mouseX = vb.x + ((e.clientX - rect.left) / rect.width) * vb.w;
      const mouseY = vb.y + ((e.clientY - rect.top) / rect.height) * vb.h;
      const newW = Math.min(Math.max(vb.w * zoomFactor, 200), 2000);
      const newH = Math.min(Math.max(vb.h * zoomFactor, 200), 2000);
      return {
        x: mouseX - (mouseX - vb.x) * (newW / vb.w),
        y: mouseY - (mouseY - vb.y) * (newH / vb.h),
        w: newW,
        h: newH,
      };
    });
  }, []);

  // passive: false gerekiyor çünkü preventDefault çağrıyoruz
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [onWheel]);

  // ─── Replan handler ──────────────────────────────────────────────────────
  const handleReplan = () => {
    if (replanning) return;
    setReplanning(true);
    setReplanStatus("REPLANNING...");
    setTimeout(() => {
      setReplanned(true);
      setReplanning(false);
      setReplanStatus("OPTIMIZED");
      setMetrics(REPLANNED_METRICS);
    }, 1800);
  };

  // ─── Rota rengi — thermal ağırlığına göre ────────────────────────────────
  const safeRouteOpacity = (0.5 + (weights.thermal / 100) * 0.5).toFixed(2);
  const safeRouteWidth = (2 + (weights.thermal / 100) * 2).toFixed(1);

  // ─── SVG viewBox string ──────────────────────────────────────────────────
  const viewBoxStr = `${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`;

  return (
    <div className="bg-slate-50 text-slate-900 overflow-hidden select-none" style={{ height: "100vh", width: "100vw" }}>

      {/* ── Top Navigation Bar ─────────────────────────────────────────── */}
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
              <img alt="Commander" src="https://lh3.googleusercontent.com/aida-public/AB6AXuC9g198cssrJ-P3H6YFAjzymWu8m0OldNqRnKPx1A-6vAKL38-9NkQkMOH3N5Qwtuid-VP1OUan4esLfR4HGsHMsAfyB8zS-gT6LeN-ryJbBfWDk6aFDjJCouDa7uj9J86WrFxyvA60DTfYgeov8lwCh-rKBGAp0RdI2op6RbfOiG8jEKcSbGLf_u_er2CZG8__umXx_GC18xq0LaHmxADKuANWdEirBC5uz-fZB0qjpVEWHo-nqxFNL991cajZLhrZDB07hHXSZOAc" />
            </div>
          </div>
        </div>
      </header>

      {/* ── GIS Map Canvas ─────────────────────────────────────────────── */}
      <main className="relative w-screen h-screen pt-16 bg-slate-100 overflow-hidden" style={{ cursor: "grab" }}>
        <div className="absolute inset-0 map-background">
          <div className="absolute inset-0 topo-shading" />

          {/* ── Interactive SVG Map ─────────────────────────────────────── */}
          <svg
            ref={svgRef}
            className="absolute inset-0 w-full h-full"
            viewBox={viewBoxStr}
            preserveAspectRatio="xMidYMid slice"
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseUp}
            style={{ userSelect: "none" }}
          >
            <defs>
              <radialGradient id="thermalGradient">
                <stop offset="0%" stopColor="#ef4444" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
              </radialGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>

            {/* Grid lines */}
            <path d="M 0 200 L 1000 200 M 0 400 L 1000 400 M 0 600 L 1000 600 M 0 800 L 1000 800" stroke="rgba(0,0,0,0.05)" strokeWidth="1" />
            <path d="M 200 0 L 200 1000 M 400 0 L 400 1000 M 600 0 L 600 1000 M 800 0 L 800 1000" stroke="rgba(0,0,0,0.05)" strokeWidth="1" />

            {/* Grid labels */}
            {[200, 400, 600, 800].map((v) => (
              <g key={v}>
                <text x={v} y={15} fontSize="12" fill="rgba(0,0,0,0.15)" textAnchor="middle">{v}</text>
                <text x={8} y={v} fontSize="12" fill="rgba(0,0,0,0.15)" dominantBaseline="middle">{v}</text>
              </g>
            ))}

            {/* PSR Regions */}
            <path className="psr-region" d="M 100 100 Q 150 80 200 150 T 300 100 L 280 250 Q 200 280 120 230 Z" />
            <path className="psr-region" d="M 750 600 Q 850 550 900 650 T 800 800 Q 700 750 750 600" />

            {/* Thermal hazard zones — radius driven by thermal weight */}
            <circle fill="url(#thermalGradient)" opacity={0.3 + (weights.thermal / 100) * 0.3} cx="450" cy="500" r={130 + (weights.thermal / 100) * 40} />
            <circle fill="url(#thermalGradient)" opacity={0.3 + (weights.thermal / 100) * 0.2} cx="550" cy="450" r={80 + (weights.thermal / 100) * 30} />

            {/* Short (High Risk) Route */}
            <path
              d={coordsToPath(SHORT_PATH_COORDS)}
              fill="none"
              opacity={replanned ? 0.25 : 0.55}
              stroke="#ef4444"
              strokeDasharray="6,4"
              strokeWidth="1.5"
              style={{ transition: "opacity 0.8s ease" }}
            />

            {/* Safe Route */}
            <path
              d={SAFE_PATH}
              fill="none"
              stroke="#10b981"
              strokeWidth={safeRouteWidth}
              opacity={safeRouteOpacity}
              style={{ transition: "stroke-width 0.3s, opacity 0.3s" }}
            />

            {/* Replanned Segment */}
            {!replanned && (
              <path
                d="M 500 750 C 550 650 650 350 750 250"
                fill="none"
                stroke="#f59e0b"
                strokeLinecap="round"
                strokeWidth="3"
              />
            )}
            {replanned && (
              <path
                d="M 500 750 C 480 640 520 400 730 250"
                fill="none"
                stroke="#f59e0b"
                strokeLinecap="round"
                strokeWidth="3.5"
                filter="url(#glow)"
                style={{ animation: "none", opacity: 1 }}
              />
            )}

            {/* Markers */}
            <circle cx="250" cy="850" fill="#1e293b" r="8" stroke="white" strokeWidth="2" />
            <text x="250" y="875" fontSize="14" fill="#1e293b" textAnchor="middle" fontWeight="bold">START</text>
            <circle cx="750" cy="250" fill="#10b981" r="10" stroke="white" strokeWidth="3" filter="url(#glow)" />
            <text x="750" y="235" fontSize="14" fill="#10b981" textAnchor="middle" fontWeight="bold">GOAL</text>

            {/* Hazard node — clickable */}
            <circle cx="500" cy="750" fill="#ef4444" r="7" stroke="white" strokeWidth="2" style={{ cursor: "pointer" }} />

            {/* Replan segment midpoint marker */}
            {replanned && (
              <>
                <circle cx="600" cy="490" fill="#f59e0b" r="6" stroke="white" strokeWidth="2" filter="url(#glow)" />
                <text x="620" y="487" fontSize="13" fill="#f59e0b" fontWeight="bold">NEW SEGMENT</text>
              </>
            )}
          </svg>

          {/* ── Map Legend ──────────────────────────────────────────────── */}
          <div className="map-panel absolute bottom-36 left-8 glass-panel p-4 rounded-xl border border-slate-200 text-[0.65rem] font-bold space-y-3 z-10">
            <h4 className="uppercase tracking-widest text-slate-400 mb-2">Map Legend</h4>
            <div className="flex items-center gap-2"><span className="w-3 h-0.5 bg-emerald-500" /><span>SAFE PATH</span></div>
            <div className="flex items-center gap-2"><span className="w-3 h-0.5 bg-amber-500" /><span>REPLANNED SEGMENT</span></div>
            <div className="flex items-center gap-2"><span className="w-3 h-0.5 bg-red-400" /><span className="text-slate-400">HIGH RISK (ESTIMATED)</span></div>
            <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-slate-300 opacity-50 border border-slate-400 border-dashed" /><span>PSR REGION</span></div>
            <div className="pt-2 border-t border-slate-100 text-slate-400">
              <span className="block">🖱 Drag to pan</span>
              <span className="block">⚙ Scroll to zoom</span>
            </div>
          </div>

          {/* ── Node Tooltip ────────────────────────────────────────────── */}
          <div className="map-panel absolute top-[48%] left-[52%] glass-panel px-4 py-3 rounded-xl shadow-xl z-10 min-w-[180px]">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
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

        {/* ── System Intelligence Module (Left) ──────────────────────────── */}
        <div className="map-panel absolute top-8 left-8 w-80 z-20">
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
              <div className={`p-3 rounded-xl border ${replanned ? "bg-emerald-50 border-emerald-100" : "bg-red-50 border-red-100"} transition-colors duration-500`}>
                <p className="text-xs leading-relaxed text-slate-700 font-medium">
                  {replanned ? (
                    <><span className="text-emerald-600 font-bold uppercase text-[0.65rem]">Resolved:</span>{" "}Route successfully recomputed. New segment avoids sector 4-B. Thermal exposure reduced by <span className="text-emerald-600 font-bold">42%</span>.</>
                  ) : (
                    <><span className="text-red-600 font-bold uppercase text-[0.65rem]">Alert:</span>{" "}Thermal spike detected in <span className="text-slate-900 font-bold underline decoration-red-200">sector 4-B</span>. Route recomputed to reduce exposure by <span className="text-emerald-600 font-bold">42%</span>.</>
                  )}
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
              <span className={`flex items-center gap-1.5 text-[0.65rem] font-black ${replanning ? "text-amber-500" : "text-emerald-600"} transition-colors duration-300`}>
                <span className={`w-1.5 h-1.5 rounded-full ${replanning ? "bg-amber-400 animate-pulse" : "bg-emerald-500"}`} />
                {replanStatus}
              </span>
            </div>
          </div>
        </div>

        {/* ── Precision Control Rail (Right) ─────────────────────────────── */}
        <aside className="map-panel fixed right-6 top-24 bottom-24 w-20 glass-panel rounded-3xl shadow-2xl flex flex-col items-center py-8 z-40">
          <div className="flex flex-col items-center gap-1 mb-8">
            <div className="w-10 h-10 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center mb-1">
              <span className="material-symbols-outlined text-slate-600">precision_manufacturing</span>
            </div>
            <span className="text-[0.55rem] font-black uppercase text-slate-400">ALPHA-1</span>
          </div>
          <div className="flex flex-col gap-5 flex-1 w-full px-4">
            {[
              { icon: "thermostat", label: "Thermal" },
              { icon: "terrain", label: "Slope" },
              { icon: "bolt", label: "Energy" },
              { icon: "layers", label: "Layers" },
            ].map(({ icon, label }) => (
              <button key={label} className="flex flex-col items-center gap-1.5 group">
                <div className="w-12 h-12 bg-white border border-slate-200 rounded-2xl flex items-center justify-center text-slate-400 group-hover:bg-slate-50 group-hover:text-slate-900 transition-all shadow-sm">
                  <span className="material-symbols-outlined">{icon}</span>
                </div>
                <span className="text-[0.55rem] font-bold text-slate-400 uppercase tracking-tighter">{label}</span>
              </button>
            ))}
          </div>
          <button className="w-12 h-12 bg-red-500 text-white rounded-2xl shadow-lg shadow-red-200 hover:bg-red-600 transition-all flex flex-col items-center justify-center gap-0.5 active:scale-95">
            <span className="material-symbols-outlined text-lg">bolt</span>
            <span className="text-[0.4rem] font-black">TRIGGER</span>
          </button>
        </aside>

        {/* ── Weighting Parameters Panel ─────────────────────────────────── */}
        <div className="map-panel absolute right-32 top-1/2 -translate-y-1/2 w-64 z-20">
          <div className="glass-panel p-5 rounded-2xl shadow-xl border border-slate-200/50">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-[0.65rem] font-black uppercase tracking-widest">Weighting Parameters</h3>
              <span className="material-symbols-outlined text-slate-300 text-base">tune</span>
            </div>
            <div className="space-y-5">
              {/* Thermal */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-[0.6rem] font-bold">
                  <span className="text-slate-400">THERMAL WEIGHT</span>
                  <span className="tabular-nums text-slate-900">{weights.thermal}%</span>
                </div>
                <input
                  type="range" min="0" max="100" value={weights.thermal}
                  onChange={(e) => setWeights((w) => ({ ...w, thermal: +e.target.value }))}
                  className="w-full h-1 appearance-none rounded-full outline-none cursor-pointer"
                  style={{ background: `linear-gradient(to right, #1e293b ${weights.thermal}%, #e2e8f0 ${weights.thermal}%)` }}
                />
              </div>
              {/* Slope */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-[0.6rem] font-bold">
                  <span className="text-slate-400">SLOPE WEIGHT</span>
                  <span className="tabular-nums text-slate-900">{weights.slope}%</span>
                </div>
                <input
                  type="range" min="0" max="100" value={weights.slope}
                  onChange={(e) => setWeights((w) => ({ ...w, slope: +e.target.value }))}
                  className="w-full h-1 appearance-none rounded-full outline-none cursor-pointer"
                  style={{ background: `linear-gradient(to right, #94a3b8 ${weights.slope}%, #e2e8f0 ${weights.slope}%)` }}
                />
              </div>
              {/* Energy */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-[0.6rem] font-bold">
                  <span className="text-slate-400">ENERGY WEIGHT</span>
                  <span className="tabular-nums text-slate-900">{weights.energy}%</span>
                </div>
                <input
                  type="range" min="0" max="100" value={weights.energy}
                  onChange={(e) => setWeights((w) => ({ ...w, energy: +e.target.value }))}
                  className="w-full h-1 appearance-none rounded-full outline-none cursor-pointer"
                  style={{ background: `linear-gradient(to right, #94a3b8 ${weights.energy}%, #e2e8f0 ${weights.energy}%)` }}
                />
              </div>
            </div>
            <button
              onClick={handleReplan}
              disabled={replanning}
              className="mt-8 w-full py-2.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-60 rounded-xl text-[0.65rem] font-bold text-slate-900 transition-colors uppercase tracking-widest relative overflow-hidden"
            >
              {replanning ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="inline-block w-3 h-3 border-2 border-slate-400 border-t-slate-800 rounded-full animate-spin" />
                  Replanning...
                </span>
              ) : (
                "Replan Mission"
              )}
            </button>
          </div>
        </div>

        {/* ── Bottom Metrics Bar ─────────────────────────────────────────── */}
        <div className="map-panel fixed bottom-8 left-1/2 -translate-x-1/2 w-[90%] max-w-5xl z-40">
          <div className="glass-panel px-10 py-6 rounded-3xl shadow-2xl border border-slate-200/50 flex items-center justify-between gap-8">
            <div className="flex items-center gap-12">
              {[
                { label: "Distance", value: metrics.distance, unit: "km" },
                { label: "Thermal Exposure", value: metrics.thermal, unit: "%" },
                { label: "Energy Cost", value: metrics.energy, unit: "kWh" },
                { label: "Max Slope", value: metrics.slope, unit: "°" },
              ].map(({ label, value, unit }) => (
                <div key={label} className="flex flex-col">
                  <span className="text-[0.6rem] font-bold uppercase tracking-widest text-slate-400 mb-1">{label}</span>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-extrabold tabular-nums tracking-tight" style={{ transition: "all 0.6s ease" }}>{value}</span>
                    <span className="text-xs font-bold text-slate-400">{unit}</span>
                  </div>
                </div>
              ))}
              <div className="flex flex-col">
                <span className="text-[0.6rem] font-bold uppercase tracking-widest text-slate-400 mb-1">Compute Time</span>
                <div className="flex items-baseline gap-1 text-emerald-600">
                  <span className="text-2xl font-extrabold tabular-nums tracking-tight">{metrics.compute}</span>
                  <span className="text-xs font-bold uppercase">ms</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-4 pl-8 border-l border-slate-100">
              <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 text-emerald-600 rounded-full border border-emerald-100">
                <span className="material-symbols-outlined text-sm">verified</span>
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
