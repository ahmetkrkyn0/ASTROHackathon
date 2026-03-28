import { useState, useRef, useEffect, useCallback } from "react";

// ─── Mock metric data ────────────────────────────────────────────────────────
const INITIAL_METRICS = { thermal: 12, slope: 8.2, compute: 142 };
const REPLANNED_METRICS = { thermal: 7, slope: 7.1, compute: 218 };

// ─── Tool config ─────────────────────────────────────────────────────────────
const TOOLS = [
  { id: "start",   icon: "flag",       label: "Start",   desc: "Click to set Start location" },
  { id: "goal",    icon: "sports_score", label: "Goal",  desc: "Click to set Goal location" },
  { id: "thermal", icon: "thermostat", label: "Thermal", desc: "Click to place thermal hazard zone" },
  { id: "crater",  icon: "terrain",    label: "Slope",   desc: "Click to place crater" },
  { id: "shadow",  icon: "layers",     label: "Shadow",  desc: "Click to place PSR shadow region" },
];

const MAP_METERS_PER_UNIT = 17.9;
const CURVE_SEGMENTS = 64;

function getQuadraticLength(start, control, end, segments = CURVE_SEGMENTS) {
  let length = 0;
  let previous = start;

  for (let index = 1; index <= segments; index += 1) {
    const t = index / segments;
    const mt = 1 - t;
    const point = {
      x: (mt * mt * start.x) + (2 * mt * t * control.x) + (t * t * end.x),
      y: (mt * mt * start.y) + (2 * mt * t * control.y) + (t * t * end.y),
    };

    length += Math.hypot(point.x - previous.x, point.y - previous.y);
    previous = point;
  }

  return length;
}

function lerp(start, end, factor) {
  return start + ((end - start) * factor);
}

export default function MissionControlPage() {
  // Weights
  const [weights, setWeights] = useState({ thermal: 85, slope: 42 });

  // Pan/zoom
  const svgRef       = useRef(null);
  const isPanning    = useRef(false);
  const didMove      = useRef(false);
  const lastPos      = useRef({ x: 0, y: 0 });
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: 1000, h: 1000 });

  // Replan
  const [replanning,   setReplanning]   = useState(false);
  const [replanned,    setReplanned]    = useState(false);
  const [metrics,      setMetrics]      = useState(INITIAL_METRICS);
  const [replanStatus, setReplanStatus] = useState("OPTIMIZED");

  // Tooltip hover tracked to mouse position
  const [tooltipData, setTooltipData] = useState(null);

  // Active tool + placed elements
  const [activeTool,    setActiveTool]    = useState(null);
  const [startCoord,    setStartCoord]    = useState({ x: 250, y: 850 });
  const [goalCoord,     setGoalCoord]     = useState({ x: 750, y: 250 });
  const [thermalZones,  setThermalZones]  = useState([]);
  const [craters,       setCraters]       = useState([]);
  const [shadowRegions, setShadowRegions] = useState([]);

  // Convert screen → SVG coordinates
  const screenToSVG = useCallback((clientX, clientY) => {
    const el = svgRef.current;
    if (!el) return { x: 500, y: 500 };
    const point = el.createSVGPoint();
    const ctm = el.getScreenCTM();

    if (!ctm) return { x: 500, y: 500 };

    point.x = clientX;
    point.y = clientY;

    const position = point.matrixTransform(ctm.inverse());
    return { x: position.x, y: position.y };
  }, []);

  // ─── Pan ────────────────────────────────────────────────────────────────
  const onMouseDown = useCallback((e) => {
    if (e.target.closest(".map-panel")) return;
    if (activeTool) {
      didMove.current = false;
      return;
    }
    isPanning.current = true;
    didMove.current   = false;
    lastPos.current   = { x: e.clientX, y: e.clientY };
  }, [activeTool]);

  const onMouseMove = useCallback((e) => {
    if (!isPanning.current) return;
    const dx = e.clientX - lastPos.current.x;
    const dy = e.clientY - lastPos.current.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) didMove.current = true;
    lastPos.current = { x: e.clientX, y: e.clientY };
    setViewBox((vb) => {
      const scale = vb.w / (svgRef.current?.clientWidth || 1000);
      return { ...vb, x: vb.x - dx * scale, y: vb.y - dy * scale };
    });
  }, []);

  const onMouseUp = useCallback(() => { isPanning.current = false; }, []);

  // ─── Zoom ───────────────────────────────────────────────────────────────
  const onWheel = useCallback((e) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 1.12 : 0.88;
    const zoomPoint = screenToSVG(e.clientX, e.clientY);
    setViewBox((vb) => {
      const nw = Math.min(Math.max(vb.w * factor, 200), 2000);
      const nh = Math.min(Math.max(vb.h * factor, 200), 2000);
      return {
        x: zoomPoint.x - ((zoomPoint.x - vb.x) * (nw / vb.w)),
        y: zoomPoint.y - ((zoomPoint.y - vb.y) * (nh / vb.h)),
        w: nw,
        h: nh,
      };
    });
  }, [screenToSVG]);

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [onWheel]);

  // ─── Map click → place element ──────────────────────────────────────────
  const onMapClick = useCallback((e) => {
    if (didMove.current || !activeTool) return;
    if (e.target.closest(".map-panel")) return;
    const pos = screenToSVG(e.clientX, e.clientY);
    
    if (activeTool === "start")   setStartCoord(pos);
    if (activeTool === "goal")    setGoalCoord(pos);
    if (activeTool === "thermal") setThermalZones ((p) => [...p, { ...pos, r: 80 + Math.random()*40, tempDelta: Math.floor(Math.random() * 80) + 10 }]);
    if (activeTool === "crater")  setCraters       ((p) => [...p, { ...pos, slope: Math.floor(Math.random() * 25) + 5, depth: Math.floor(Math.random() * 200) + 50 }]);
    if (activeTool === "shadow")  setShadowRegions ((p) => [...p, { ...pos, temp: -Math.floor(Math.random() * 50) - 150 }]);
  }, [activeTool, screenToSVG]);

  // ─── Dynamic Paths based on Start/Goal ────────────────────────────────
  const midX = (startCoord.x + goalCoord.x) / 2;
  const midY = (startCoord.y + goalCoord.y) / 2;
  const safeControlPoint = {
    x: midX + (100 * (weights.thermal / 100)),
    y: midY + (100 * (weights.thermal / 100)),
  };
  const replannedControlPoint = { x: midX - 250, y: midY - 100 };
  const sectorNode = {
    x: lerp(startCoord.x, goalCoord.x, 0.56),
    y: lerp(startCoord.y, goalCoord.y, 0.56),
  };
  const safePath = `M ${startCoord.x} ${startCoord.y} Q ${safeControlPoint.x} ${safeControlPoint.y} ${goalCoord.x} ${goalCoord.y}`;
  const highRiskPath = `M ${startCoord.x} ${startCoord.y} L ${goalCoord.x} ${goalCoord.y}`;
  const replannedPath = `M ${startCoord.x} ${startCoord.y} Q ${replannedControlPoint.x} ${replannedControlPoint.y} ${goalCoord.x} ${goalCoord.y}`;
  const distanceKm = Number((((replanned
    ? getQuadraticLength(startCoord, replannedControlPoint, goalCoord)
    : getQuadraticLength(startCoord, safeControlPoint, goalCoord))
    * MAP_METERS_PER_UNIT) / 1000).toFixed(1));

  // ─── Replan ─────────────────────────────────────────────────────────────
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

  // ─── Derived visuals ─────────────────────────────────────────────────────
  const routeW   = (2 + (weights.thermal / 100) * 2).toFixed(1);
  const routeOp  = (0.5 + (weights.thermal / 100) * 0.5).toFixed(2);
  const cursor   = activeTool ? "crosshair" : "grab";
  const vbStr    = `${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`;

  // Toggle tool (second click = deactivate)
  const toggleTool = (id) => setActiveTool((curr) => curr === id ? null : id);

  return (
    <div className="bg-slate-50 text-slate-900 overflow-hidden select-none" style={{ height: "100vh", width: "100vw" }}>

      {/* ── Nav ─────────────────────────────────────────────────────────── */}
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
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
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

      {/* ── Main canvas ──────────────────────────────────────────────────── */}
      <main
        className="relative w-screen h-screen pt-16 bg-slate-100 overflow-hidden"
        style={{ cursor }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        onClick={onMapClick}
      >
        <div className="absolute inset-0 map-background">
          <div className="absolute inset-0 topo-shading" />

          {/* ── Active tool hint banner ────────────────────────────────── */}
          {activeTool && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 px-4 py-2 bg-slate-900/90 text-white text-xs font-bold rounded-full backdrop-blur-sm shadow-lg flex items-center gap-2">
              <span className="material-symbols-outlined text-sm">
                {TOOLS.find(t => t.id === activeTool)?.icon}
              </span>
              {TOOLS.find(t => t.id === activeTool)?.desc}
              <button
                onClick={(e) => { e.stopPropagation(); setActiveTool(null); }}
                className="ml-2 w-4 h-4 bg-white/20 rounded-full text-[0.6rem] flex items-center justify-center hover:bg-white/30"
              >✕</button>
            </div>
          )}

          {/* ── SVG map ───────────────────────────────────────────────── */}
          <svg
            ref={svgRef}
            className="absolute inset-0 w-full h-full"
            viewBox={vbStr}
            preserveAspectRatio="xMidYMid slice"
            style={{ userSelect: "none" }}
          >
            <defs>
              <radialGradient id="thermalGradient">
                <stop offset="0%" stopColor="#ef4444" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
              </radialGradient>
              <filter id="glow"><feGaussianBlur stdDeviation="3" result="c"/><feMerge><feMergeNode in="c"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
              
              <pattern id="smallGrid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 40 40 M 0 40 L 40 40" fill="none" stroke="rgba(0,0,0,0.02)" strokeWidth="0.5"/>
              </pattern>
              <pattern id="gridPattern" width="200" height="200" patternUnits="userSpaceOnUse">
                <rect width="200" height="200" fill="url(#smallGrid)"/>
                <path d="M 200 0 L 200 200 M 0 200 L 200 200" fill="none" stroke="rgba(0,0,0,0.06)" strokeWidth="1"/>
              </pattern>
            </defs>

            {/* Infinite Grid */}
            <rect x="-50000" y="-50000" width="100000" height="100000" fill="url(#gridPattern)" />

            {/* ── Static PSR regions ──────────────────────────────────── */}
            <path className="psr-region" d="M 100 100 Q 150 80 200 150 T 300 100 L 280 250 Q 200 280 120 230 Z" />
            <path className="psr-region" d="M 750 600 Q 850 550 900 650 T 800 800 Q 700 750 750 600" />

            {/* ── Static thermal hazards ──────────────────────────────── */}
            <circle fill="url(#thermalGradient)" opacity={0.3 + (weights.thermal/100)*0.3} cx="450" cy="500" r={130 + (weights.thermal/100)*40} />
            <circle fill="url(#thermalGradient)" opacity={0.2 + (weights.thermal/100)*0.2} cx="550" cy="450" r={80  + (weights.thermal/100)*30} />

            {/* ── USER-placed thermal zones ────────────────────────────── */}
            {thermalZones.map((z, i) => (
              <g key={`th-${i}`}
                 style={{ cursor: "pointer" }}
                 onMouseEnter={(e) => setTooltipData({ x: e.clientX, y: e.clientY, title: `THERMAL ZONE ${i+1}`, lines: [{label: "Temp Delta", value: `+${z.tempDelta} K`}, {label:"Radius", value:`${Math.round(z.r)} m`}], risk: "CRITICAL" })}
                 onMouseMove={(e) => setTooltipData(prev => prev ? { ...prev, x: e.clientX, y: e.clientY } : null)}
                 onMouseLeave={() => setTooltipData(null)}>
                <circle fill="url(#thermalGradient)" opacity="0.55" cx={z.x} cy={z.y} r={z.r} />
                <circle fill="none" stroke="#ef4444" strokeWidth="0.8" strokeDasharray="4 2" opacity="0.5" cx={z.x} cy={z.y} r={z.r} />
                <text x={z.x} y={z.y - z.r - 6} fontSize="11" fill="#ef4444" textAnchor="middle" fontWeight="bold">THERMAL</text>
              </g>
            ))}

            {/* ── USER-placed craters ──────────────────────────────────── */}
            {craters.map((c, i) => (
              <g key={`cr-${i}`}
                 style={{ cursor: "pointer" }}
                 onMouseEnter={(e) => setTooltipData({ x: e.clientX, y: e.clientY, title: `CRATER ${i+1}`, lines: [{label: "Slope", value: `${c.slope}\u00b0`}, {label:"Depth", value:`${c.depth} m`}], risk: "HIGH" })}
                 onMouseMove={(e) => setTooltipData(prev => prev ? { ...prev, x: e.clientX, y: e.clientY } : null)}
                 onMouseLeave={() => setTooltipData(null)}>
                <ellipse cx={c.x} cy={c.y} rx="60" ry="40" fill="rgba(30,41,59,0.18)" stroke="rgba(30,41,59,0.35)" strokeWidth="1" strokeDasharray="4 2" />
                <ellipse cx={c.x} cy={c.y} rx="30" ry="20" fill="rgba(30,41,59,0.28)" />
                <text x={c.x} y={c.y - 48} fontSize="11" fill="#475569" textAnchor="middle" fontWeight="bold">CRATER</text>
              </g>
            ))}

            {/* ── USER-placed shadow / PSR regions ───────────────────── */}
            {shadowRegions.map((s, i) => (
              <g key={`sh-${i}`}
                 style={{ cursor: "pointer" }}
                 onMouseEnter={(e) => setTooltipData({ x: e.clientX, y: e.clientY, title: `PSR REGION ${i+1}`, lines: [{label: "Surface Temp", value: `${s.temp} C`}], risk: "MODERATE" })}
                 onMouseMove={(e) => setTooltipData(prev => prev ? { ...prev, x: e.clientX, y: e.clientY } : null)}
                 onMouseLeave={() => setTooltipData(null)}>
                <ellipse cx={s.x} cy={s.y} rx="70" ry="50" fill="rgba(30,41,59,0.15)" stroke="rgba(30,41,59,0.3)" strokeWidth="1" strokeDasharray="4 2" />
                <text x={s.x} y={s.y - 56} fontSize="11" fill="#64748b" textAnchor="middle" fontWeight="bold">PSR SHADOW</text>
              </g>
            ))}

            {/* ── Routes ──────────────────────────────────────────────── */}
            {/* Short / high risk */}
            <path d={highRiskPath} fill="none" opacity={replanned ? 0.2 : 0.55} stroke="#ef4444" strokeDasharray="6,4" strokeWidth="1.5" style={{ transition: "d 0.3s, opacity 0.8s" }} />

            {/* Safe route */}
            <path d={safePath} fill="none" stroke="#10b981" strokeWidth={routeW} opacity={routeOp} style={{ transition: "d 0.3s, stroke-width 0.3s, opacity 0.3s" }} />

            {/* Replanned segment */}
            {!replanned && <path d={safePath} fill="none" stroke="#f59e0b" strokeLinecap="round" strokeWidth="3" opacity="0" />}
            {replanned && (
              <>
                <path d={replannedPath} fill="none" stroke="#f59e0b" strokeLinecap="round" strokeWidth="3.5" filter="url(#glow)" style={{ transition: "d 0.3s" }} />
                <circle cx={(startCoord.x + goalCoord.x)/2 - 125} cy={(startCoord.y + goalCoord.y)/2 - 50} fill="#f59e0b" r="6" stroke="white" strokeWidth="2" filter="url(#glow)" />
                <text x={(startCoord.x + goalCoord.x)/2 - 105} y={(startCoord.y + goalCoord.y)/2 - 47} fontSize="12" fill="#f59e0b" fontWeight="bold">NEW SEGMENT</text>
              </>
            )}

            {/* Goal Marker */}
            <circle cx={goalCoord.x} cy={goalCoord.y} fill="#10b981" r="14" stroke="white" strokeWidth="3" filter="url(#glow)" />
            <text x={goalCoord.x} y={goalCoord.y - 20} fontSize="13" fill="#10b981" textAnchor="middle" fontWeight="bold">GOAL</text>

            {/* Start Marker & Rover Icon */}
            <g transform={`translate(${startCoord.x}, ${startCoord.y})`} style={{ pointerEvents: "none" }}>
              <ellipse cx="0" cy="18" rx="24" ry="12" fill="rgba(0,0,0,0.15)" />
              {/* Wheels */}
              <rect x="-16" y="8" width="8" height="12" rx="2" fill="#334155" />
              <rect x="8" y="8" width="8" height="12" rx="2" fill="#334155" />
              <rect x="-18" y="0" width="6" height="10" rx="1.5" fill="#475569" />
              <rect x="12" y="0" width="6" height="10" rx="1.5" fill="#475569" />
              {/* Body */}
              <rect x="-12" y="-4" width="24" height="16" rx="3" fill="#f8fafc" stroke="#cbd5e1" strokeWidth="1" />
              {/* Solar Panel */}
              <rect x="-8" y="-10" width="16" height="10" rx="1" fill="#0ea5e9" opacity="0.9" />
              <path d="M-8 -6 L8 -6 M-4 -10 L-4 0 M4 -10 L4 0" stroke="rgba(255,255,255,0.3)" strokeWidth="0.5" />
              {/* Antenna */}
              <line x1="-10" y1="-4" x2="-14" y2="-16" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" />
              <circle cx="-14" cy="-16" r="2" fill="#ef4444" />
              <text x="0" y="42" fontSize="13" fill="#1e293b" textAnchor="middle" fontWeight="bold">START / ROVER</text>
            </g>

            {/* Hazard marker — hover triggers tooltip */}
            <circle
              cx={sectorNode.x} cy={sectorNode.y} fill="#ef4444" r="8" stroke="white" strokeWidth="2"
              style={{ cursor: "pointer" }}
              onMouseEnter={(e) => setTooltipData({ x: e.clientX, y: e.clientY, title: `NODE: 4-B`, lines: [{label: "Temp Delta", value: `+42.4 K`}, {label:"Elevation", value:`-4,102 m`}], risk: "CRITICAL" })}
              onMouseMove={(e) => setTooltipData(prev => prev ? { ...prev, x: e.clientX, y: e.clientY } : null)}
              onMouseLeave={() => setTooltipData(null)}
            />
            <text x={sectorNode.x + 14} y={sectorNode.y + 4} fontSize="11" fill="#b91c1c" fontWeight="bold">SECTOR 4-B</text>
          </svg>

          {/* ── Cursor-tracking Tooltip ─────────────────────────────────── */}
          {tooltipData && (
            <div
              className="map-panel absolute glass-panel px-4 py-3 rounded-xl shadow-xl z-50 min-w-[200px] pointer-events-none backdrop-blur-md"
              style={{ top: tooltipData.y + 15, left: tooltipData.x + 15, transform: "translate(0, 0)" }}
            >
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-2 h-2 rounded-full animate-pulse ${tooltipData.risk === 'CRITICAL' ? 'bg-red-500' : tooltipData.risk === 'SAFE' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                <span className="text-[0.65rem] font-black uppercase tracking-widest">{tooltipData.title}</span>
              </div>
              <div className="space-y-1.5 text-[0.7rem]">
                {tooltipData.lines.map((line, idx) => (
                  <div key={idx} className="flex justify-between text-slate-500 gap-4">
                    <span>{line.label}</span><span className="font-bold text-slate-900">{line.value}</span>
                  </div>
                ))}
                <div className="pt-1.5 mt-1.5 border-t border-slate-100 flex justify-between items-center">
                  <span className="text-[0.6rem] font-bold text-slate-400 uppercase tracking-widest">RISK FACTOR</span>
                  <span className={`text-[0.65rem] font-black uppercase tracking-widest ${tooltipData.risk === 'CRITICAL' ? 'text-red-600' : tooltipData.risk === 'SAFE' ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {tooltipData.risk}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* ── Map Legend ───────────────────────────────────────────────── */}
          <div className="map-panel absolute bottom-36 left-8 glass-panel p-4 rounded-xl border border-slate-200 text-[0.65rem] font-bold space-y-2.5 z-10">
            <h4 className="uppercase tracking-widest text-slate-400 mb-1">Map Legend</h4>
            <div className="flex items-center gap-2"><span className="w-3 h-0.5 bg-emerald-500"/><span>SAFE PATH</span></div>
            <div className="flex items-center gap-2"><span className="w-3 h-0.5 bg-amber-500"/><span>REPLANNED SEGMENT</span></div>
            <div className="flex items-center gap-2"><span className="w-3 h-0.5 bg-red-400"/><span className="text-slate-400">HIGH RISK</span></div>
            <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-slate-300 opacity-50 border border-slate-400 border-dashed"/><span>PSR REGION</span></div>
            <div className="pt-2 border-t border-slate-100 text-slate-400 space-y-0.5">
              <span className="block">🖱 Drag → pan</span><span className="block">⚙ Scroll → zoom</span>
            </div>
          </div>
        </div>

        {/* ── System Intelligence Panel ─────────────────────────────────── */}
        <div className="map-panel absolute left-8 w-80 z-20" style={{ top: "calc(4rem + 1.5rem)" }}>
          <div className="glass-panel p-5 rounded-2xl shadow-2xl border border-slate-200/50">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center flex-shrink-0">
                  <span className="material-symbols-outlined text-white text-base">psychology</span>
                </div>
                <div>
                  <h3 className="text-[0.65rem] font-black uppercase tracking-widest text-slate-900">System Intelligence</h3>
                  <p className="text-[0.6rem] text-slate-400">AI AGENT: LUNA-42</p>
                </div>
              </div>
              <span className="px-2 py-0.5 bg-slate-100 rounded text-[0.6rem] font-bold text-slate-500 flex-shrink-0">T+04:22:12</span>
            </div>
            <div className={`p-3 rounded-xl border text-xs leading-relaxed font-medium transition-colors duration-500 ${replanned ? "bg-emerald-50 border-emerald-100 text-slate-700" : "bg-red-50 border-red-100 text-slate-700"}`}>
              {replanned
                ? <><span className="text-emerald-600 font-bold uppercase text-[0.65rem]">Resolved: </span>Route recomputed. Sector 4-B avoided. Thermal exposure reduced by <span className="text-emerald-600 font-bold">42%</span>.</>
                : <><span className="text-red-600 font-bold uppercase text-[0.65rem]">Alert: </span>Thermal spike in <span className="font-bold underline decoration-red-200">sector 4-B</span>. Route recomputed — exposure reduced by <span className="text-emerald-600 font-bold">42%</span>.</>
              }
            </div>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div className="text-[0.6rem] font-bold text-slate-400 uppercase mb-1">Trigger Type</div>
                <div className="text-[0.7rem] font-bold text-slate-700">THERMAL_EXT</div>
              </div>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div className="text-[0.6rem] font-bold text-slate-400 uppercase mb-1">Confidence</div>
                <div className="text-[0.7rem] font-bold text-emerald-600">99.2%</div>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
              <span className="text-[0.65rem] font-bold text-slate-400 uppercase tracking-tighter">Status</span>
              <span className={`flex items-center gap-1.5 text-[0.65rem] font-black transition-colors ${replanning ? "text-amber-500" : "text-emerald-600"}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${replanning ? "bg-amber-400 animate-pulse" : "bg-emerald-500"}`} />
                {replanStatus}
              </span>
            </div>
          </div>
        </div>

        {/* ── Right Control Rail ───────────────────────────────────────────── */}
        <aside className="map-panel fixed right-6 top-24 bottom-24 w-20 glass-panel rounded-3xl shadow-2xl flex flex-col items-center py-6 z-40">
          <div className="flex flex-col items-center gap-1 mb-6">
            <div className="w-10 h-10 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center mb-0.5">
              <span className="material-symbols-outlined text-slate-600">precision_manufacturing</span>
            </div>
            <span className="text-[0.55rem] font-black uppercase text-slate-400">ALPHA-1</span>
          </div>

          <div className="flex flex-col gap-4 flex-1 w-full px-3">
            {TOOLS.map(({ id, icon, label }) => {
              const isActive = activeTool === id;
              return (
                <button
                  key={id}
                  onClick={(e) => { e.stopPropagation(); toggleTool(id); }}
                  title={`${label} — click to ${isActive ? "deactivate" : "activate"}`}
                  className="flex flex-col items-center gap-1 group relative"
                >
                  <div className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-all shadow-sm border
                    ${isActive
                      ? "bg-slate-900 border-slate-900 text-white shadow-md scale-110"
                      : "bg-white border-slate-200 text-slate-400 group-hover:bg-slate-50 group-hover:text-slate-900"}`}>
                    <span className="material-symbols-outlined">{icon}</span>
                  </div>
                  <span className={`text-[0.55rem] font-bold uppercase tracking-tighter ${isActive ? "text-slate-900" : "text-slate-400"}`}>{label}</span>
                  {isActive && <span className="absolute -left-1 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-slate-900" />}
                </button>
              );
            })}
          </div>

          <button
            onClick={(e) => { e.stopPropagation(); handleReplan(); }}
            className="w-12 h-12 bg-red-500 text-white rounded-2xl shadow-lg shadow-red-200 hover:bg-red-600 transition-all flex flex-col items-center justify-center gap-0.5 active:scale-95"
          >
            <span className="material-symbols-outlined text-lg">bolt</span>
            <span className="text-[0.4rem] font-black">TRIGGER</span>
          </button>
        </aside>

        {/* ── Weighting Parameters ─────────────────────────────────────────── */}
        <div className="map-panel absolute right-32 top-1/2 -translate-y-1/2 w-64 z-20">
          <div className="glass-panel p-5 rounded-2xl shadow-xl border border-slate-200/50">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-[0.65rem] font-black uppercase tracking-widest">Weighting Parameters</h3>
              <span className="material-symbols-outlined text-slate-300 text-base">tune</span>
            </div>
            <div className="space-y-5">
              {[
                { key: "thermal", label: "THERMAL WEIGHT", color: "#1e293b" },
                { key: "slope",   label: "SLOPE WEIGHT",   color: "#94a3b8" },
              ].map(({ key, label, color }) => (
                <div key={key} className="space-y-2">
                  <div className="flex justify-between items-center text-[0.6rem] font-bold">
                    <span className="text-slate-400">{label}</span>
                    <span className="tabular-nums text-slate-900">{weights[key]}%</span>
                  </div>
                  <input
                    type="range" min="0" max="100" value={weights[key]}
                    onChange={(e) => setWeights((w) => ({ ...w, [key]: +e.target.value }))}
                    onClick={(e) => e.stopPropagation()}
                    className="w-full h-1 appearance-none rounded-full outline-none cursor-pointer"
                    style={{ background: `linear-gradient(to right, ${color} ${weights[key]}%, #e2e8f0 ${weights[key]}%)` }}
                  />
                </div>
              ))}
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); handleReplan(); }}
              disabled={replanning}
              className="mt-6 w-full py-2.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-60 rounded-xl text-[0.65rem] font-bold text-slate-900 transition-colors uppercase tracking-widest"
            >
              {replanning
                ? <span className="flex items-center justify-center gap-2">
                    <span className="w-3 h-3 border-2 border-slate-400 border-t-slate-800 rounded-full animate-spin inline-block" />
                    Replanning...
                  </span>
                : "Replan Mission"}
            </button>
          </div>
        </div>

        {/* ── Bottom Metrics Bar ───────────────────────────────────────────── */}
        <div className="map-panel fixed bottom-8 left-1/2 -translate-x-1/2 w-[90%] max-w-5xl z-40">
          <div className="glass-panel px-8 py-5 rounded-3xl shadow-2xl border border-slate-200/50 flex items-center justify-between gap-6">
            <div className="flex items-center gap-10">
              {[
                { label: "Distance",         value: distanceKm,       unit: "km" },
                { label: "Thermal Exposure", value: metrics.thermal,  unit: "%" },
                { label: "Max Slope",        value: metrics.slope,    unit: "\u00b0" },
              ].map(({ label, value, unit }) => (
                <div key={label} className="flex flex-col">
                  <span className="text-[0.6rem] font-bold uppercase tracking-widest text-slate-400 mb-1 whitespace-nowrap">{label}</span>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-extrabold tabular-nums tracking-tight">{value}</span>
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
            <div className="flex items-center gap-3 pl-6 border-l border-slate-100 flex-shrink-0">
              <div className="flex items-center gap-2 px-3 py-2 bg-emerald-50 text-emerald-600 rounded-full border border-emerald-100">
                <span className="material-symbols-outlined text-sm">verified</span>
                <span className="text-[0.65rem] font-bold tracking-tight uppercase whitespace-nowrap">Safe Path Preferred</span>
              </div>
              <button
                onClick={(e) => e.stopPropagation()}
                className="bg-slate-900 text-white px-6 py-3 rounded-2xl text-[0.65rem] font-bold uppercase tracking-widest hover:bg-slate-800 transition-all shadow-lg active:scale-95 whitespace-nowrap"
              >
                Execute Route
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
