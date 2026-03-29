import { createGridMetadata } from "../models/missionModels";

export const layersMetadataMock = createGridMetadata({
  region_id: "south_pole_demo_sector",
  region_name: "Shackleton Crater - South Rim",
  resolution_m: 80,
  shape: [500, 500],
  origin_m: {
    x: 176000,
    y: 48000,
  },
  extent_m: {
    width: 40000,
    height: 40000,
  },
  projection: "Moon 2015 Polar Stereographic",
  start_grid: [78, 64],
  goal_grid: [402, 426],
  coordinate_units: "meters",
  alternate_coordinate_units: "kilometers",
  grid_size_px: [500, 500],
  route_overlay_supported: true,
  grid_lines_supported: true,
  overlay_opacity_default: 0.82,
  layers: [
    {
      id: "elevation",
      label: "Elevation",
      api_key: "elevation_grid",
      cmap: "terrain",
      unit: "m",
      value_range: [-4315, 4262],
      description: "Topographic overview derived from the DEM using the terrain color scale.",
    },
    {
      id: "slope",
      label: "Slope",
      api_key: "slope_grid",
      cmap: "magma",
      unit: "deg",
      value_range: [0, 34],
      description: "Gradient severity map rendered with the magma scale for steepness hotspots.",
    },
    {
      id: "thermal_risk",
      label: "Thermal Risk",
      api_key: "thermal_risk_grid",
      cmap: "hot",
      unit: "score",
      value_range: [0, 1],
      description: "Normalized thermal hazard field combining illumination, shadow proximity, and thresholds.",
    },
    {
      id: "traversability",
      label: "Traversability",
      api_key: "traversability_grid",
      cmap: "RdYlGn",
      unit: "score",
      value_range: [0, 1],
      description: "Relative mobility cost map using the RdYlGn scale from impassable to favorable terrain.",
    },
    {
      id: "psr_mask",
      label: "PSR Mask",
      api_key: "psr_mask",
      cmap: "bone",
      unit: "boolean",
      value_range: [0, 1],
      description: "Permanently shadowed region mask rendered with the bone scale for cold-trap awareness.",
    },
  ],
});

export default layersMetadataMock;
