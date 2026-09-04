import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import {
  generateRockField,
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
      expect(Math.hypot(rock.x, rock.z)).toBeGreaterThanOrEqual(4.5)
    }
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
      rock.position.set(descriptor.x, descriptor.radiusY * 0.88, descriptor.z)
      rock.userData.lidarRockId = descriptor.id
      rock.updateMatrixWorld(true)
      return rock
    })

    const scan = simulateLidarScan(new THREE.Vector3(0, 1.6, 0), terrain, rocks, 7)
    expect(scan.summary.detectedRocks).toBeGreaterThan(0)
    expect(scan.summary.rockReturns).toBeGreaterThan(scan.summary.detectedRocks)
    expect(scan.summary.nearestObstacleM).toBeLessThan(60)

    rocks.forEach((rock) => rock.geometry.dispose())
    material.dispose()
  })
})
