import { createReplanResult } from "../models/missionModels";

export const replanResultMock = createReplanResult({
  replan_needed: true,
  scenario_id: "south_pole_demo_v1",
  trigger_type: "thermal_spike",
  affected_segment_start: 4,
  old_segment: [
    [5, 3],
    [6, 4],
    [7, 5],
    [8, 6],
  ],
  new_segment: [
    [5, 3],
    [5, 4],
    [6, 5],
    [7, 6],
    [8, 7],
  ],
  reason: "Thermal risk crossed the caution threshold near the crater rim. The route shifts one corridor east to stay inside the safe band.",
  metrics_delta: {
    distance_delta_m: 110,
    thermal_delta: -21.4,
    energy_delta: 6.3,
  },
  computation_time_ms: 218,
  event_log: [
    {
      id: "evt-001",
      timestamp: "T+00:00",
      level: "info",
      title: "Mission plan loaded",
      detail: "Baseline safe route was prepared from pre-loaded environmental layers.",
    },
    {
      id: "evt-002",
      timestamp: "T+00:14",
      level: "info",
      title: "Scenario confirmed",
      detail: "South pole crater detour scenario is active for the current mock session.",
    },
    {
      id: "evt-003",
      timestamp: "T+02:11",
      level: "warning",
      title: "Thermal event detected",
      detail: "A manual thermal spike was introduced on the active route corridor.",
    },
    {
      id: "evt-004",
      timestamp: "T+02:12",
      level: "success",
      title: "Replan preview ready",
      detail: "A safer replacement segment is available for operator review.",
    },
  ],
});

export default replanResultMock;
