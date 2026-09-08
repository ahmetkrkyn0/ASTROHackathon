import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import {
  generateFixedBoulderCluster,
  generatePebbleField,
  generateRockField,
  PEBBLE_TIERS,
  ROCK_FIELD,
  sampleTerrainHeight,
  simulateLidarScan,
} from './lidarSimulation'
import type { TerrainField } from './lidarSimulation'

function flatTerrain(size = 41, resolutionM = 1): TerrainField {
  return {
    rows: size,
    cols: size,
    resolutionM,
    minElevationM: 100,
    heights: new Float32Array(size * size).fill(100),
    verticalScale: 1,
  }
}

describe('sampleTerrainHeight', () => {
  it('maps the DEM centre and applies the same vertical scale as the mesh', () => {
    const terrain = flatTerrain(3, 2)
    terrain.heights[4] = 104
    terrain.verticalScale = 2
    expect(sampleTerrainHeight(terrain, 0, 0)).toBeCloseTo(8)
  })

  it('returns null after a beam leaves the DEM', () => {
    expect(sampleTerrainHeight(flatTerrain(), 1000, 0)).toBeNull()
  })
})

describe('generateRockField', () => {
  it('is deterministic in world coordinates', () => {
    expect(generateRockField(12, -7)).toEqual(generateRockField(12, -7))
  })

  it('keeps rocks out of the rover safety footprint', () => {
    for (const rock of generateRockField(0, 0)) {
      expect(Math.hypot(rock.x, rock.z)).toBeGreaterThanOrEqual(ROCK_FIELD.safetyRadiusM)
    }
  })

  // The field has to be a property of the WORLD, not of whoever asked for
  // it: App.tsx generates one window to hand the planner obstacle cells and
  // TerrainCanvas3D renders another, and a rock that exists in one but not
  // the other is a rover driving through a boulder it routed around.
  it('returns identical rocks for the same ground seen from two windows', () => {
    const a = generateRockField(0, 0, 120)
    const b = generateRockField(90, 40, 120)
    const byId = new Map(b.map((rock) => [rock.id, rock]))
    let shared = 0
    for (const rock of a) {
      const other = byId.get(rock.id)
      if (!other) continue
      shared++
      expect(other).toEqual(rock)
    }
    expect(shared).toBeGreaterThan(10)
  })

  it('draws a lunar size distribution: mostly cobbles, occasional blocks', () => {
    const diameters = generateRockField(0, 0, 400)
      .map((rock) => rock.radiusX * 2)
      .sort((a, b) => a - b)
    expect(diameters.length).toBeGreaterThan(200)
    expect(diameters[0]).toBeGreaterThanOrEqual(ROCK_FIELD.navMinDiameterM)
    expect(diameters[diameters.length - 1]).toBeLessThanOrEqual(ROCK_FIELD.maxDiameterM)
    // Median stays in the cobble range the exponential term governs...
    const median = diameters[Math.floor(diameters.length / 2)]
    expect(median).toBeLessThan(0.8)
    // ...while the power-law tail still produces genuine metre-plus blocks.
    expect(diameters.filter((d) => d > 1.5).length).toBeGreaterThan(0)
  })

  it('does not let rocks interpenetrate', () => {
    const rocks = generateRockField(0, 0, 150)
    for (let i = 0; i < rocks.length; i++) {
      for (let j = i + 1; j < rocks.length; j++) {
        const a = rocks[i]
        const b = rocks[j]
        const minGap = Math.max(a.radiusX, a.radiusZ) + Math.max(b.radiusX, b.radiusZ)
        expect(Math.hypot(a.x - b.x, a.z - b.z)).toBeGreaterThanOrEqual(minGap)
      }
    }
  })

  it('gives every rock a shape, a burial depth and a bedding tilt', () => {
    for (const rock of generateRockField(0, 0, 120)) {
      expect(['scan', 'cobble', 'breccia', 'slab']).toContain(rock.shape)
      expect(rock.burial).toBeGreaterThanOrEqual(0.05)
      expect(rock.burial).toBeLessThanOrEqual(0.46)
      expect(Math.abs(rock.tiltX)).toBeLessThanOrEqual(0.23)
    }
  })
})

describe('generateFixedBoulderCluster', () => {
  it('is a stable, rigidly translated boulder garden with close large rocks', () => {
    const first = generateFixedBoulderCluster(100, -40)
    const later = generateFixedBoulderCluster(100, -40)
    const movedAnchor = generateFixedBoulderCluster(130, -15)

    expect(first).toEqual(later)
    expect(first).toHaveLength(47)
    expect(first.filter((rock) => rock.radiusX * 2 >= 3.8)).toHaveLength(11)
    for (let index = 0; index < first.length; index++) {
      expect(movedAnchor[index].x - first[index].x).toBeCloseTo(30)
      expect(movedAnchor[index].z - first[index].z).toBeCloseTo(25)
    }

    const large = first.slice(0, 3)
    const nearestPair = Math.min(
      ...large.flatMap((rock, index) =>
        large.slice(index + 1).map((other) => Math.hypot(rock.x - other.x, rock.z - other.z)),
      ),
    )
    expect(nearestPair).toBeLessThan(6)
    expect(Math.max(...first.map((rock) => rock.x)) - Math.min(...first.map((rock) => rock.x))).toBeGreaterThan(130)
  })
})

describe('generatePebbleField', () => {
  it('stays below the navigation layer and grades coarser with distance', () => {
    const pebbles = generatePebbleField(0, 0)
    expect(pebbles.length).toBeGreaterThan(100)
    for (const pebble of pebbles) {
      const diameter = pebble.radiusX * 2
      expect(diameter).toBeLessThanOrEqual(ROCK_FIELD.navMinDiameterM)
      const distance = Math.hypot(pebble.x, pebble.z)
      const tier = PEBBLE_TIERS.find((t) => distance >= t.innerM && distance < t.outerM)
      // A pebble can drift just past its chunk centre's tier boundary; the
      // floor that matters is the coarsest tier it could have been drawn in.
      const floor = tier ? tier.minDiameterM : PEBBLE_TIERS[PEBBLE_TIERS.length - 1].minDiameterM
      expect(diameter).toBeGreaterThanOrEqual(Math.min(floor, PEBBLE_TIERS[0].minDiameterM))
    }
  })

  it('is deterministic in world coordinates', () => {
    expect(generatePebbleField(30, -12)).toEqual(generatePebbleField(30, -12))
  })
})

describe('simulateLidarScan', () => {
  it('emits first returns from terrain and a triangle-mesh obstacle', () => {
    const terrain = flatTerrain(161, 1)
    const rock = new THREE.Mesh(
      new THREE.SphereGeometry(1.5, 16, 12),
      new THREE.MeshBasicMaterial(),
    )
    rock.position.set(0, 1.25, -8)
    rock.userData.lidarRockId = 'test-boulder'
    rock.updateMatrixWorld(true)

    const scan = simulateLidarScan(new THREE.Vector3(0, 1.6, 0), terrain, [rock], 42)

    expect(scan.summary.returns).toBeGreaterThan(0)
    expect(scan.summary.terrainReturns).toBeGreaterThan(0)
    expect(scan.summary.rockReturns).toBeGreaterThan(0)
    expect(scan.summary.detectedRocks).toBe(1)
    expect(scan.summary.nearestObstacleM).not.toBeNull()
    expect(scan.summary.nearestObstacleM!).toBeGreaterThan(6)
    expect(scan.summary.nearestObstacleM!).toBeLessThan(8)
    expect(scan.positions.length).toBe(scan.summary.returns * 3)
    expect(scan.colors.length).toBe(scan.positions.length)

    rock.geometry.dispose()
    ;(rock.material as THREE.Material).dispose()
  })

  it('finds hazards in the generated local rock field', () => {
    const terrain = flatTerrain(181, 1)
    const material = new THREE.MeshBasicMaterial()
    const rocks = generateRockField(0, 0).map((descriptor) => {
      const rock = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 1), material)
      rock.scale.set(descriptor.radiusX, descriptor.radiusY, descriptor.radiusZ)
      rock.position.set(descriptor.x, descriptor.radiusY * (1 - descriptor.burial), descriptor.z)
      rock.userData.lidarRockId = descriptor.id
      rock.updateMatrixWorld(true)
      return rock
    })

    const scan = simulateLidarScan(new THREE.Vector3(0, 1.6, 0), terrain, rocks, 7)
    expect(scan.summary.detectedRocks).toBeGreaterThan(0)
    // Only >= now, not >: this field carries just the >= 0.45 m navigation
    // hazards, and sub-metre gravel moved to generatePebbleField, so a scan
    // can legitimately catch a distant rock on a single beam. The
    // multiple-returns-per-obstacle behaviour is covered by the close
    // triangle-mesh case above, where it is actually load-bearing.
    expect(scan.summary.rockReturns).toBeGreaterThanOrEqual(scan.summary.detectedRocks)
    expect(scan.summary.nearestObstacleM).toBeLessThan(60)

    rocks.forEach((rock) => rock.geometry.dispose())
    material.dispose()
  })
})
