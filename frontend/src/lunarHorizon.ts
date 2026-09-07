import * as THREE from 'three'

interface TerrainEdge {
  rows: number
  cols: number
  resolutionM: number
  minM: number
  heights: Float32Array
}

/** Decorative terrain only. Never used for picking, shadows, routes or LiDAR. */
export function createLunarHorizon({ rows, cols, resolutionM, minM, heights }: TerrainEdge) {
  const width = cols * resolutionM
  const depth = rows * resolutionM
  const span = Math.max(width, depth)
  const edge: THREE.Vector3[] = []
  const add = (row: number, col: number) => {
    const h = heights[row * cols + col]
    edge.push(new THREE.Vector3(
      col * width / (cols - 1) - width / 2,
      Number.isFinite(h) ? h - minM : 0,
      row * depth / (rows - 1) - depth / 2,
    ))
  }
  // Match PlaneGeometry's edge samples exactly, including rectangular DEMs.
  for (let c = 0; c < cols; c++) add(0, c)
  for (let r = 1; r < rows; r++) add(r, cols - 1)
  for (let c = cols - 2; c >= 0; c--) add(rows - 1, c)
  for (let r = rows - 2; r > 0; r--) add(r, 0)

  const mean = edge.reduce((total, p) => total + p.y, 0) / edge.length
  // Fine DEM bumps must not extrude into kilometre-long radial grooves.
  // Preserve every real edge vertex, then low-pass the collar away from it.
  const smoothingRadius = Math.max(1, Math.floor(edge.length / 40))
  const smoothEdge = edge.map((_, i) => {
    let sum = 0
    for (let offset = -smoothingRadius; offset <= smoothingRadius; offset++) {
      sum += edge[(i + offset + edge.length) % edge.length].y
    }
    return sum / (smoothingRadius * 2 + 1)
  })
  const rings = [1, 1.08, 1.22, 1.5, 2, 2.8, 3.8, 5.2, 7, 10, 14, 20]
  const positions = new Float32Array(rings.length * edge.length * 3)
  const colours = new Float32Array(positions.length)
  const indices: number[] = []
  const albedo = new THREE.Color(0x7a746c)

  rings.forEach((scale, ring) => {
    edge.forEach((p, i) => {
      const angle = Math.atan2(p.z, p.x)
      const blend = THREE.MathUtils.smoothstep(scale, 1, 2.8)
      // Broad, irregular crater rims. Fixed harmonics keep the backdrop stable
      // across mounts; these are a composition, not a claimed regional DEM.
      const ridge = 0.65 + 0.20 * Math.sin(angle * 5 + 0.7)
        + 0.10 * Math.sin(angle * 11 - 1.2) + 0.05 * Math.cos(angle * 23)
      const nearRim = Math.exp(-Math.pow((scale - 3.8) / 1.4, 2))
      const farRim = Math.exp(-Math.pow((scale - 10) / 3.8, 2))
      const height = mean * 0.65 + span * ridge * (nearRim * 0.22 + farRim * 0.38)
      const at = (ring * edge.length + i) * 3
      positions[at] = p.x * scale
      const collarHeight = THREE.MathUtils.lerp(p.y, smoothEdge[i], THREE.MathUtils.smoothstep(scale, 1, 1.08))
      positions[at + 1] = THREE.MathUtils.lerp(collarHeight, height, blend)
      positions[at + 2] = p.z * scale
      // Subtle tonal variation; no atmospheric haze on an airless landscape.
      const tone = 1 - blend * (0.10 + 0.08 * (1 - ridge))
      colours[at] = albedo.r * tone
      colours[at + 1] = albedo.g * tone
      colours[at + 2] = albedo.b * tone
      if (ring < rings.length - 1) {
        const a = ring * edge.length + i
        const b = ring * edge.length + (i + 1) % edge.length
        const c = a + edge.length
        const d = b + edge.length
        indices.push(a, b, c, b, d, c)
      }
    })
  })

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colours, 3))
  geometry.setIndex(indices)
  geometry.computeVertexNormals()
  const material = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, metalness: 0 })
  const mesh = new THREE.Mesh(geometry, material)
  const boundaryGeometry = new THREE.BufferGeometry().setFromPoints([
    ...edge.map(p => p.clone().add(new THREE.Vector3(0, 0.8, 0))),
    edge[0].clone().add(new THREE.Vector3(0, 0.8, 0)),
  ])
  const boundaryMaterial = new THREE.LineDashedMaterial({
    color: 0xaebbc7, transparent: true, opacity: 0.45,
    dashSize: span / 100, gapSize: span / 150, depthWrite: false,
  })
  const boundary = new THREE.Line(boundaryGeometry, boundaryMaterial)
  boundary.computeLineDistances()
  const group = new THREE.Group()
  group.add(mesh, boundary)

  return {
    group, mesh, boundary,
    dispose: () => {
      geometry.dispose()
      material.dispose()
      boundaryGeometry.dispose()
      boundaryMaterial.dispose()
    },
  }
}
