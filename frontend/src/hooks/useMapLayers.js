import { useCallback, useEffect, useState } from "react";
import missionService from "../services/missionService";

const DEFAULT_LAYER_IDS = ["thermal_risk"];

export function useMapLayers({ region, scenarioId, initialLayerIds = DEFAULT_LAYER_IDS } = {}) {
  const [layersMetadata, setLayersMetadata] = useState(null);
  const [activeLayerIds, setActiveLayerIds] = useState(initialLayerIds);
  const [overlayOpacity, setOverlayOpacity] = useState(0.82);
  const [axisUnit, setAxisUnit] = useState("m");
  const [routeOverlayVisible, setRouteOverlayVisible] = useState(true);
  const [gridLinesVisible, setGridLinesVisible] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadLayers() {
      try {
        setLoading(true);
        const metadata = await missionService.getLayersMetadata({ region, scenarioId });
        if (cancelled) return;

        setLayersMetadata(metadata);
        setOverlayOpacity(metadata.overlay_opacity_default ?? 0.82);
        setError("");
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Layer metadata could not be loaded.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadLayers();

    return () => {
      cancelled = true;
    };
  }, [region, scenarioId]);

  const toggleLayer = useCallback((layerId) => {
    setActiveLayerIds((current) => (
      current.includes(layerId)
        ? current.filter((id) => id !== layerId)
        : [...current, layerId]
    ));
  }, []);

  return {
    layersMetadata,
    layers: layersMetadata?.layers ?? [],
    activeLayerIds,
    toggleLayer,
    overlayOpacity,
    setOverlayOpacity,
    axisUnit,
    setAxisUnit,
    routeOverlayVisible,
    setRouteOverlayVisible,
    gridLinesVisible,
    setGridLinesVisible,
    loading,
    error,
  };
}

export default useMapLayers;
