import { describe, it, expect } from 'vitest'

import { buildOverlapIgvNavigation, DEFAULT_OVERLAP_ROI_COLOR } from '../igvUtils'

describe('buildOverlapIgvNavigation', () => {
  it('builds locus and ROI configs from numeric coordinates', () => {
    const result = buildOverlapIgvNavigation(
      { chromosome: 'chr1', overlap_start: 1000, overlap_end: 2000, overlap_id: 'abc' },
      { paddingBp: 50_000, roiColor: DEFAULT_OVERLAP_ROI_COLOR },
    )

    expect(result.locus).toBe('chr1:0-52000')
    expect(result.overlapStart).toBe(1000)
    expect(result.overlapEnd).toBe(2000)
    expect(result.roiConfigs).toEqual([
      {
        color: DEFAULT_OVERLAP_ROI_COLOR,
        features: [{ chr: 'chr1', start: 1000, end: 2000, name: 'Overlap abc' }],
      },
    ])
  })

  it('parses string coordinates safely', () => {
    const result = buildOverlapIgvNavigation(
      { chromosome: 'chr2', overlap_start: '60000', overlap_end: '65000' },
      { paddingBp: 1000, roiColor: 'rgba(0,0,0,0.1)' },
    )

    expect(result.locus).toBe('chr2:59000-66000')
    expect(result.roiConfigs[0].features[0]).toMatchObject({ chr: 'chr2', start: 60000, end: 65000 })
  })
})

