import { describe, expect, it } from 'vitest'

import { GLOBAL_COMPARE_UNAVAILABLE_MESSAGE, globalCompareApi } from '@/api/globalCompare'

describe('globalCompareApi', () => {
  it('exposes an explicit unavailable contract', async () => {
    expect(globalCompareApi.isAvailable).toBe(false)
    expect(globalCompareApi.availabilityReason).toBe(GLOBAL_COMPARE_UNAVAILABLE_MESSAGE)

    await expect(globalCompareApi.getGlobalCompare()).rejects.toThrow(GLOBAL_COMPARE_UNAVAILABLE_MESSAGE)
    await expect(globalCompareApi.getSignalDistribution()).rejects.toThrow(GLOBAL_COMPARE_UNAVAILABLE_MESSAGE)
  })
})
