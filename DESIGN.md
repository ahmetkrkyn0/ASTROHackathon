# Design System Strategy: The Orbital Horizon

## 1. Overview & Creative North Star
The Creative North Star for this design system is **"The Orbital Horizon."** 

This system rejects the cluttered, high-contrast "gamer" aesthetic typical of aerospace interfaces in favor of Swiss-inspired clarity and editorial breathing room. We are not building a dashboard; we are building a high-fidelity instrument for precision decision-making. 

To break the "template" look, this system utilizes **intentional asymmetry**. Primary telemetry data is often offset or anchored to a rigid 8.5rem (Token 24) margin, while secondary glass-lite panels float with subtle overlaps. This layering creates a sense of physical depth—as if the user is looking through a series of precision-engineered glass lenses at a clear white horizon.

---

## 2. Colors & Surface Logic
The palette is rooted in high-visibility neutrals, using NASA-spec accents only for critical functional signaling.

### The "No-Line" Rule
Designers are prohibited from using 1px solid borders to define major layout sections. Separation must be achieved through **Tonal Transitions**. A sidebar should not be "boxed in"; it should be defined by a shift from `surface` (#F8F9FA) to `surface_container_low` (#F3F4F5). 

### Surface Hierarchy & Nesting
Treat the UI as a physical stack of materials. 
- **Base Layer:** `surface` (#F8F9FA) - The vast "canvas" of the mission.
- **Content Zones:** `surface_container_low` (#F3F4F5) - Used for large, distinct background areas.
- **Active Modules:** `surface_container_lowest` (#FFFFFF) - Used for the most important data cards to make them "pop" against the gray base.

### The "Glass & Gradient" Rule
To add "soul" to the minimalism, primary actions and floating telemetry panels must use **Glassmorphism-Lite**. 
- **Application:** Use `surface_container_lowest` at 70% opacity with a `16px` backdrop-blur. 
- **Signature Texture:** Primary CTAs may use a razor-thin linear gradient from `primary` (#5B5F63) to `primary_container` (#8E9297) at a 135-degree angle to provide a metallic, tactile feel without breaking the flat aesthetic.

---

## 3. Typography
We utilize **Inter** for its mathematical precision and neutral character.

- **Display (3.5rem):** Reserved for singular, mission-critical metrics (e.g., "T-Minus" or "Velocity"). Use `Extra-Bold` (700) with `-0.02em` tracking.
- **Headline (2rem):** Used for view titles. Set in `Semi-Bold` (600) to anchor the page.
- **Title (1.125rem):** Used for module headers. 
- **Body (0.875rem):** The workhorse. Maintain a generous `1.5` line-height for readability during high-stress monitoring.
- **Label (0.6875rem):** Use `Medium` (500) and All-Caps for technical metadata and sensor labels.

**Editorial Tip:** Use "Weight Contrast" rather than "Color Contrast." Pair a `Bold` Title with a `Light` Body to create hierarchy without exhausting the user's eyes with too many colors.

---

## 4. Elevation & Depth
Depth in this system is a function of light and density, not drop-shadows.

### The Layering Principle
Achieve lift by stacking tokens. Place a `surface_container_lowest` card atop a `surface_container_low` section. The subtle contrast (pure white on ultra-light gray) creates a "soft lift" that feels premium and intentional.

### Ambient Shadows
For floating panels (e.g., a "Replanning" modal), use an **Ambient Shadow**:
- **X/Y:** 0, 12px
- **Blur:** 40px
- **Color:** `on_surface` (#191C1D) at **4% opacity**.
This mimics the soft, non-directional light of an orbital environment.

### The "Ghost Border"
If a container requires a border for accessibility, use the **Ghost Border**:
- **Token:** `outline_variant` (#BDCAB9)
- **Opacity:** **15%**.
- **Rule:** Never use 100% opaque borders for interior layout containment.

---

## 5. Components

### Buttons
- **Primary:** Pill-shaped (Roundness `full`). Background: `secondary` (#28A745) for "Go/Safe" or `primary` (#5B5F63) for standard.
- **Tertiary:** No background. Use `label-md` weight. This is the preferred style for "Cancel" or "Back" to keep the UI clean.

### Pill Segmented Controls
Used for toggling view modes (e.g., Trajectory vs. Telemetry). 
- **Container:** `surface_container_high` with `full` rounding. 
- **Selected State:** A `surface_container_lowest` pill with an Ambient Shadow, creating a physical "switch" look.

### Telemetry Cards & Lists
- **Rule:** **Strictly forbid divider lines.** 
- **Separation:** Use Spacing Scale `3` (1rem) for vertical separation.
- **Leading Elements:** Use NASA-spec status pips (e.g., a 4px `secondary` dot) to indicate system health instead of large icons.

### Refined Sliders
- **Track:** 2px height using `outline_variant` at 20% opacity.
- **Thumb:** A pure white circle (`surface_container_lowest`) with a 1px `outline` (#6E7B6B). 

### Precision Scrubber (Context-Specific)
For mission timelines. A horizontal scroll area using `body-sm` for timestamps. Current time is indicated by a razor-thin `secondary` line that spans the full height of the component.

---

## 6. Do's and Don'ts

### Do:
- **Use White Space as a Tool:** If a section feels crowded, increase the margin to `20` (7rem) rather than adding a divider.
- **Maintain Monospace Numbers:** For any changing data, ensure the font features use `tabular-nums` to prevent the UI from "jumping" as numbers change.
- **Embrace Asymmetry:** Align primary controls to the right and telemetry to the left to create a sophisticated, custom-engineered layout.

### Don't:
- **Don't use "Gamer" Gradients:** No neon glows or deep black backgrounds. Keep it "Bright Mission Control."
- **Don't use standard Tooltips:** Tooltips should be glassmorphic with `surface_container_lowest` and 20% opacity `outline-variant` borders.
- **Don't crowd the edges:** Maintain a minimum outer margin of Token `12` (4rem) on all screens. Precision requires space.