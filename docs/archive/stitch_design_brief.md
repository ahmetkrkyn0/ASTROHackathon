# LunaPath Frontend Design Brief v2

## Project Overview
LunaPath is an adaptive route planning system for autonomous lunar rovers operating on the Moon's South Pole. The UI should feel like you're sitting in a real lunar mission control room — not a web app with a map widget, but a **full-screen immersive cockpit** for planetary exploration.

## Tech Stack
- React 18 + TypeScript + Vite
- Canvas-based map rendering (500x500 pixel grid, 80m/px resolution)
- Backend: FastAPI on port 8000 (already built)

## Target Audience
Hackathon judges, space engineers. First impression matters — the map should dominate the screen and look cinematic.

---

## CRITICAL DESIGN DIRECTION

### The Map is THE Product
The map is not a sidebar widget. It is the **full centerpiece** of the application, taking up 65-70% of the screen. Think Google Earth for the Moon — immersive, zoomable, explorable.

### Two Map Modes (Layer Toggle)
The map has two visual modes that the user can switch between:

1. **Lunar Surface Mode (Default)** — Realistic topographic rendering of the Moon's south pole. Rich earth-tone colormap showing actual lunar terrain: deep greens/teals for low elevation valleys, warm oranges/reds for ridges and crater rims, yellows for mid-elevation plateaus. This looks like a real satellite/DEM visualization — the kind you'd see in a NASA press release. Craters, ridges, and terrain features are clearly visible. This is the "wow factor" view.

2. **Analysis Overlay Mode** — When toggled, semi-transparent analytical layers appear OVER the base terrain:
   - Slope hazard overlay (red zones for steep areas)
   - Thermal risk heatmap (blue=cold, red=hot)
   - Traversability mask (blocked areas dimmed/hatched)
   - Shadow ratio overlay (dark = permanent shadow regions)
   - Cost grid visualization

The user switches between these using a **floating layer control** (like Google Maps layer button) on the map itself — not buried in a sidebar.

### Map Interaction
- **Zoom in/out** with mouse wheel or +/- buttons (floating on map corner)
- **Pan/drag** the map to explore terrain
- **Click to place** Start (green pin) and Goal (red pin) markers
- **Hover tooltip** showing coordinates, elevation, slope at cursor position
- Route drawn as a glowing line over the terrain, color-coded by risk level (green->yellow->orange->red segments)
- Rover animation dot traveling along the route after calculation

### Map UI Overlays (Floating on the Map)
These elements float OVER the map canvas, not in separate panels:
- **Top-left**: Coordinate readout box (LAT, LON, ALT of cursor) — dark translucent background
- **Top-right**: Zoom controls (+/-) and Layer toggle button
- **Bottom-center**: Legend bar (Safe / Caution / Steep / Critical color scale)
- **Bottom-left**: Scale bar (distance reference)

---

## Layout Structure

This is NOT a traditional 3-column layout. The map dominates:

```
+============================================================================+
|  HEADER BAR (slim, 48px)                                                    |
|  [LUNAPATH logo]  [LUNAR SOUTH POLE ROUTE PLANNER]    [CONNECTED] [UTC]    |
+============================================================================+
|          |                                                    |             |
|  LEFT    |              MAIN MAP CANVAS                       |   RIGHT     |
|  PANEL   |              (fills all remaining space)           |   PANEL     |
|  240px   |                                                    |   280px     |
|          |    +--floating overlays on map--+                  |             |
|  Mission |    | coords | zoom | layers    |                  |  Mission    |
|  Controls|    +---------------------------+                  |  Telemetry  |
|          |                                                    |             |
|          |         [terrain with route]                       |  Path info  |
|          |                                                    |  Energy     |
|          |                                                    |  Risk       |
|          |    +--legend bar--+                                |  Waypoints  |
|          |                                                    |             |
+============================================================================+
|  FOOTER STATUS BAR (24px) — system log, diagnostics, UTC clock             |
+============================================================================+
```

**Key proportions:**
- Header: 48px fixed
- Left sidebar: 240px fixed, collapsible
- Right panel: 280px fixed, collapsible
- Map: ALL remaining space (stretches with window)
- Footer: 24px fixed

---

## Component Specifications

### A. Header Bar (48px height)
- Background: #0a0a1a with subtle bottom border glow (#1a1a4a)
- Left: "LUNAPATH" in bold, letter-spacing 6px, color #a0a0ff, font-size 20px
- Left subtitle: "LUNAR SOUTH POLE ROUTE PLANNER" in #505070, font-size 11px, uppercase
- Right: Connection status badge — green dot + "CONNECTED" or red dot + "DISCONNECTED"
- Far right: Grid info "500x500 · 80m/px" and live UTC clock

### B. Left Sidebar — Mission Controls (240px)
Background: #0a0a18, border-right: 1px solid #1a1a3a
Scrollable, all sections collapsible with subtle animation.

**Section 1: Mission Profile Selector**
- 4 profile cards stacked vertically (not a dropdown)
- Each card: icon + profile name + one-line description
- Selected card has left accent border in profile color and slightly brighter background
- Cards:
  - Balanced (blue #3B82F6) — balanced scale icon — "All risks weighted equally"
  - Energy Saver (green #22C55E) — battery icon — "Maximize battery life"
  - Fast Recon (red #EF4444) — lightning icon — "Shortest viable path"
  - Shadow Traverse (purple #A855F7) — moon/shadow icon — "Thermal safety priority"

**Section 2: Cost Weight Sliders**
- Compact card with dark background (#0e0e20)
- Title: "COST WEIGHTS" in uppercase, tiny, muted
- 4 sliders: SLOPE, ENERGY, SHADOW, THERMAL
- Each: label left, slider middle, value right (e.g., "0.409")
- Slider accent color matches the dominant weight's profile color
- Range: 0.0 to 2.0, step 0.01
- Auto-fills when profile changes, but user can manually override

**Section 3: Actions**
- "CALCULATE ROUTE" — full-width primary button, prominent
  - Default: #1a1a4a background, #a0a0ff text, subtle border
  - Hover: brighter, slight glow
  - Loading: pulse animation, text changes to "COMPUTING A*..."
  - Disabled (no start/goal): dimmed, cursor not-allowed
- "SET START" and "SET GOAL" — two buttons side by side below
  - SET START: green accent (#00e676) when active
  - SET GOAL: red accent (#ff1744) when active
  - Show coordinates when set: "START (125, 340)"
- "RESET" — ghost button, very subtle

### C. Main Map Canvas (Central, Dominant)
**This is the hero element.** It fills ALL space between left and right panels.

**Visual Style:**
- The base terrain rendering uses the rich topographic colormap from our DEM data:
  - Deep teal/green (#1e5546) for low valleys
  - Olive/sage (#509640) for gentle slopes
  - Yellow (#beb414) for mid-elevation
  - Orange (#d26e00) for steep ridges
  - Dark red (#5a0505, #be2800) for impassable crater walls
- This creates a natural, satellite-imagery-like appearance
- Blocked/impassable areas are subtly darkened (not bright red — more like shadowed)

**Floating Map Controls (on the map canvas):**
- **Coordinate Box** (top-left, floating): Semi-transparent dark panel showing LAT, LON, ALT of current cursor position. Updates on mouse move. Font: monospace, small.
- **Zoom Controls** (top-right, floating): + and - buttons, stacked vertically, with subtle glass-morphism background
- **Layer Toggle** (top-right, below zoom): Icon button that opens a small floating panel with toggle switches for each analysis layer
- **Legend** (bottom-center, floating): Horizontal color-coded legend — "SAFE · CAUTION · STEEP · CRITICAL" with corresponding colored dots/bars

**Route Rendering:**
- Path drawn as a 3px line with subtle outer glow
- Color transitions smoothly based on risk level of each segment:
  - LOW: #00e676 (green) with green glow
  - MEDIUM: #ffea00 (yellow) with yellow glow
  - HIGH: #ff6d00 (orange) with orange glow
  - CRITICAL: #ff1744 (red) with red glow
- Dashed line style for the portions ahead of the rover during animation
- Solid line for already-traversed portions

**Markers:**
- Start: Green circle with "S" label, subtle green glow/pulse
- Goal: Red circle with "G" label, subtle red glow/pulse
- Both markers should look like mission waypoint pins — not generic map markers

**Rover Animation:**
- White filled circle (4px radius) with colored ring matching current risk level
- Leaves a solid trail behind it
- Smooth ~30fps movement along the path

### D. Right Panel — Mission Telemetry (280px)
Background: #0a0a18, border-left: 1px solid #1a1a3a
Header: "MISSION TELEMETRY" + "REAL-TIME ANALYSIS" subtitle

**Section 1: Path Overview**
Two-column grid layout:
```
DISTANCE        DURATION
12,450 M        18.25 H

WAYPOINTS       NODES
156             24,891

COMP. TIME
1,240 MS (green accent color)
```

**Section 2: Energy Dashboard**
- Circular battery gauge (ring/donut chart style)
  - Center: "67.3%" large text
  - Ring: gradient from green to yellow based on level
- Side metrics:
  - "MIN BATTERY: 42.1%" (yellow colored)
  - "EST. CONSUMPTION: 142 Wh/km"

**Section 3: Risk Assessment**
- Horizontal stacked bar showing risk distribution
  - Green (LOW) | Yellow (MEDIUM) | Orange (HIGH) | Red (CRITICAL)
  - Proportional widths
- Below: 2x2 grid with counts
  ```
  LOW      MED
  120      28

  HIGH     CRIT
  6        2
  ```
  Each cell has a left-border accent in its risk color

**Section 4: Waypoint Inspector**
- Scrollable table at the bottom of the right panel
- Title: "WAYPOINT INSPECTOR" with a small table icon
- Columns: ID, COORD, SLOPE
- Each row shows: WP_001, "85.34S, 10.2E", "2.4°"
- Rows with HIGH/CRITICAL risk are highlighted (darker red background, brighter text)
- Clicking a row highlights/zooms to that waypoint on the map

### E. Footer Status Bar (24px)
- Background: #060610
- Left: System log text — "SYSTEM LOG: V4.2.0-LUNAR // NODE_SEC_7 // STABLE" in green monospace (#00e676)
- Right: Tab-style links — "EVENT_LOG | COORDINATES | DIAGNOSTICS" + UTC timestamp
- This adds the "mission control room" feel

---

## Color System

### Base Theme
| Token | Hex | Usage |
|---|---|---|
| bg-primary | #080810 | App background |
| bg-secondary | #0a0a18 | Panels, sidebar |
| bg-surface | #0e0e20 | Cards, inputs, elevated surfaces |
| bg-overlay | rgba(8,8,16,0.85) | Floating elements on map |
| border-default | #1a1a3a | Panel borders, dividers |
| border-accent | #2a2a5a | Active/hover borders |
| text-primary | #c8c8dc | Body text |
| text-secondary | #808098 | Descriptions |
| text-muted | #505070 | Labels, hints |
| accent-primary | #a0a0ff | Headers, active states, links |
| accent-glow | #6060ff | Subtle glows, active borders |

### Semantic Colors
| Token | Hex | Usage |
|---|---|---|
| safe / low-risk | #00e676 | Safe terrain, low risk, start marker |
| caution / medium-risk | #ffea00 | Medium risk, moderate slopes |
| danger / high-risk | #ff6d00 | High risk, steep terrain |
| critical | #ff1744 | Critical risk, goal marker, blocked terrain |

### Mission Profile Colors
| Profile | Hex | Usage |
|---|---|---|
| Balanced | #3B82F6 | Profile card accent, route overlay |
| Energy Saver | #22C55E | Profile card accent, route overlay |
| Fast Recon | #EF4444 | Profile card accent, route overlay |
| Shadow Traverse | #A855F7 | Profile card accent, route overlay |

---

## Typography
- Primary font: `'JetBrains Mono', 'Fira Code', 'Courier New', monospace`
- All caps for section headers, labels, and status text
- Letter-spacing: 2-4px for headers, 1px for labels
- Font sizes: 20px header logo, 13px body, 11px labels, 10px status bar

---

## Screens to Design

### Screen 1: Landing / Initial State
- Map shows full lunar terrain in Surface Mode
- Left panel visible with profile selector, all at default
- Right panel shows "Select start and goal on the map to begin planning" placeholder
- Footer shows system status
- No route, no markers
- **This screen should make people go "wow" — the terrain visualization is the star**

### Screen 2: Active Planning (Route Calculated)
- Start (S) and Goal (G) markers visible on map
- Route line drawn between them with risk-colored segments
- Right panel fully populated with telemetry data
- Rover animation in progress or completed
- Layer toggle showing "Slope" active

### Screen 3: Analysis Mode (Layer Overlay Active)
- Same as Screen 2 but with an analysis layer toggled ON
- Semi-transparent thermal/slope/traversability overlay on top of base terrain
- Layer control panel open showing toggle switches

### Screen 4: Multi-Profile Comparison (Stretch Goal)
- Multiple colored routes overlaid on the same map
- Right panel switches to comparison table view
- Each route in its profile color (blue, green, red, purple)

---

## Interaction Details

### Map Zoom & Pan
- Mouse wheel: zoom in/out (min 1x, max 4x)
- Click + drag: pan the map
- Double-click: zoom in centered on click point
- Floating +/- buttons for zoom control

### Point Selection Flow
1. User clicks "SET START" button (or keyboard shortcut)
2. Cursor changes to crosshair on map
3. User clicks on map → green "S" pin drops with subtle bounce animation
4. Automatically switches to "SET GOAL" mode
5. User clicks again → red "G" pin drops
6. Mode returns to idle
7. "CALCULATE ROUTE" button becomes active (brighter)

### Route Animation
1. After route calculation completes, animation auto-starts
2. White rover dot appears at Start
3. Moves along path at ~30fps
4. Trail solidifies behind the rover
5. Path ahead shown as dashed line
6. Telemetry values in right panel update in sync with rover position (optional)

---

## What NOT to Do
- Don't make the map small or secondary — it IS the product
- Don't use generic web UI patterns (no rounded cards, no shadows, no gradients on buttons)
- Don't make it look like a Bootstrap/Material dashboard
- Don't use bright white backgrounds anywhere
- Don't add unnecessary visual noise — every pixel should serve a purpose
- Don't make panels wider than specified — map real estate is sacred
- Keep it feeling technical and aerospace-grade, not consumer-app friendly

## Design References
- NASA JPL Mission Control consoles
- SpaceX Dragon/Starship cockpit displays
- Satellite ground station monitoring UIs
- Elite Dangerous galaxy map
- Military C4ISR tactical displays
- Kerbal Space Program mission planning
