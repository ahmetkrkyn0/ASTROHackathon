import { describe, expect, it } from 'vitest'

import type { BinaryField } from '../../net/layers'
import { categoryCounts, categoryValues, coarseFieldCommands } from './overlays'
import { COARSE_FIELDS, coarseFieldById } from './fields'

const P_SAFE = coarseFieldById('p_safe')
const BEST_ACTION = coarseFieldById('best_action')
const SIDE = coarseFieldById('side')

function field(data: Float32Array, overrides: Partial<BinaryField> = {}): BinaryField {
  return {
    data,
    rows: 3,
    cols: 4,
    resolutionM: 20,
    downsample: 4,
    validity: 'MODEL',
    min: 0,
    max: 1,
    nodataCount: 0,
    layerName: 'test',
    ...overrides,
  }
}

/** The real action codes: 0-7 moves, 8 wait, 254 safe, 255 none. */
const ACTIONS = new Float32Array([0, 5, 8, 254, 255, NaN, 3, 254, 255, 255, 1, NaN])

describe('categorical encoding', () => {
  it('emits one single-colour mask per category, never a ramp', () => {
    const commands = coarseFieldCommands(BEST_ACTION, field(ACTIONS))
    expect(commands.length).toBeGreaterThan(1)
    for (const command of commands) {
      if (command.kind !== 'field') throw new Error('expected field commands')
      // Both stops identical: there is exactly one value in each mask, so
      // there is nothing for the renderer to interpolate between. That is what
      // makes this encoding categorical rather than a two-stop gradient.
      expect(command.ramp.colors).toHaveLength(2)
      expect(command.ramp.colors[0]).toEqual(command.ramp.colors[1])
    }
  })

  it('never places two codes in one mask’s value range', () => {
    // A ramp over best_action would give code 130 a colour halfway between
    // "drive north" and "already safe" -- an action the policy never returned.
    const commands = coarseFieldCommands(BEST_ACTION, field(ACTIONS))
    for (const command of commands) {
      if (command.kind !== 'field') throw new Error('expected field commands')
      const distinct = new Set(command.values.filter((v) => v !== null))
      expect(distinct).toEqual(new Set([1]))
    }
  })

  it('groups the eight compass moves into one category', () => {
    const drive = BEST_ACTION.render.mode === 'categorical'
      ? BEST_ACTION.render.categories.find((c) => c.key === 'drive')
      : undefined
    expect(drive?.codes).toEqual([0, 1, 2, 3, 4, 5, 6, 7])
    const values = categoryValues(field(ACTIONS), drive!)
    // Codes 0, 5, 3 and 1 in the fixture above.
    expect(values.filter((v) => v !== null)).toHaveLength(4)
  })

  it('keeps "no action helps" apart from "not traversable"', () => {
    // 255 means the policy found nothing; NaN means the block is not passable
    // at all. Different facts, and merging them would report a policy failure
    // where there is simply no ground.
    const none = BEST_ACTION.render.mode === 'categorical'
      ? BEST_ACTION.render.categories.find((c) => c.key === 'none')!
      : undefined
    const values = categoryValues(field(ACTIONS), none!)
    expect(values).toEqual([
      null, null, null, null, 1, null, null, null, 1, 1, null, null,
    ])
  })

  it('drops a category with no cells rather than blitting an empty grid', () => {
    // `wait` covers three blocks out of 15 625 on the real window; an empty
    // one still costs a full-grid allocation and a blit.
    const noWait = new Float32Array([0, 254, 255, NaN, 1, 2, 3, 4, 5, 6, 7, 254])
    const commands = coarseFieldCommands(BEST_ACTION, field(noWait))
    expect(commands.map((c) => c.id)).not.toContain('coarse-best_action-wait')
    expect(commands.map((c) => c.id)).toContain('coarse-best_action-drive')
  })

  it('reads side codes as three separate categories', () => {
    const commands = coarseFieldCommands(
      SIDE,
      field(new Float32Array([0, 1, 2, 1, 2, 1, NaN, 0, 1, 2, 2, 1])),
    )
    expect(commands.map((c) => c.id).sort()).toEqual([
      'coarse-side-cold',
      'coarse-side-hot',
      'coarse-side-inside',
    ])
  })
})

describe('coarseFieldCommands, scalar', () => {
  it('draws a ramp over the field’s own measured range', () => {
    const commands = coarseFieldCommands(
      P_SAFE,
      field(new Float32Array([0, 0.25, 0.5, 0.75, 1, NaN, 0, 1, 0.5, 0.5, 0, 1]), {
        min: 0,
        max: 1,
      }),
    )
    expect(commands).toHaveLength(1)
    const command = commands[0]
    if (command.kind !== 'field') throw new Error('expected a field command')
    expect(command.ramp.colors.length).toBeGreaterThan(2)
    expect(command.values[5]).toBeNull()
  })

  it('keeps the coarse shape rather than the fine grid’s', () => {
    const commands = coarseFieldCommands(
      P_SAFE,
      field(new Float32Array(12), { rows: 3, cols: 4, downsample: 4, min: 0, max: 1 }),
    )
    const command = commands[0]
    if (command.kind !== 'field') throw new Error('expected a field command')
    // drawField blits at these dimensions with smoothing off, so each value
    // stays a 20 m block instead of being interpolated to look like 5 m data.
    expect([command.rows, command.cols]).toEqual([3, 4])
  })

  it('draws nothing for a field with no gradient', () => {
    expect(
      coarseFieldCommands(P_SAFE, field(new Float32Array(12), { min: 1, max: 1 })),
    ).toEqual([])
  })
})

describe('categoryCounts', () => {
  it('counts each category and ignores NaN', () => {
    const counts = categoryCounts(
      field(ACTIONS),
      BEST_ACTION.render.mode === 'categorical' ? BEST_ACTION.render.categories : [],
    )
    expect(counts).toMatchObject({ drive: 4, wait: 1, safe: 2, none: 3 })
    expect(counts.__unknown).toBeUndefined()
  })

  it('reports a code the table does not cover instead of dropping it', () => {
    // A backend that grows a fifth action must surface as a visible unknown,
    // not as cells that quietly stop being drawn.
    const counts = categoryCounts(
      field(new Float32Array([0, 8, 254, 255, 42, 42, NaN, 0, 0, 0, 0, 0])),
      BEST_ACTION.render.mode === 'categorical' ? BEST_ACTION.render.categories : [],
    )
    expect(counts.__unknown).toBe(2)
  })
})

describe('coarse field table', () => {
  it('states a limit on every field', () => {
    for (const spec of COARSE_FIELDS) {
      expect(spec.limit.length, `${spec.id} has no limit`).toBeGreaterThan(20)
    }
  })

  it('marks the two code fields categorical and the two scalars not', () => {
    expect(coarseFieldById('best_action').render.mode).toBe('categorical')
    expect(coarseFieldById('side').render.mode).toBe('categorical')
    expect(coarseFieldById('p_safe').render.mode).toBe('ramp')
    expect(coarseFieldById('max_dwell_h').render.mode).toBe('ramp')
  })

  it('gives every category a distinct colour within its field', () => {
    for (const spec of COARSE_FIELDS) {
      if (spec.render.mode !== 'categorical') continue
      const colours = spec.render.categories.map((c) => c.color.join(','))
      expect(new Set(colours).size).toBe(colours.length)
    }
  })
})
