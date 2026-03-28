import { createGridMetadata } from "../models/missionModels";

export const layersMetadataMock = createGridMetadata({
  region_id: "south_pole_12x12_demo",
  region_name: "South Pole Demo Sector",
  resolution_m: 50,
  shape: [12, 12],
  start_grid: [1, 1],
  goal_grid: [10, 10],
  layers: [
    {
      id: "elevation",
      label: "Elevation",
      description: "Base topography overview derived from the DEM.",
    },
    {
      id: "slope",
      label: "Slope",
      description: "Estimated gradient severity across the grid.",
    },
    {
      id: "thermal_risk",
      label: "Thermal Risk",
      description: "Normalized risk values based on PSR proximity and thermal thresholds.",
    },
    {
      id: "traversability",
      label: "Traversability",
      description: "Relative movement difficulty combining slope and terrain roughness.",
    },
    {
      id: "psr_mask",
      label: "PSR Mask",
      description: "Static permanently shadowed region mask used for the demo.",
    },
  ],
});

export default layersMetadataMock;
