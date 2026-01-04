import { describe, expect, it } from 'vitest'

import { getMax, getMinMax } from './minMax'

describe('getMinMax', () => {
  it('returns defaults when no finite values', () => {
    expect(getMinMax([], { defaultMin: 0, defaultMax: 1 })).toEqual({ min: 0, max: 1 })
    expect(getMinMax([null, undefined], { defaultMin: -1, defaultMax: 2 })).toEqual({ min: -1, max: 2 })
    expect(getMinMax([NaN, Infinity, -Infinity], { defaultMin: 3, defaultMax: 4 })).toEqual({ min: 3, max: 4 })
  })

  it('includes baseline values when provided', () => {
    expect(getMinMax([2, 3], { defaultMin: 0, defaultMax: 1, include: [0, 1] })).toEqual({
      min: 0,
      max: 3,
    })
    expect(getMinMax([0.2, 0.5], { defaultMin: 0, defaultMax: 1, include: [0, 1] })).toEqual({
      min: 0,
      max: 1,
    })
  })
})

describe('getMax', () => {
  it('returns default when no finite values', () => {
    expect(getMax([], 0)).toBe(0)
    expect(getMax([null, undefined, NaN], 5)).toBe(5)
  })

  it('returns maximum of finite values', () => {
    expect(getMax([1, 3, 2], 0)).toBe(3)
    expect(getMax([null, 1, undefined, 2], 0)).toBe(2)
  })
})

