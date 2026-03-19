import { test, expect } from '@playwright/test'

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'

test.describe('ChIP-seq compare API contract', () => {
  test('legacy global compare endpoints are not exposed', async ({ request }) => {
    const legacyEndpoints = [
      '/api/v1/chipseq/global-compare',
      '/api/v1/chipseq/cell-line-matrix',
      '/api/v1/chipseq/signal-distribution',
    ]

    for (const endpoint of legacyEndpoints) {
      const response = await request.get(`${API_BASE}${endpoint}`)
      expect(response.status(), `${endpoint} should not be public`).toBe(404)
    }
  })

  test('real gene-scoped ChIP-seq endpoints still live under /api/v1/features/chipseq', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/marks`, {
      params: { species_id: 1 },
    })

    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(Array.isArray(data)).toBeTruthy()
  })
})
