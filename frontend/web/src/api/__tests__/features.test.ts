import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/utils/safeWindow', () => ({
  openDownloadUrl: vi.fn(() => ({ window: {} as unknown as Window, blocked: false })),
}))

import { openDownloadUrl } from '@/utils/safeWindow'
import { featuresApi } from '@/api/features'
import { API_BASE_URL } from '@/config/api'

const openDownloadUrlMock = vi.mocked(openDownloadUrl)

describe('featuresApi.exportRepeatsToBED', () => {
  beforeEach(() => {
    openDownloadUrlMock.mockClear()
  })

  it('builds export URL and opens via openDownloadUrl', () => {
    featuresApi.exportRepeatsToBED(123, {
      repeat_class: 'LINE',
      min_divergence: 1,
      max_divergence: 20,
    })

    expect(openDownloadUrlMock).toHaveBeenCalledTimes(1)
    expect(openDownloadUrlMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/features/genes/123/repeats/export?repeat_class=LINE&min_divergence=1&max_divergence=20`
    )
  })
})
