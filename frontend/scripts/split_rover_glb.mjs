#!/usr/bin/env node
/**
 * Split a single-mesh rover GLB into a body plus four separately pivoted
 * wheel nodes, so the scene can actually turn its wheels.
 *
 * Why this exists
 * ---------------
 * The Viper asset ships in two mutually exclusive forms, and the scene
 * needs what neither of them is on its own:
 *
 *   rovers/viper/viper_rover.glb    5 nodes (wheel_1/2/4 + the misspelled
 *                                   wheek_3 + rover_body), but 0 materials,
 *                                   0 textures and no UVs -- so it renders
 *                                   as an untextured shape under the glTF
 *                                   default material.
 *   rovers/viper/viper_texture.glb  full PBR (base colour, metallic
 *                                   roughness, normal) with UVs and
 *                                   tangents, but ONE fused mesh -- so
 *                                   there is nothing to spin.
 *
 * The fused mesh turns out to separate cleanly: welding coincident vertices
 * and walking triangle connectivity yields exactly six components -- one
 * large body, four identically sized wheels at the corners, and one small
 * fitting -- so the wheels can be recovered without hand-authoring
 * anything. This writes them out as named nodes, keeping the material,
 * UVs and tangents intact.
 *
 * Pivots
 * ------
 * The wheels in the ORIGINAL split asset sit at the model origin with no
 * node translation, while their geometry is off at the corners. Rotating
 * such a node swings the wheel around the middle of the rover instead of
 * spinning it on its axle -- which is exactly what the scene did. Here each
 * wheel's geometry is recentred on its own bounding-box centre and the
 * offset moved into the node's translation, so rotating the node does the
 * one thing it looks like it should.
 *
 * Usage:
 *   node scripts/split_rover_glb.mjs <input.glb> <output.glb>
 */

import { readFileSync, writeFileSync } from 'node:fs'

const GLB_MAGIC = 0x46546c67
const CHUNK_JSON = 0x4e4f534a
const CHUNK_BIN = 0x004e4942

const COMPONENT_TYPE_SIZES = { 5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4 }
const TYPE_COMPONENT_COUNTS = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 }

function parseGlb(buffer) {
  if (buffer.readUInt32LE(0) !== GLB_MAGIC) throw new Error('not a GLB file')
  let offset = 12
  let json = null
  let bin = null
  while (offset < buffer.length) {
    const length = buffer.readUInt32LE(offset)
    const type = buffer.readUInt32LE(offset + 4)
    const chunk = buffer.subarray(offset + 8, offset + 8 + length)
    if (type === CHUNK_JSON) json = JSON.parse(chunk.toString('utf8'))
    else if (type === CHUNK_BIN) bin = chunk
    offset += 8 + length
  }
  if (!json || !bin) throw new Error('GLB is missing its JSON or BIN chunk')
  return { json, bin }
}

/** Read one accessor into a plain JS array of per-element component arrays. */
function readAccessor(json, bin, accessorIndex) {
  const accessor = json.accessors[accessorIndex]
  const view = json.bufferViews[accessor.bufferView]
  const componentSize = COMPONENT_TYPE_SIZES[accessor.componentType]
  const componentCount = TYPE_COMPONENT_COUNTS[accessor.type]
  const elementSize = componentSize * componentCount
  const stride = view.byteStride || elementSize
  const base = (view.byteOffset || 0) + (accessor.byteOffset || 0)
  const out = []
  for (let i = 0; i < accessor.count; i++) {
    const element = []
    for (let c = 0; c < componentCount; c++) {
      const at = base + i * stride + c * componentSize
      switch (accessor.componentType) {
        case 5126:
          element.push(bin.readFloatLE(at))
          break
        case 5125:
          element.push(bin.readUInt32LE(at))
          break
        case 5123:
          element.push(bin.readUInt16LE(at))
          break
        case 5121:
          element.push(bin.readUInt8(at))
          break
        case 5122:
          element.push(bin.readInt16LE(at))
          break
        default:
          element.push(bin.readInt8(at))
      }
    }
    out.push(element)
  }
  return out
}

/**
 * Union-find over triangle connectivity, with vertices first welded by
 * quantised position. Welding matters: an exporter splits a vertex wherever
 * the UV or normal is discontinuous, so a single watertight wheel arrives
 * as thousands of "separate" vertices that share a position.
 */
function connectedComponents(positions, indices) {
  const parent = new Int32Array(positions.length)
  for (let i = 0; i < parent.length; i++) parent[i] = i
  const find = (x) => {
    while (parent[x] !== x) {
      parent[x] = parent[parent[x]]
      x = parent[x]
    }
    return x
  }
  const union = (a, b) => {
    const ra = find(a)
    const rb = find(b)
    if (ra !== rb) parent[ra] = rb
  }

  const welded = new Map()
  for (let i = 0; i < positions.length; i++) {
    const key = positions[i].map((v) => Math.round(v * 1e4)).join(',')
    const existing = welded.get(key)
    if (existing === undefined) welded.set(key, i)
    else union(i, existing)
  }
  for (let t = 0; t < indices.length; t += 3) {
    union(indices[t], indices[t + 1])
    union(indices[t + 1], indices[t + 2])
  }

  const groups = new Map()
  for (let i = 0; i < positions.length; i++) {
    const root = find(i)
    let group = groups.get(root)
    if (!group) {
      group = []
      groups.set(root, group)
    }
    group.push(i)
  }
  return [...groups.values()].sort((a, b) => b.length - a.length)
}

function boundsOf(positions, vertexIndices) {
  const min = [Infinity, Infinity, Infinity]
  const max = [-Infinity, -Infinity, -Infinity]
  for (const i of vertexIndices) {
    for (let k = 0; k < 3; k++) {
      if (positions[i][k] < min[k]) min[k] = positions[i][k]
      if (positions[i][k] > max[k]) max[k] = positions[i][k]
    }
  }
  return { min, max, centre: min.map((v, k) => (v + max[k]) / 2), size: max.map((v, k) => v - min[k]) }
}

function main() {
  const [inputPath, outputPath] = process.argv.slice(2)
  if (!inputPath || !outputPath) {
    console.error('usage: node scripts/split_rover_glb.mjs <input.glb> <output.glb>')
    process.exit(1)
  }

  const { json, bin } = parseGlb(readFileSync(inputPath))
  if (json.meshes.length !== 1 || json.meshes[0].primitives.length !== 1) {
    throw new Error('expected a single fused mesh with one primitive')
  }
  const primitive = json.meshes[0].primitives[0]
  const positions = readAccessor(json, bin, primitive.attributes.POSITION)
  const indices = readAccessor(json, bin, primitive.indices).map((e) => e[0])
  const attributeNames = Object.keys(primitive.attributes)
  const attributes = Object.fromEntries(
    attributeNames.map((name) => [name, readAccessor(json, bin, primitive.attributes[name])]),
  )

  const components = connectedComponents(positions, indices)
  console.log(`found ${components.length} connected components`)
  for (const [i, component] of components.entries()) {
    const { size, centre } = boundsOf(positions, component)
    console.log(
      `  ${i}: ${component.length} verts  size ${size.map((v) => v.toFixed(3)).join(' x ')}  centre ${centre
        .map((v) => v.toFixed(3))
        .join(', ')}`,
    )
  }

  // The body is the largest component; the wheels are the four next largest
  // that share a size to within a few per cent. Anything else (a fitting, a
  // stray shell) is folded into the body rather than dropped, so the split
  // never silently loses geometry.
  const [body, ...rest] = components
  const wheelCandidates = rest.filter((c) => c.length > positions.length * 0.02).slice(0, 4)
  if (wheelCandidates.length !== 4) {
    throw new Error(`expected 4 wheel components, found ${wheelCandidates.length}`)
  }
  const leftovers = rest.filter((c) => !wheelCandidates.includes(c))
  const bodyVertices = [body, ...leftovers].flat()

  // Name by position: the long horizontal axis is front/back, the short one
  // is left/right. Front is +long simply so the four names are distinct and
  // stable; nothing downstream depends on which end is called front.
  const wheelBounds = wheelCandidates.map((c) => boundsOf(positions, c))
  const bodySize = boundsOf(positions, bodyVertices).size
  const longAxis = bodySize[0] >= bodySize[2] ? 0 : 2
  const sideAxis = longAxis === 0 ? 2 : 0
  const longMid =
    wheelBounds.reduce((sum, b) => sum + b.centre[longAxis], 0) / wheelBounds.length
  const sideMid = wheelBounds.reduce((sum, b) => sum + b.centre[sideAxis], 0) / wheelBounds.length
  const parts = [{ name: 'rover_body', vertices: bodyVertices, recentre: false }]
  wheelCandidates.forEach((component, index) => {
    const centre = wheelBounds[index].centre
    const front = centre[longAxis] >= longMid ? 'f' : 'r'
    const side = centre[sideAxis] >= sideMid ? 'l' : 'r'
    parts.push({ name: `wheel_${front}${side}`, vertices: component, recentre: true })
  })

  // ---- rebuild the binary chunk -------------------------------------------
  const segments = []
  let binLength = 0
  const pushSegment = (buffer) => {
    const padded = buffer.length % 4 === 0 ? buffer : Buffer.concat([buffer, Buffer.alloc(4 - (buffer.length % 4))])
    const offset = binLength
    segments.push(padded)
    binLength += padded.length
    return { offset, length: buffer.length }
  }

  const newBufferViews = []
  const newAccessors = []

  // Texture image data carries over byte for byte.
  const imageViewRemap = new Map()
  for (const image of json.images ?? []) {
    if (image.bufferView === undefined) continue
    const view = json.bufferViews[image.bufferView]
    const bytes = bin.subarray(view.byteOffset || 0, (view.byteOffset || 0) + view.byteLength)
    const placed = pushSegment(Buffer.from(bytes))
    imageViewRemap.set(image.bufferView, newBufferViews.length)
    newBufferViews.push({ buffer: 0, byteOffset: placed.offset, byteLength: placed.length })
  }
  for (const image of json.images ?? []) {
    if (image.bufferView === undefined) continue
    image.bufferView = imageViewRemap.get(image.bufferView)
  }

  const newMeshes = []
  const newNodes = []
  for (const part of parts) {
    const vertexSet = new Set(part.vertices)
    const remap = new Map()
    part.vertices.forEach((original, next) => remap.set(original, next))
    const translation = part.recentre ? boundsOf(positions, part.vertices).centre : [0, 0, 0]

    const partAttributes = {}
    for (const name of attributeNames) {
      const source = attributes[name]
      const componentCount = source[0].length
      const buffer = Buffer.alloc(part.vertices.length * componentCount * 4)
      const min = new Array(componentCount).fill(Infinity)
      const max = new Array(componentCount).fill(-Infinity)
      part.vertices.forEach((original, next) => {
        for (let c = 0; c < componentCount; c++) {
          let value = source[original][c]
          if (name === 'POSITION' && c < 3) value -= translation[c]
          buffer.writeFloatLE(value, (next * componentCount + c) * 4)
          if (value < min[c]) min[c] = value
          if (value > max[c]) max[c] = value
        }
      })
      const placed = pushSegment(buffer)
      newBufferViews.push({
        buffer: 0,
        byteOffset: placed.offset,
        byteLength: placed.length,
        target: 34962,
      })
      partAttributes[name] = newAccessors.length
      newAccessors.push({
        bufferView: newBufferViews.length - 1,
        componentType: 5126,
        count: part.vertices.length,
        type: componentCount === 4 ? 'VEC4' : componentCount === 3 ? 'VEC3' : 'VEC2',
        min,
        max,
      })
    }

    const partIndices = []
    for (let t = 0; t < indices.length; t += 3) {
      if (!vertexSet.has(indices[t])) continue
      partIndices.push(remap.get(indices[t]), remap.get(indices[t + 1]), remap.get(indices[t + 2]))
    }
    const indexBuffer = Buffer.alloc(partIndices.length * 4)
    partIndices.forEach((value, i) => indexBuffer.writeUInt32LE(value, i * 4))
    const placedIndices = pushSegment(indexBuffer)
    newBufferViews.push({
      buffer: 0,
      byteOffset: placedIndices.offset,
      byteLength: placedIndices.length,
      target: 34963,
    })
    const indexAccessor = newAccessors.length
    newAccessors.push({
      bufferView: newBufferViews.length - 1,
      componentType: 5125,
      count: partIndices.length,
      type: 'SCALAR',
    })

    newMeshes.push({
      name: `${part.name}_mesh`,
      primitives: [
        {
          attributes: partAttributes,
          indices: indexAccessor,
          ...(primitive.material !== undefined ? { material: primitive.material } : {}),
        },
      ],
    })
    const node = { name: part.name, mesh: newMeshes.length - 1 }
    if (part.recentre) node.translation = translation
    newNodes.push(node)
    console.log(
      `  -> ${part.name}: ${part.vertices.length} verts, ${partIndices.length / 3} tris` +
        (part.recentre ? `, pivot at ${translation.map((v) => v.toFixed(3)).join(', ')}` : ''),
    )
  }

  // The wheels are children of the body so the whole rover moves as one, the
  // way the original split asset was arranged.
  newNodes[0].children = newNodes.slice(1).map((_, i) => i + 1)

  const outputJson = {
    asset: { version: '2.0', generator: 'lunapath split_rover_glb.mjs' },
    scene: 0,
    scenes: [{ name: 'Scene', nodes: [0] }],
    nodes: newNodes,
    meshes: newMeshes,
    accessors: newAccessors,
    bufferViews: newBufferViews,
    buffers: [{ byteLength: binLength }],
    ...(json.materials ? { materials: json.materials } : {}),
    ...(json.textures ? { textures: json.textures } : {}),
    ...(json.images ? { images: json.images } : {}),
    ...(json.samplers ? { samplers: json.samplers } : {}),
  }

  let jsonBuffer = Buffer.from(JSON.stringify(outputJson), 'utf8')
  if (jsonBuffer.length % 4 !== 0) {
    jsonBuffer = Buffer.concat([jsonBuffer, Buffer.alloc(4 - (jsonBuffer.length % 4), 0x20)])
  }
  const binBuffer = Buffer.concat(segments)
  const header = Buffer.alloc(12)
  header.writeUInt32LE(GLB_MAGIC, 0)
  header.writeUInt32LE(2, 4)
  header.writeUInt32LE(12 + 8 + jsonBuffer.length + 8 + binBuffer.length, 8)
  const jsonHeader = Buffer.alloc(8)
  jsonHeader.writeUInt32LE(jsonBuffer.length, 0)
  jsonHeader.writeUInt32LE(CHUNK_JSON, 4)
  const binHeader = Buffer.alloc(8)
  binHeader.writeUInt32LE(binBuffer.length, 0)
  binHeader.writeUInt32LE(CHUNK_BIN, 4)

  writeFileSync(outputPath, Buffer.concat([header, jsonHeader, jsonBuffer, binHeader, binBuffer]))
  console.log(`wrote ${outputPath} (${(binBuffer.length / 1048576).toFixed(1)} MB of binary)`)
}

main()
