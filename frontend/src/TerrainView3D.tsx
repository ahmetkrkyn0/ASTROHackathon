import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import {
  fetchBinaryGrid,
  fetchIlluminationSeries,
  fetchTerrainManifest,
  type IlluminationSeries,
  type PlanWeights,
  type TerrainManifest,
  type Waypoint,
} from './api'
import {
  aspectToRgb,
  grayReverseToRgb,
  lunarRegolithToRgb,
  magmaToRgb,
  thermalToRgb,
  viridisToRgb,
  type RGB,
} from './colormap'
import type { ClickMode, MapViewMode } from './MapCanvas'

// Which manifest layer paints the mesh for each 2-D view mode, so the two
// views never disagree about what "cost" or "shadow" looks like. The ramps
// are the same functions MapCanvas paints with.
const VIEW_LAYER: Record<MapViewMode, string> = {
  surface: 'elevation',
  thermal: 'thermal',
  cost: 'cost',
  shadow: 'shadow_ratio',
  traversability: 'traversable',
  slope: 'slope',
  aspect: 'aspect',
}

const IMPASSABLE: RGB = [120, 26, 32]
const NODATA: RGB = [8, 8, 11]

function colorFor(viewMode: MapViewMode, value: number, min: number, max: number): RGB {
  switch (viewMode) {
    case 'surface':
      return lunarRegolithToRgb(value, min, max)
    case 'thermal':
      return thermalToRgb(value, min, max)
    case 'cost':
      return viridisToRgb(value, min, max)
    case 'shadow':
      return grayReverseToRgb(value, min, max)
    case 'slope':
      return magmaToRgb(value, min, max)
    case 'aspect':
      return aspectToRgb(value)
    case 'traversability':
      return value >= 0.5 ? [86, 148, 108] : IMPASSABLE
    default:
      return NODATA
  }
}

// The single grid-to-scene mapping: the route polyline, the placed markers
// and the raycast inverse all go through it, so a change here cannot move
// one of them without moving the others. The mesh sits centred on the
// origin and is tilted -PI/2 about X, which sends its local +Y (row 0, the
// north edge) to world -Z and leaves local +X (east) as world +X. Vertices
// are sample centres spaced exactly `res` apart, spanning (n-1)*res.
function cellToWorldXZ(
  row: number,
  col: number,
  rows: number,
  cols: number,
  res: number,
): [number, number] {
  return [(col - (cols - 1) / 2) * res, (row - (rows - 1) / 2) * res]
}

function disposeChildren(group: THREE.Group) {
  for (const child of group.children) {
    const withGeometry = child as Partial<THREE.Mesh>
    withGeometry.geometry?.dispose()
    const material = withGeometry.material
    if (Array.isArray(material)) {
      material.forEach((entry) => entry.dispose())
    } else {
      material?.dispose()
    }
  }
}

const SERIES_SLICES = 24
const SERIES_SLICE_HOURS = 1
// Matches SUN_TRACK_START_UTC in lunapath/src/process_lunar_data.py, the
// epoch the baked shadow_ratio and thermal layers were integrated over. A
// different epoch here would light the scene from one date while the layer
// it tints came from another.
const SERIES_START_UTC = '2026-11-15T00:00:00'

// A pointer that moved more than this between down and up was an orbit
// drag, not a click. OrbitControls consumes the same events, so without the
// test every camera move would also drop a waypoint.
const CLICK_SLOP_PX = 5

interface Props {
  viewMode: MapViewMode
  waypoints: Waypoint[] | null
  routeStep: number | null
  roverId: string
  weights: PlanWeights
  clickMode: ClickMode
  start: [number, number] | null
  goal: [number, number] | null
  onCellClick: (row: number, col: number) => void
}

export default function TerrainView3D({
  viewMode,
  waypoints,
  routeStep,
  roverId,
  weights,
  clickMode,
  start,
  goal,
  onCellClick,
}: Props) {
  const mountRef = useRef<HTMLDivElement>(null)
  const meshRef = useRef<THREE.Mesh | null>(null)
  const sunRef = useRef<THREE.DirectionalLight | null>(null)
  const routeGroupRef = useRef<THREE.Group | null>(null)
  const pickGroupRef = useRef<THREE.Group | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  // Read inside the pointer handler, which is bound once for the lifetime of
  // the renderer. A ref keeps it current without rebuilding the scene.
  const clickModeRef = useRef(clickMode)
  const onCellClickRef = useRef(onCellClick)
  clickModeRef.current = clickMode
  onCellClickRef.current = onCellClick

  const [manifest, setManifest] = useState<TerrainManifest | null>(null)
  const [series, setSeries] = useState<IlluminationSeries | null>(null)
  const [shadowCube, setShadowCube] = useState<Float32Array | null>(null)
  const [heights, setHeights] = useState<Float32Array | null>(null)
  const [exaggeration, setExaggeration] = useState(1.5)
  const [sunSlice, setSunSlice] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState('Loading terrain manifest...')

  // ── Data: manifest, elevation field, sun track, shadow cube ────────────────
  useEffect(() => {
    const abort = new AbortController()
    let cancelled = false

    async function load() {
      try {
        setError(null)
        setStatus('Loading terrain manifest...')
        const m = await fetchTerrainManifest({ roverId, weights, signal: abort.signal })
        if (cancelled) return
        setManifest(m)
        setExaggeration(m.elevation.vertical_exaggeration_suggested)

        setStatus('Loading elevation field...')
        const cells = m.grid.rows * m.grid.cols
        const h = await fetchBinaryGrid(m.layers.elevation.binary_url, cells, abort.signal)
        if (cancelled) return
        setHeights(h)

        // The sun track is SPICE and works on its own. The shadow cube needs
        // the horizon cache; without it the series reports model "static"
        // and there is nothing to animate.
        setStatus('Loading illumination series...')
        const s = await fetchIlluminationSeries(
          {
            startUtc: SERIES_START_UTC,
            nSlices: SERIES_SLICES,
            sliceHours: SERIES_SLICE_HOURS,
            downsample: 1,
          },
          abort.signal,
        )
        if (cancelled) return
        setSeries(s)

        if (s.shadow_model.time_varying) {
          setStatus('Loading shadow cube...')
          const [t, sr, sc] = s.binary_format.shape
          const cube = await fetchBinaryGrid(
            s.fields.shadow.binary_url,
            t * sr * sc,
            abort.signal,
          )
          if (cancelled) return
          setShadowCube(cube)
        }
        setStatus('')
      } catch (err) {
        if (cancelled || abort.signal.aborted) return
        setError(err instanceof Error ? err.message : String(err))
        setStatus('')
      }
    }

    void load()
    return () => {
      cancelled = true
      abort.abort()
    }
    // Depend on the four scalars, not the object: App rebuilds `weights` with
    // a spread on every tick of a weight slider, and an identity dependency
    // would re-fetch the manifest, the 1 MB elevation field and the 24 MB
    // shadow cube on each one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roverId, weights.w_slope, weights.w_energy, weights.w_shadow, weights.w_thermal])

  // ── Scene: built once the elevation field is in ────────────────────────────
  useEffect(() => {
    const mount = mountRef.current
    if (!mount || !manifest || !heights) return

    const { rows, cols, resolution_m: res } = manifest.grid
    const { min_m } = manifest.elevation

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x05060a)
    sceneRef.current = scene

    const camera = new THREE.PerspectiveCamera(
      50,
      mount.clientWidth / Math.max(mount.clientHeight, 1),
      1,
      100000,
    )
    const span = Math.max(rows, cols) * res
    camera.position.set(span * 0.55, span * 0.45, span * 0.55)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    mount.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.maxPolarAngle = Math.PI / 2.05

    // PlaneGeometry's vertex order is row-major from the top-left, which is
    // index-for-index the same as the float32 payload.
    //
    // The extent is (cols-1)*res, NOT cols*res. cols-1 segments carry cols
    // vertices, so sizing the plane at cols*res would space them
    // cols*res/(cols-1) apart -- 5.01 m instead of 5.00 m here, a 0.2%
    // stretch, with every vertex off its true position by up to half a cell
    // at the edges. Vertices are sample centres; the distance from the first
    // centre to the last is (cols-1)*res.
    const geometry = new THREE.PlaneGeometry(
      (cols - 1) * res,
      (rows - 1) * res,
      cols - 1,
      rows - 1,
    )
    const position = geometry.attributes.position
    for (let i = 0; i < heights.length; i += 1) {
      const h = heights[i]
      // A single NaN vertex drops the ENTIRE mesh from the render. Clamp to
      // the datum rather than trusting the grid to stay clean.
      position.setZ(i, (Number.isFinite(h) ? h : min_m) - min_m)
    }
    position.needsUpdate = true
    geometry.computeVertexNormals()
    geometry.setAttribute(
      'color',
      new THREE.BufferAttribute(new Float32Array(heights.length * 3), 3),
    )

    const mesh = new THREE.Mesh(
      geometry,
      new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, metalness: 0 }),
    )
    // Lay the plane flat: +Z becomes height, and row 0 falls to -Z, i.e.
    // north. georeference.row_axis is north-to-south, col_axis west-to-east.
    mesh.rotation.x = -Math.PI / 2
    scene.add(mesh)
    meshRef.current = mesh

    const sun = new THREE.DirectionalLight(0xfff6e5, 3.0)
    scene.add(sun)
    sunRef.current = sun
    // Polar sun sits within ~1.5 deg of the horizon, so unlit faces would be
    // pure black without a floor. This is legibility, not radiometry.
    scene.add(new THREE.AmbientLight(0x5a6478, 0.55))

    const routeGroup = new THREE.Group()
    scene.add(routeGroup)
    routeGroupRef.current = routeGroup

    const pickGroup = new THREE.Group()
    scene.add(pickGroup)
    pickGroupRef.current = pickGroup
    cameraRef.current = camera

    // ── Picking ──────────────────────────────────────────────────────────
    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    let downAt: { x: number; y: number } | null = null

    const onPointerDown = (event: PointerEvent) => {
      downAt = { x: event.clientX, y: event.clientY }
    }

    const onPointerUp = (event: PointerEvent) => {
      const origin = downAt
      downAt = null
      if (!origin || clickModeRef.current === 'idle') return
      if (Math.hypot(event.clientX - origin.x, event.clientY - origin.y) > CLICK_SLOP_PX) {
        return
      }

      const rect = renderer.domElement.getBoundingClientRect()
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
      raycaster.setFromCamera(pointer, camera)
      const hit = raycaster.intersectObject(mesh, false)[0]
      if (!hit) return

      // Back to the plane's own frame, which undoes both the -PI/2 tilt and
      // the vertical exaggeration on scale.z. In that frame +X is east and
      // +Y is the row-0 edge, because PlaneGeometry lays vertices out
      // row-major from the top-left. Vertices are sample centres, so this
      // rounds to the nearest one rather than flooring into a cell.
      const local = mesh.worldToLocal(hit.point.clone())
      const col = Math.round(local.x / res + (cols - 1) / 2)
      const row = Math.round((rows - 1) / 2 - local.y / res)
      if (row < 0 || row >= rows || col < 0 || col >= cols) return

      onCellClickRef.current(row, col)
    }

    renderer.domElement.addEventListener('pointerdown', onPointerDown)
    renderer.domElement.addEventListener('pointerup', onPointerUp)

    let frame = 0
    const renderLoop = () => {
      frame = requestAnimationFrame(renderLoop)
      controls.update()
      renderer.render(scene, camera)
    }
    renderLoop()

    const onResize = () => {
      if (!mount.clientWidth || !mount.clientHeight) return
      camera.aspect = mount.clientWidth / mount.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(mount.clientWidth, mount.clientHeight)
    }
    const observer = new ResizeObserver(onResize)
    observer.observe(mount)

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      renderer.domElement.removeEventListener('pointerdown', onPointerDown)
      renderer.domElement.removeEventListener('pointerup', onPointerUp)
      controls.dispose()
      geometry.dispose()
      ;(mesh.material as THREE.Material).dispose()
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement)
      }
      meshRef.current = null
      sunRef.current = null
      disposeChildren(routeGroup)
      disposeChildren(pickGroup)
      routeGroupRef.current = null
      pickGroupRef.current = null
      cameraRef.current = null
      sceneRef.current = null
    }
  }, [manifest, heights])

  // ── Vertex colours: active layer, darkened by the current shadow slice ─────
  const activeLayerName = VIEW_LAYER[viewMode]

  useEffect(() => {
    const mesh = meshRef.current
    if (!mesh || !manifest) return
    const entry = manifest.layers[activeLayerName]
    if (!entry) return

    const abort = new AbortController()
    let cancelled = false

    async function paint() {
      const cells = manifest!.grid.rows * manifest!.grid.cols
      const values = await fetchBinaryGrid(entry.binary_url, cells, abort.signal)
      if (cancelled) return

      const colorAttr = mesh!.geometry.attributes.color as THREE.BufferAttribute
      const colors = colorAttr.array as Float32Array
      const { min, max } = entry
      const [, sr, sc] = series?.binary_format.shape ?? [0, 0, 0]
      const slice =
        shadowCube && sr * sc === cells
          ? shadowCube.subarray(sunSlice * sr * sc, (sunSlice + 1) * sr * sc)
          : null

      for (let i = 0; i < values.length; i += 1) {
        const v = values[i]
        const rgb = Number.isFinite(v) ? colorFor(viewMode, v, min, max) : NODATA
        // shadow_ratio 1 = fully dark. Keep a floor so shadowed terrain
        // stays readable instead of collapsing to black.
        const lit = slice && Number.isFinite(slice[i]) ? 1 - 0.75 * slice[i] : 1
        colors[i * 3] = (rgb[0] / 255) * lit
        colors[i * 3 + 1] = (rgb[1] / 255) * lit
        colors[i * 3 + 2] = (rgb[2] / 255) * lit
      }
      colorAttr.needsUpdate = true
    }

    void paint().catch((err) => {
      if (!cancelled && !abort.signal.aborted) {
        setError(err instanceof Error ? err.message : String(err))
      }
    })

    return () => {
      cancelled = true
      abort.abort()
    }
  }, [manifest, activeLayerName, viewMode, shadowCube, sunSlice, series])

  // ── Vertical exaggeration ──────────────────────────────────────────────────
  useEffect(() => {
    if (meshRef.current) meshRef.current.scale.z = exaggeration
  }, [exaggeration, manifest, heights])

  // ── Sun position, straight from the series that produced the shadows ───────
  useEffect(() => {
    const sun = sunRef.current
    if (!sun || !series || series.sun.length === 0 || !manifest) return
    const sample = series.sun[Math.min(sunSlice, series.sun.length - 1)]
    const a = THREE.MathUtils.degToRad(sample.azimuth_grid_deg)
    const e = THREE.MathUtils.degToRad(sample.elevation_deg)
    // Grid azimuth is clockwise from north. After the -PI/2 tilt, north is
    // -Z and east is +X.
    sun.position
      .set(Math.sin(a) * Math.cos(e), Math.sin(e), -Math.cos(a) * Math.cos(e))
      .multiplyScalar(Math.max(manifest.grid.rows, manifest.grid.cols) * manifest.grid.resolution_m * 8)
  }, [series, sunSlice, manifest])

  // ── Route polyline, sitting on the mesh via each waypoint's altitude_m ─────
  useEffect(() => {
    const group = routeGroupRef.current
    if (!group || !manifest) return

    // This effect re-runs on every exaggeration tick and playback step.
    // Group.clear() only detaches -- the GPU buffers stay allocated, so the
    // geometries and materials have to go back explicitly.
    disposeChildren(group)
    group.clear()
    if (!waypoints || waypoints.length < 2) return

    const { rows, cols, resolution_m: res } = manifest.grid
    const { min_m } = manifest.elevation
    const toWorld = (wp: Waypoint) => {
      const [x, z] = cellToWorldXZ(wp.row, wp.col, rows, cols, res)
      const alt = wp.altitude_m
      // Same datum as the mesh, then the same exaggeration, then a small
      // lift so the line is not z-fighting the surface it traces.
      const y = ((Number.isFinite(alt as number) ? (alt as number) : min_m) - min_m) * exaggeration + 4
      return new THREE.Vector3(x, y, z)
    }

    const drawUpTo = routeStep !== null ? Math.min(routeStep + 1, waypoints.length) : waypoints.length
    const points = waypoints.slice(0, Math.max(drawUpTo, 2)).map(toWorld)

    group.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(points),
        new THREE.LineBasicMaterial({ color: 0x6fe3ff }),
      ),
    )

    const marker = (position: THREE.Vector3, color: number) => {
      const m = new THREE.Mesh(
        new THREE.SphereGeometry(res * 2.5, 16, 12),
        new THREE.MeshBasicMaterial({ color }),
      )
      m.position.copy(position)
      return m
    }
    group.add(marker(toWorld(waypoints[0]), 0x53f2a5))
    group.add(marker(toWorld(waypoints[waypoints.length - 1]), 0xff6b6b))
    if (routeStep !== null && routeStep < waypoints.length) {
      group.add(marker(toWorld(waypoints[routeStep]), 0xffd166))
    }
  }, [waypoints, routeStep, manifest, exaggeration])

  // ── Placed start/goal, before any route exists ─────────────────────────────
  // Without these a click in 3-D has no visible effect until Generate Route,
  // and the user cannot tell whether the pick landed.
  useEffect(() => {
    const group = pickGroupRef.current
    if (!group || !manifest || !heights) return

    disposeChildren(group)
    group.clear()

    const { rows, cols, resolution_m: res } = manifest.grid
    const { min_m } = manifest.elevation

    const place = (cell: [number, number] | null, color: number) => {
      if (!cell) return
      const [row, col] = cell
      if (row < 0 || row >= rows || col < 0 || col >= cols) return
      const h = heights[row * cols + col]
      const marker = new THREE.Mesh(
        new THREE.SphereGeometry(res * 3, 16, 12),
        new THREE.MeshBasicMaterial({ color }),
      )
      const [x, z] = cellToWorldXZ(row, col, rows, cols, res)
      marker.position.set(
        x,
        ((Number.isFinite(h) ? h : min_m) - min_m) * exaggeration + 6,
        z,
      )
      group.add(marker)
    }

    place(start, 0x53f2a5)
    place(goal, 0xff6b6b)
  }, [start, goal, manifest, heights, exaggeration])

  const sunLabel = useMemo(() => {
    if (!series || series.sun.length === 0) return null
    const s = series.sun[Math.min(sunSlice, series.sun.length - 1)]
    return `${s.utc.replace('T', ' ').replace('Z', '')} UTC | az ${s.azimuth_grid_deg.toFixed(1)}deg el ${s.elevation_deg.toFixed(2)}deg`
  }, [series, sunSlice])

  return (
    <div className="terrain3d-shell">
      <div ref={mountRef} className="terrain3d-canvas" />

      {(status || error) && (
        <div className="terrain3d-status" role="status">
          {error ? `3-D scene error: ${error}` : status}
        </div>
      )}

      <div className="terrain3d-controls">
        <label>
          <span>Vertical exaggeration {exaggeration.toFixed(1)}x</span>
          <input
            type="range"
            min={1}
            max={6}
            step={0.1}
            value={exaggeration}
            onChange={(event) => setExaggeration(Number(event.target.value))}
          />
        </label>

        {series && series.sun.length > 0 && (
          <label>
            <span>{sunLabel}</span>
            <input
              type="range"
              min={0}
              max={series.sun.length - 1}
              step={1}
              value={sunSlice}
              onChange={(event) => setSunSlice(Number(event.target.value))}
            />
          </label>
        )}

        {series && !series.shadow_model.time_varying && (
          // Never present a frozen cube as physics.
          <p className="terrain3d-note">
            Shadow is static ({series.shadow_model.reason ?? 'no horizon cache'}). The sun
            slider still moves the light, but the shading does not follow it.
          </p>
        )}

        <p className="terrain3d-note">
          {clickMode === 'idle'
            ? 'Drag to orbit, scroll to zoom.'
            : `Drag to orbit. Click the terrain to place the ${clickMode}.`}
        </p>
      </div>
    </div>
  )
}
