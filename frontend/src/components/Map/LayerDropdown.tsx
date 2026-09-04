import React, { useState, useRef, useEffect } from 'react'
import type { MapViewMode } from '../../MapCanvas'

interface LayerDropdownProps {
  viewMode: MapViewMode
  onViewModeChange: (mode: MapViewMode) => void
  dimension: '2d' | '3d'
  onDimensionChange: (dim: '2d' | '3d') => void
  hudOpen?: boolean
  onToggleHud?: () => void
}

interface LayerOption {
  id: MapViewMode
  label: string
  desc: string
}

interface LayerGroup {
  name: string
  options: LayerOption[]
}

const LAYER_GROUPS: LayerGroup[] = [
  {
    name: 'Terrain',
    options: [
      { id: 'surface', label: 'Surface', desc: 'Lunar Regolith Topography & Hillshade' },
      { id: 'slope', label: 'Slope', desc: 'Terrain Incline (Degrees)' },
      { id: 'aspect', label: 'Aspect', desc: 'Surface Facing Direction' },
    ],
  },
  {
    name: 'Environment',
    options: [
      { id: 'thermal', label: 'Thermal', desc: 'Surface Temperature (Kelvin / °C)' },
      { id: 'shadow', label: 'Shadow', desc: 'Permanent Shadow Region Ratio' },
    ],
  },
  {
    name: 'Planning',
    options: [
      { id: 'cost', label: 'Cost', desc: 'A* Multi-Factor Weighted Cost Grid' },
      { id: 'traversability', label: 'Traverse', desc: 'Rover Incline & Obstacle Mask' },
    ],
  },
]

export const LayerDropdown: React.FC<LayerDropdownProps> = ({
  viewMode,
  onViewModeChange,
  dimension,
  onDimensionChange,
  hudOpen = true,
  onToggleHud,
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Find active option
  let activeOption: LayerOption = { id: 'surface', label: 'Surface', desc: 'Topography' }
  for (const group of LAYER_GROUPS) {
    const found = group.options.find((opt) => opt.id === viewMode)
    if (found) {
      activeOption = found
      break
    }
  }

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  return (
    <div className="lp-map-controls-dock" ref={menuRef}>
      {/* HUD Overlay Toggle */}
      {onToggleHud && (
        <button
          type="button"
          className={`lp-hud-dock-btn ${hudOpen ? 'is-active' : ''}`}
          onClick={onToggleHud}
          title={hudOpen ? 'Hide On-Screen Telemetry HUD' : 'Show On-Screen Telemetry HUD'}
        >
          <span className="lp-dock-icon">📍</span>
          <span>HUD</span>
        </button>
      )}

      {/* 2D / 3D Dimension Switcher */}
      <div className="lp-dim-toggle">
        <button
          type="button"
          className={`lp-dim-btn ${dimension === '2d' ? 'is-active' : ''}`}
          onClick={() => onDimensionChange('2d')}
        >
          2D
        </button>
        <button
          type="button"
          className={`lp-dim-btn ${dimension === '3d' ? 'is-active' : ''}`}
          onClick={() => onDimensionChange('3d')}
        >
          3D
        </button>
      </div>

      {/* Layer Dropdown Trigger */}
      <div className="lp-layer-menu-wrapper">
        <button
          type="button"
          className={`lp-layer-trigger ${isOpen ? 'is-open' : ''}`}
          onClick={() => setIsOpen((prev) => !prev)}
          aria-expanded={isOpen}
        >
          <span className="lp-layer-label-hint">LAYER</span>
          <strong className="lp-layer-current-name">{activeOption.label}</strong>
          <span className="lp-dropdown-chevron" aria-hidden="true">
            {isOpen ? '▴' : '▾'}
          </span>
        </button>

        {isOpen && (
          <div className="lp-layer-dropdown-panel" role="menu">
            {LAYER_GROUPS.map((group) => (
              <div key={group.name} className="lp-layer-group">
                <div className="lp-layer-group-header">{group.name}</div>
                <div className="lp-layer-group-items">
                  {group.options.map((opt) => {
                    const isSelected = opt.id === viewMode
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        role="menuitem"
                        className={`lp-layer-item ${isSelected ? 'is-selected' : ''}`}
                        onClick={() => {
                          onViewModeChange(opt.id)
                          setIsOpen(false)
                        }}
                      >
                        <div className="lp-layer-item-content">
                          <span className="lp-layer-item-title">{opt.label}</span>
                          <span className="lp-layer-item-desc">{opt.desc}</span>
                        </div>
                        {isSelected && <span className="lp-layer-check">✓</span>}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default LayerDropdown
