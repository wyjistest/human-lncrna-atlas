import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}))

vi.mock('@/utils/export', () => ({
  saveBlobWithFilename: vi.fn(),
}))

import { analysisApi } from '@/api/analysis'
import { apiClient } from '@/api/client'
import { saveBlobWithFilename } from '@/utils/export'

describe('analysisApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('serializes mark_names as repeated query params without bracket suffixes', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { data: [], total: 0, query_params: {} },
    })

    await analysisApi.getChipseqOverlaps({
      mark_names: ['H3K27me3', 'H3K4me3'],
      limit: 50,
    })

    const [, config] = vi.mocked(apiClient.get).mock.calls[0]
    expect(config?.params).toBeInstanceOf(URLSearchParams)
    expect((config?.params as URLSearchParams).toString()).toBe(
      'mark_names=H3K27me3&mark_names=H3K4me3&limit=50',
    )
  })

  it('exports disease network as json blob with a fallback filename', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: new Blob(['{}'], { type: 'application/json' }),
      headers: {},
    })

    await analysisApi.exportDiseaseNetworkJson({
      trait_name: 'diabetes',
      limit: 100,
    })

    const [path, config] = vi.mocked(apiClient.get).mock.calls[0]
    expect(path).toBe('/api/v1/export/disease-network')
    expect(config?.responseType).toBe('blob')
    expect((config?.params as URLSearchParams).toString()).toBe(
      'trait_name=diabetes&limit=100&format=json',
    )
    expect(saveBlobWithFilename).toHaveBeenCalledWith(
      expect.any(Blob),
      {},
      expect.stringMatching(/^disease-network-\d+\.json$/),
    )
  })
})
